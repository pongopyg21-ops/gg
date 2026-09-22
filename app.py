import os
import io
import secrets
import re
import sqlite3
import zipfile
from contextlib import closing
import datetime

from flask import Flask, g, jsonify, request, send_file, send_from_directory, session

import allergens
import faq
import houses
import igiene
import magazzino
import units
import voice
import voce_cloud

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Il database storico: la prima casa, quella che raccoglie quello che c'era
# prima che le case esistessero. Le altre stanno in `case/case-<slug>.db`,
# e tutte seguono `MAGGIORDOMO_DATA` (vedi houses.py): il codice puo' stare in
# un'immagine, i dati no.
DB_PATH = os.environ.get("CUCINA_DB", os.path.join(houses.DATA_DIR, "cucina.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = houses.secret_key()
# Il biscotto di sessione dura a lungo: l'utente scrive nome e password una volta
# sola, poi resta collegato anche riaprendo il browser giorni dopo.
app.config.update(PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=365),
                  SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax")

# Quanti pasti al giorno e quali. L'utente sceglie il numero nel primo passo
# dell'onboarding, e da lì derivano i pasti mostrati nel piano e accettati
# dall'API. Due è il valore di partenza.
MEAL_SETS = {
    1: ["cena"],
    2: ["pranzo", "cena"],
    3: ["colazione", "pranzo", "cena"],
    4: ["colazione", "pranzo", "merenda", "cena"],
    5: ["colazione", "spuntino", "pranzo", "merenda", "cena"],
}
MEALS_PER_DAY_MIN, MEALS_PER_DAY_MAX = 1, 5
MEALS = MEAL_SETS[2]


def valid_meals(db):
    """I pasti che l'utente ha scelto di gestire.

    Il numero sta nel profilo: da qui si ricava l'elenco, che è l'unica fonte
    dei pasti validi sia in lettura sia in scrittura.
    """
    scelti = get_profile(db).get("meals_per_day") or 2
    return MEAL_SETS.get(int(scelti), MEALS)


def casa_attiva():
    """Lo slug della casa collegata, o None. Sta nella sessione firmata."""
    return session.get("casa")


def get_db():
    """Il database della casa collegata.

    Aprire il file giusto e' tutto quello che separa due case: le query restano
    identiche a prima, quindi non c'e' modo di dimenticarsi un filtro. Senza
    sessione non c'e' database: le API rispondono 401 e non toccano nulla.
    """
    if "db" not in g:
        slug = casa_attiva()
        if not slug:
            return None
        g.db = sqlite3.connect(houses.db_path(slug))
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate(db):
    """Aggiunge le colonne mancanti ai database creati da versioni precedenti.

    `CREATE TABLE IF NOT EXISTS` non tocca le tabelle esistenti: senza questo
    passaggio un database gia' in uso resterebbe senza le colonne nuove.
    """
    have = {r["name"] for r in db.execute("PRAGMA table_info(recipes)")}
    for col, ddl in (
        ("image", "ALTER TABLE recipes ADD COLUMN image TEXT NOT NULL DEFAULT ''"),
        ("image_credit", "ALTER TABLE recipes ADD COLUMN image_credit TEXT NOT NULL DEFAULT ''"),
    ):
        if col not in have:
            db.execute(ddl)

    # chi si era profilato prima che esistesse la scelta delle preferite non l'ha
    # mai vista: il passo gli viene riproposto una volta sola
    have = {r["name"] for r in db.execute("PRAGMA table_info(profile)")}
    if have and "fav_prompted" not in have:
        db.execute("ALTER TABLE profile ADD COLUMN fav_prompted INTEGER NOT NULL DEFAULT 0")
    # i profili nati prima della scelta dei pasti restano a due, il valore storico
    if have and "meals_per_day" not in have:
        db.execute("ALTER TABLE profile ADD COLUMN meals_per_day INTEGER NOT NULL DEFAULT 2")
    # il giorno fisso delle pulizie: sabato, come suggerisce l'articolo
    if have and "chore_day" not in have:
        db.execute("ALTER TABLE profile ADD COLUMN chore_day INTEGER NOT NULL DEFAULT 5")

    # Il catalogo delle pulizie si semina qui, non in seed.py: la sezione Igiene
    # deve funzionare anche su un database creato prima che esistesse, senza
    # obbligare a rilanciare il seed a mano. L'inserimento e' idempotente e non
    # tocca le righe gia' presenti, cosi' le modifiche dell'utente restano.
    _semina_pulizie(db)

    # Le voci create prima che esistesse la distinzione non dicono da dove
    # vengono, e non c'e' modo di ricavarlo: anche una voce scritta a mano
    # valorizza `ingredient_id`. Si marcano tutte come generate, cosi' la prima
    # rigenerazione ripulisce la lista accumulata invece di lasciarla a meta'.
    # Le poche voci aggiunte a mano prima dell'aggiornamento vanno reinserite:
    # meglio una lista che riparte pulita che una che resta sbagliata.
    have = {r["name"] for r in db.execute("PRAGMA table_info(shopping_items)")}
    if have and "generated" not in have:
        db.execute("ALTER TABLE shopping_items ADD COLUMN generated INTEGER NOT NULL DEFAULT 0")
        db.execute("UPDATE shopping_items SET generated = 1")


def _semina_pulizie(db):
    # `migrate` viene chiamata anche su database vecchi a cui manca del tutto la
    # tabella: senza questo controllo il seme fallirebbe su un DB legittimo
    tabelle = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "chores" not in tabelle:
        return
    esistenti = {r["name"] for r in db.execute("SELECT name FROM chores")}
    nuove = [v for v in igiene.catalogo() if v["name"] not in esistenti]
    if not nuove:
        return
    db.executemany(
        """INSERT INTO chores (name, area, frequency, minutes, month)
           VALUES (:name, :area, :frequency, :minutes, :month)""",
        nuove,
    )


def init_db(percorso=None, con_ricettario=False):
    """Crea (se serve) il database di una casa e vi applica schema e migrazioni.

    `con_ricettario` serve alle case nuove: nascono col ricettario italiano di
    partenza invece che vuote. Non si usa per il database storico, che ha gia' i
    suoi dati.
    """
    percorso = percorso or DB_PATH
    with closing(sqlite3.connect(percorso)) as db:
        db.row_factory = sqlite3.Row
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            db.executescript(fh.read())
        migrate(db)
        db.commit()
    if con_ricettario:
        _semina_ricettario(percorso)


def _semina_ricettario(percorso):
    """Il ricettario di partenza in una casa nuova.

    Riusa `seed.py` invece di duplicare l'elenco: le ricette sono 45 e con le
    foto, e tenerne due copie significherebbe che un giorno divergono.
    """
    import seed

    seed.semina(percorso)


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


def one(cur):
    r = cur.fetchone()
    return dict(r) if r else None


# ---------------------------------------------------------------- accesso
# Le rotte pubbliche sono poche e non toccano dati di una casa: la pagina, i
# file statici e l'accesso. Tutto il resto richiede una sessione. La difesa sta
# qui, in un punto solo, invece che su ogni rotta: dimenticarsene una
# significherebbe esporre i dati di una casa, e sono cinquanta.
ROTTE_PUBBLICHE = {"/", "/api/houses", "/api/login", "/api/logout", "/api/session"}


@app.before_request
def richiedi_accesso():
    percorso = request.path
    if percorso in ROTTE_PUBBLICHE:
        return None
    if percorso.startswith("/static/"):
        return None
    if casa_attiva():
        return None
    return jsonify({"error": "Non sei collegato a nessuna casa", "auth": False}), 401


@app.route("/api/session")
def api_session():
    """Chi e' collegato. La usa la pagina per decidere se mostrare l'accesso."""
    slug = casa_attiva()
    if not slug:
        return jsonify({"authenticated": False})
    nome = houses.nome_di(slug)
    if nome is None:
        # la casa e' stata eliminata mentre la sessione era aperta
        session.clear()
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "house": slug, "nome": nome})


@app.route("/api/backup")
def api_backup():
    """Scarica i dati della casa collegata come file.

    Serve a spostare il lavoro da un posto a un altro: i database **non sono in
    git** (contengono dati di casa, non codice), quindi senza questo passaggio
    cambiare macchina significherebbe ripartire da zero. E' anche l'unico modo di
    avere un salvataggio dei propri dati senza accedere al disco del server.

    Esporta **solo la casa collegata**, mai l'intero registro: chi condivide una
    casa non deve poter scaricare i dati dell'altra. Il file e' una copia
    coerente, presa con l'API di backup di SQLite (non copiando il file mentre e'
    in uso, che darebbe un database corrotto) e ripulita dal diario di
    scrittura, che non serve a chi riceve la copia.

    Il nome resta quello del database: cosi' il file si rimette al suo posto
    senza rinominarlo, ed e' quello che serve a chi lo reimporta.
    """
    slug = casa_attiva()
    if not slug:
        return jsonify({"error": "Non sei collegato a nessuna casa"}), 401

    percorso = houses.db_path(slug)
    if not os.path.exists(percorso):
        return jsonify({"error": "Il database di questa casa non esiste"}), 404

    memoria = io.BytesIO()
    with closing(sqlite3.connect(percorso)) as origine, closing(sqlite3.connect(":memory:")) as copia:
        origine.backup(copia)

        # I diari di scrittura non servono alla copia, e sqlite3 ne creerebbe uno
        # per il file temporaneo: si passa a `journal_mode=DELETE` prima di
        # leggere, cosi' l'archivio non contiene tracce del percorso originale.
        copia.execute("PRAGMA journal_mode=DELETE")
        dump = "\n".join(copia.iterdump())

    nome = os.path.basename(percorso)
    # La destinazione non e' sempre la stessa: la casa storica ha il database
    # accanto al codice, le altre nella sottocartella `case/`. Indicare il
    # percorso esatto evita di rimettere il file dove l'app non lo cerca, che e'
    # il modo piu' facile di credere di aver recuperato i dati e non averlo fatto.
    destinazione = os.path.relpath(percorso, houses.DATA_DIR)
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nome, dump)
        # Un file in scena: dice da dove viene e quando e' stato preso, cosi' fra
        # tre copie sul disco si sa quale tenere.
        z.writestr(
            "LEGGIMI.txt",
            "Copia dei dati de Il Maggiordomo\n"
            f"Casa: {houses.nome_di(slug) or slug}\n"
            f"Data: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"File: {nome}\n\n"
            "Per rimetterla in funzione, nella cartella dell'app:\n"
            f"  - copia {nome} in  {destinazione}\n"
            "  - se l'app era avviata, riavviala dopo averlo copiato\n\n"
            "In pratica: metti il file dove stanno gli altri database (accanto al\n"
            "codice, oppure nella sottocartella case/). Non serve rinominarlo.\n",
        )

    memoria.seek(0)
    return send_file(
        memoria,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"maggiordomo-{slug}-{datetime.date.today().isoformat()}.zip",
    )


@app.route("/api/houses")
def api_houses():
    """Le case esistenti, per proporle nella schermata di accesso.

    Non e' un'informazione sensibile: sono nomi di casa, e senza la password non
    danno accesso a nulla.
    """
    return jsonify(houses.elenco())


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True) or {}
    casa = houses.per_nome(data.get("nome"))
    if not casa or not houses.autentica(casa["slug"], data.get("password")):
        # stesso messaggio per casa inesistente e password sbagliata: dire quale
        # delle due e' errata aiuterebbe a indovinare le case altrui
        return bad_request("Nome o password non corretti", 401)
    session.clear()
    session["casa"] = casa["slug"]
    session.permanent = True
    return jsonify({"house": casa["slug"], "nome": casa["nome"]})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/houses", methods=["POST"])
def api_house_create():
    """Crea una casa con il ricettario di partenza e vi collega chi la crea."""
    data = request.get_json(force=True) or {}
    try:
        slug = houses.crea(data.get("nome"), data.get("password"))
    except ValueError as err:
        return bad_request(str(err))
    init_db(houses.db_path(slug), con_ricettario=True)
    session.clear()
    session["casa"] = slug
    session.permanent = True
    return jsonify({"house": slug, "nome": houses.nome_di(slug)}), 201


def bad_request(msg, code=400):
    return jsonify({"error": msg}), code


def parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_or_create_ingredient(db, name, unit="pz", category="Altro"):
    name = (name or "").strip()
    if not name:
        return None
    cur = db.execute("SELECT * FROM ingredients WHERE name = ? COLLATE NOCASE", (name,))
    found = one(cur)
    if found:
        return found["id"]
    cur = db.execute(
        "INSERT INTO ingredients (name, unit, category) VALUES (?, ?, ?)",
        (name, unit, category),
    )
    return cur.lastrowid


def delete_orphan_ingredients(db):
    """Rimuove gli ingredienti che nessuno usa piu'.

    Eliminando una ricetta, `recipe_items` sparisce per CASCADE ma la riga in
    `ingredients` resta: e' un catalogo, non un dato della ricetta. Senza questa
    pulizia il nome continua a comparire nel riepilogo allergeni e fra i
    suggerimenti del form, anche se nessuna ricetta lo nomina piu'.

    Un ingrediente con una giacenza in dispensa o una voce in lista e' ancora in
    uso: la spesa si genera dalle ricette, ma un articolo comprato a mano ha
    diritto a restare. Per questo la condizione guarda tutte e tre le tabelle.
    """
    db.execute(
        """DELETE FROM ingredients
           WHERE id NOT IN (SELECT DISTINCT ingredient_id FROM recipe_items)
             AND id NOT IN (SELECT ingredient_id FROM pantry)
             AND id NOT IN (SELECT ingredient_id FROM shopping_items
                            WHERE ingredient_id IS NOT NULL)"""
    )


def parse_terms(raw):
    """Da testo libero a elenco di termini: separatori riga, virgola e punto e virgola."""
    if isinstance(raw, (list, tuple)):
        parts = [str(p) for p in raw]
    else:
        parts = re.split(r"[,;\n]+", str(raw or ""))
    seen, terms = set(), []
    for part in parts:
        term = part.strip()
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def favorite_ids(db):
    """Id delle ricette preferite, in ordine di nome (come l'elenco ricette)."""
    cur = db.execute(
        """SELECT f.recipe_id FROM favorites f JOIN recipes r ON r.id = f.recipe_id
           ORDER BY r.name"""
    )
    return [r["recipe_id"] for r in cur]


def set_favorites(db, raw):
    """Sostituisce l'insieme delle preferite.

    Gli id che non corrispondono a una ricetta esistente vengono ignorati invece
    di far fallire il salvataggio: un elenco scelto prima che una ricetta venisse
    eliminata altrove non deve bloccare l'utente.
    """
    valid = {r["id"] for r in db.execute("SELECT id FROM recipes")}
    wanted = []
    seen = set()
    for value in raw if isinstance(raw, (list, tuple)) else []:
        try:
            rid = int(value)
        except (TypeError, ValueError):
            continue
        if rid in valid and rid not in seen:
            seen.add(rid)
            wanted.append(rid)
    db.execute("DELETE FROM favorites")
    db.executemany("INSERT INTO favorites (recipe_id) VALUES (?)", [(r,) for r in wanted])
    db.commit()
    return favorite_ids(db)


def get_profile(db):
    """Profilo utente; la riga viene creata al primo accesso."""
    cur = db.execute("SELECT * FROM profile WHERE id = 1")
    profile = one(cur)
    if profile is None:
        db.execute("INSERT INTO profile (id) VALUES (1)")
        db.commit()
        profile = one(db.execute("SELECT * FROM profile WHERE id = 1"))
    profile["restriction_list"] = parse_terms(profile["restrictions"])
    profile["favorite_ids"] = favorite_ids(db)
    return profile


PROFILE_FIELDS = {"full_name", "restrictions", "onboarded", "fav_prompted",
                  "meals_per_day", "chore_day"}


def save_profile(db, data):
    # la riga singola deve esistere prima dell'UPDATE, altrimenti non aggiorna nulla
    get_profile(db)
    # le preferite stanno in una tabella a parte: si toccano solo se il campo
    # e' presente, cosi' un salvataggio parziale (es. solo il nome) non le azzera
    if "favorite_ids" in data:
        set_favorites(db, data["favorite_ids"])
    values = {k: data[k] for k in PROFILE_FIELDS if k in data}
    if "restrictions" in values:
        values["restrictions"] = ", ".join(parse_terms(values["restrictions"]))
    for flag in ("onboarded", "fav_prompted"):
        if flag in values:
            values[flag] = 1 if values[flag] else 0
    if "meals_per_day" in values:
        try:
            scelti = int(values["meals_per_day"])
        except (TypeError, ValueError):
            raise ValueError("Numero di pasti non valido (da 1 a 5)")
        if scelti not in MEAL_SETS:
            raise ValueError("Numero di pasti non valido (da 1 a 5)")
        values["meals_per_day"] = scelti
    if "chore_day" in values:
        try:
            giorno = int(values["chore_day"])
        except (TypeError, ValueError):
            raise ValueError("Giorno delle pulizie non valido (da 0 a 6)")
        if not 0 <= giorno <= 6:
            raise ValueError("Giorno delle pulizie non valido (da 0 a 6)")
        values["chore_day"] = giorno
    if values:
        assignments = ", ".join(f"{k} = ?" for k in values)
        db.execute(
            f"UPDATE profile SET {assignments}, updated_at = datetime('now') WHERE id = 1",
            list(values.values()),
        )
        db.commit()
    return get_profile(db)


def recipe_safety(db, rid, restriction_list):
    """Allergeni riconosciuti negli ingredienti e termini dichiarati che combaciano."""
    names = [r["name"] for r in db.execute(
        """SELECT i.name FROM recipe_items ri JOIN ingredients i ON i.id = ri.ingredient_id
           WHERE ri.recipe_id = ?""",
        (rid,),
    )]
    tags = allergens.tags_for(names)
    return tags, allergens.matching_terms(restriction_list, tags, names)


# ---------------------------------------------------------------- index
@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "index.html")


@app.route("/api/meta")
def meta():
    db = get_db()
    return jsonify({"meals": valid_meals(db), "meals_per_day": get_profile(db).get("meals_per_day") or 2,
                    "meal_sets": {str(k): v for k, v in MEAL_SETS.items()},
                    "units": ["pz", "g", "kg", "ml", "l", "cucchiaio", "cucchiaino", "confezione", "fetta"],
                    "categories": ["Frutta e Verdura", "Carne e Pesce", "Latticini", "Dispensa",
                                   "Pane e Cereali", "Surgelati", "Bevande", "Dolci", "Altro"],
                    "allergens": [{"key": k, "label": v} for k, v in allergens.ALLERGENS.items()]})


# ---------------------------------------------------------------- profilo
@app.route("/api/profile", methods=["GET", "PUT"])
def profile():
    db = get_db()
    if request.method == "PUT":
        data = request.get_json(force=True) or {}
        try:
            return jsonify(save_profile(db, data))
        except ValueError as err:
            return bad_request(str(err) or "Valore non valido")
    return jsonify(get_profile(db))


@app.route("/api/profile/allergens", methods=["GET"])
def profile_allergens():
    """Quali allergeni sono riconosciuti in ciascun ingrediente in uso."""
    db = get_db()
    cur = db.execute("SELECT DISTINCT name FROM ingredients ORDER BY name")
    return jsonify({r["name"]: sorted(allergens.allergens_for(r["name"])) for r in cur})


# ---------------------------------------------------------------- ingredients
@app.route("/api/ingredients", methods=["GET", "POST"])
def ingredients():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return bad_request("Il nome è obbligatorio")
        iid = get_or_create_ingredient(db, name, units.normalize(data.get("unit")), data.get("category") or "Altro")
        db.commit()
        return jsonify({"id": iid}), 201
    cur = db.execute("SELECT * FROM ingredients WHERE name LIKE ? ORDER BY name", (f"%{request.args.get('q', '')}%",))
    return jsonify(rows(cur))


# ---------------------------------------------------------------- pantry
@app.route("/api/pantry", methods=["GET"])
def pantry_list():
    db = get_db()
    cur = db.execute(
        """SELECT p.id, p.quantity, p.unit, p.updated_at,
                  i.id AS ingredient_id, i.name, i.category
           FROM pantry p JOIN ingredients i ON i.id = p.ingredient_id
           ORDER BY i.name"""
    )
    return jsonify(rows(cur))


@app.route("/api/pantry", methods=["POST"])
def pantry_add():
    db = get_db()
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return bad_request("Il nome è obbligatorio")
    unit = units.normalize(data.get("unit"))
    iid = get_or_create_ingredient(db, name, unit, data.get("category") or "Altro")
    qty = parse_float(data.get("quantity"), 0)
    existing = one(db.execute(
        "SELECT * FROM pantry WHERE ingredient_id = ? AND unit = ?", (iid, unit)))
    if not existing:
        # nessuna riga nella stessa unità: si prova ad accodarsi a una compatibile
        for cand in db.execute("SELECT * FROM pantry WHERE ingredient_id = ?", (iid,)):
            converted = units.convert(qty, unit, cand["unit"])
            if converted is not None:
                db.execute(
                    "UPDATE pantry SET quantity = quantity + ?, updated_at = datetime('now') WHERE id = ?",
                    (converted, cand["id"]))
                db.commit()
                rebuild_shopping(db)
                db.commit()
                return jsonify({"ok": True}), 201
        db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, ?, ?)", (iid, qty, unit))
    else:
        db.execute("UPDATE pantry SET quantity = quantity + ?, updated_at = datetime('now') WHERE id = ?",
                   (qty, existing["id"]))
    db.commit()
    # quello che entra in dispensa non serve piu' comprarlo: la lista segue
    rebuild_shopping(db)
    db.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/pantry/<int:pid>", methods=["PATCH", "DELETE"])
def pantry_modify(pid):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM pantry WHERE id = ?", (pid,))
        delete_orphan_ingredients(db)
        # senza la scorta in casa l'ingrediente torna da comprare
        rebuild_shopping(db)
        db.commit()
        return jsonify({"ok": True})
    data = request.get_json(force=True) or {}
    db.execute("UPDATE pantry SET quantity = ?, updated_at = datetime('now') WHERE id = ?",
               (parse_float(data.get("quantity"), 0), pid))
    rebuild_shopping(db)
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- recipes
def recipe_full(db, rid):
    rec = one(db.execute("SELECT * FROM recipes WHERE id = ?", (rid,)))
    if not rec:
        return None
    rec["items"] = rows(db.execute(
        """SELECT ri.id, ri.quantity, ri.unit, i.id AS ingredient_id, i.name
           FROM recipe_items ri JOIN ingredients i ON i.id = ri.ingredient_id
           WHERE ri.recipe_id = ? ORDER BY i.name""",
        (rid,),
    ))
    rec["favorite"] = rid in set(favorite_ids(db))
    return rec


def clean_image(value):
    """Accetta solo un nome di file semplice, senza percorsi ne' traversal."""
    nome = os.path.basename((value or "").strip())
    if not nome or nome != (value or "").strip():
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.(jpg|jpeg|png|webp)", nome, re.IGNORECASE):
        return ""
    return nome


IMAGE_DIR = os.path.join(BASE_DIR, "static", "recipes")


@app.route("/api/recipe-images")
def recipe_images():
    """Nomi dei file immagine disponibili, per il campo foto del form."""
    try:
        nomi = sorted(f for f in os.listdir(IMAGE_DIR)
                      if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    except OSError:
        nomi = []
    return jsonify(nomi)


@app.route("/api/recipes", methods=["GET", "POST"])
def recipes():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return bad_request("Il nome è obbligatorio")
        image = clean_image(data.get("image"))
        cur = db.execute(
            "INSERT INTO recipes (name, servings, time_minutes, difficulty, instructions, image, image_credit)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, int(parse_float(data.get("servings"), 2)), data.get("time_minutes") or None,
             data.get("difficulty") or "facile", data.get("instructions") or "",
             image, (data.get("image_credit") or "").strip() if image else ""),
        )
        rid = cur.lastrowid
        for it in data.get("items") or []:
            iname = (it.get("name") or "").strip()
            if not iname:
                continue
            iid = get_or_create_ingredient(db, iname, units.normalize(it.get("unit")), it.get("category") or "Altro")
            db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)",
                       (rid, iid, parse_float(it.get("quantity"), 0), units.normalize(it.get("unit"))))
        db.commit()
        return jsonify(recipe_full(db, rid)), 201

    if request.args.get("full") == "1" or request.args.get("safe") == "1":
        ids = [r["id"] for r in db.execute("SELECT id FROM recipes ORDER BY name")]
        restriction_list = get_profile(db)["restriction_list"]
        preferite = set(favorite_ids(db))
        out = []
        for i in ids:
            rec = recipe_full(db, i)
            tags, hits = recipe_safety(db, i, restriction_list)
            rec["allergens"] = sorted(allergens.label_for(t) for t in tags)
            rec["conflicts"] = hits
            rec["favorite"] = i in preferite
            if request.args.get("safe") == "1" and hits:
                continue
            out.append(rec)
        return jsonify(out)
    cur = db.execute("SELECT * FROM recipes ORDER BY name")
    return jsonify(rows(cur))


@app.route("/api/recipes/<int:rid>", methods=["GET", "PUT", "DELETE"])
def recipe_detail(rid):
    db = get_db()
    if not one(db.execute("SELECT id FROM recipes WHERE id = ?", (rid,))):
        return bad_request("Ricetta non trovata", 404)

    if request.method == "DELETE":
        db.execute("DELETE FROM recipes WHERE id = ?", (rid,))
        # gli ingredienti che solo questa ricetta usava restano orfani altrimenti
        delete_orphan_ingredients(db)
        # se la ricetta era nel piano, i suoi ingredienti non servono piu' comprarli
        rebuild_shopping(db)
        db.commit()
        return jsonify({"ok": True})

    if request.method == "PUT":
        data = request.get_json(force=True) or {}
        attuale = one(db.execute("SELECT image, image_credit FROM recipes WHERE id = ?", (rid,)))
        # la foto si tocca solo se il campo e' presente: un salvataggio parziale
        # (es. solo gli ingredienti) non deve cancellarla
        if "image" in data:
            image = clean_image(data.get("image"))
            credito = (data.get("image_credit") or "").strip() if image else ""
        else:
            image = attuale["image"]
            credito = attuale["image_credit"]
        db.execute(
            """UPDATE recipes SET name = ?, servings = ?, time_minutes = ?, difficulty = ?,
               instructions = ?, image = ?, image_credit = ? WHERE id = ?""",
            ((data.get("name") or "").strip(), int(parse_float(data.get("servings"), 2)),
             data.get("time_minutes") or None, data.get("difficulty") or "facile",
             data.get("instructions") or "", image, credito, rid),
        )
        db.execute("DELETE FROM recipe_items WHERE recipe_id = ?", (rid,))
        for it in data.get("items") or []:
            iname = (it.get("name") or "").strip()
            if not iname:
                continue
            iid = get_or_create_ingredient(db, iname, units.normalize(it.get("unit")), it.get("category") or "Altro")
            db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)",
                       (rid, iid, parse_float(it.get("quantity"), 0), units.normalize(it.get("unit"))))
        # togliendo un ingrediente dalla ricetta puo' restare senza padrone
        delete_orphan_ingredients(db)
        # e la lista deve seguire: se la ricetta e' nel piano, le quantita'
        # cambiate valgono subito, senza rigenerare a mano
        rebuild_shopping(db)
        db.commit()
        return jsonify(recipe_full(db, rid))

    return jsonify(recipe_full(db, rid))


# ---------------------------------------------------------------- meal plan
@app.route("/api/plan", methods=["GET"])
def plan_list():
    db = get_db()
    start = request.args.get("start")
    end = request.args.get("end")
    sql = """SELECT mp.id, mp.date, mp.meal, mp.servings, r.id AS recipe_id, r.name AS recipe_name
             FROM meal_plan mp JOIN recipes r ON r.id = mp.recipe_id"""
    params = []
    if start and end:
        sql += " WHERE mp.date BETWEEN ? AND ?"
        params = [start, end]
    sql += " ORDER BY mp.date, mp.meal"
    out = rows(db.execute(sql, params))
    restriction_list = get_profile(db)["restriction_list"]
    for entry in out:
        _, hits = recipe_safety(db, entry["recipe_id"], restriction_list)
        entry["conflicts"] = hits
    return jsonify(out)


@app.route("/api/plan", methods=["POST"])
def plan_add():
    db = get_db()
    data = request.get_json(force=True) or {}
    if not data.get("date") or not data.get("meal") or not data.get("recipe_id"):
        return bad_request("date, meal e recipe_id sono obbligatori")
    if data["meal"] not in valid_meals(db):
        return bad_request("Pasto non valido")
    db.execute(
        """INSERT INTO meal_plan (date, meal, recipe_id, servings) VALUES (?, ?, ?, ?)
           ON CONFLICT(date, meal) DO UPDATE SET recipe_id = excluded.recipe_id, servings = excluded.servings""",
        (data["date"], data["meal"], int(data["recipe_id"]), int(parse_float(data.get("servings"), 2))),
    )
    # pianificare e' cio' che rende il piano una fonte di verita' per la spesa:
    # la lista si aggiorna qui, cosi' non serve ricordarsi di rigenerarla
    rebuild_shopping(db)
    db.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/plan/<int:pid>", methods=["DELETE"])
def plan_delete(pid):
    db = get_db()
    db.execute("DELETE FROM meal_plan WHERE id = ?", (pid,))
    # togliendo un pasto i suoi ingredienti non servono piu': la lista segue
    rebuild_shopping(db)
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- shopping
def pantry_available(pantry_rows, unit):
    """Giacenza di un ingrediente da mostrare accanto a una voce di spesa.

    `pantry_rows` sono le giacenze dell'ingrediente (quantità e unità). Se le unità
    sono convertibili le somma e riporta il totale nell'unità della voce. Quando la
    conversione non è possibile (es. dispensa in pezzi contro una voce in grammi)
    riporta la giacenza nella sua unità, sommando solo quelle uguali.

    Non esprime giudizi: la quantità in lista è già al netto della dispensa, quindi
    un confronto fra i due numeri sarebbe fuorviante.
    """
    if not pantry_rows:
        return None

    total = 0.0
    convertible = 0
    for row in pantry_rows:
        converted = units.convert(row["quantity"], row["unit"], unit)
        if converted is not None:
            total += converted
            convertible += 1

    if convertible:
        unit = units.normalize(unit)
    else:
        unit = units.normalize(pantry_rows[0]["unit"])
        total = sum(r["quantity"] for r in pantry_rows if units.normalize(r["unit"]) == unit)

    return {"quantity": units.format_quantity(total), "unit": unit}


@app.route("/api/shopping", methods=["GET", "POST"])
def shopping():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return bad_request("Il nome è obbligatorio")
        unit = units.normalize(data.get("unit"))
        iid = get_or_create_ingredient(db, name, unit, data.get("category") or "Altro")
        db.execute(
            "INSERT INTO shopping_items (name, quantity, unit, category, ingredient_id) VALUES (?, ?, ?, ?, ?)",
            (name, parse_float(data.get("quantity"), 1), unit, data.get("category") or "Altro", iid),
        )
        db.commit()
        return jsonify({"ok": True}), 201

    items = rows(db.execute("SELECT * FROM shopping_items ORDER BY checked, category, name"))

    # giacenze di tutti gli ingredienti in lista, in una sola query
    ids = sorted({i["ingredient_id"] for i in items if i["ingredient_id"]})
    if ids:
        marks = ",".join("?" * len(ids))
        stock = {}
        for p in db.execute(
            f"SELECT ingredient_id, quantity, unit FROM pantry WHERE ingredient_id IN ({marks})", ids
        ):
            stock.setdefault(p["ingredient_id"], []).append(p)
    else:
        stock = {}

    for item in items:
        item["pantry"] = pantry_available(stock.get(item["ingredient_id"], []), item["unit"])
        item["days"] = _day_breakdown(db, item)
        item["perishable"] = item["category"] in PERISHABLE_CATEGORIES
    return jsonify(items)


# categorie che deperiscono: comprarle in anticipo le fa scadere o perdere qualità
PERISHABLE_CATEGORIES = {"Frutta e Verdura", "Carne e Pesce", "Latticini"}


def _need_by_day(db, ingredient_id):
    """Fabbisogno di un ingrediente in ciascun giorno del piano, in unità base.

    Si legge dal piano invece di memorizzarlo: il piano è già la fonte di verità
    di quando serve un ingrediente, e una copia salvata si disallineerebbe appena
    si modifica il piano.
    """
    needs = {}
    dim = preferred = None
    filtro, pasti = meal_clause(db)
    for r in db.execute(
        f"""SELECT mp.date, mp.servings AS plan_servings, r.servings AS base_servings,
                  ri.quantity, ri.unit
           FROM meal_plan mp
           JOIN recipes r ON r.id = mp.recipe_id
           JOIN recipe_items ri ON ri.recipe_id = r.id
           WHERE ri.ingredient_id = ? AND {filtro}""",
        (ingredient_id, *pasti),
    ):
        fattore = r["plan_servings"] / (r["base_servings"] or 1)
        qty, _ = units.to_base(r["quantity"] * fattore, r["unit"])
        needs[r["date"]] = needs.get(r["date"], 0.0) + qty
        dim = dim or units.dimension(r["unit"])
        preferred = preferred or r["unit"]
    return needs, dim, preferred


def _day_breakdown(db, item):
    """Quando serve la voce, ripartendo la quantità in lista sui giorni del piano.

    La quantità mostrata in lista resta quella di sempre: qui si dice solo come si
    distribuisce. Si scala al valore effettivo della voce, così la somma dei giorni
    coincide con la vista completa anche quando la lista è stata corretta a mano.
    """
    if not item["ingredient_id"]:
        return []
    needs, dim, preferred = _need_by_day(db, item["ingredient_id"])
    if not needs:
        return []
    check_unit = units.base_unit(dim) if dim else preferred
    fabbisogno = sum(needs.values())
    # la dispensa copre i giorni più vicini, esattamente come in generazione
    have = fabbisogno - net_quantity(db, item["ingredient_id"], check_unit, fabbisogno)
    net = _distribute(needs, have)

    giorni = {}
    for giorno, q in net.items():
        q_item = units.convert(q, check_unit, item["unit"])
        if q_item is None:
            q_item = q
        giorni[giorno] = q_item
    totale = sum(giorni.values())
    if totale <= 0:
        # voce che la dispensa coprirebbe del tutto: se è in lista per accumulo o
        # per modifica manuale va comunque attribuita a un giorno, non nascosta
        giorni = {min(needs): item["quantity"]} if item["quantity"] > 0 else {}
        totale = sum(giorni.values())
    if totale <= 0:
        return []
    scala = item["quantity"] / totale

    return [{"date": g, "quantity": units.format_quantity(giorni[g] * scala),
             "unit": item["unit"]} for g in sorted(giorni)]


def _distribute(by_day, coperto):
    """Ripartisce il fabbisogno sui giorni, togliendo prima la dispensa.

    `coperto` e' quanto si ha gia' in casa: viene sottratto a partire dal giorno
    piu' vicino, perche' quello che si ha in dispensa serve naturalmente ai primi
    pasti, non a quelli della settimana dopo. La somma dei giorni restituiti e'
    esattamente il fabbisogno meno la dispensa, cioe' il totale che compare nella
    lista: se i due numeri non coincidessero, la vista per giorno contraddirebbe
    la vista completa. Con `coperto` negativo (in lista c'e' piu' del fabbisogno,
    perche' la generazione si accumula) l'eccedenza va al primo giorno.
    """
    restante = coperto
    out = {}
    for giorno in sorted(by_day):
        q = by_day[giorno]
        if restante >= q:
            restante -= q  # giorno interamente coperto dalla dispensa
            continue
        out[giorno] = q - restante
        restante = 0.0
    return out


@app.route("/api/shopping/<int:sid>", methods=["PATCH", "DELETE"])
def shopping_modify(sid):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM shopping_items WHERE id = ?", (sid,))
        delete_orphan_ingredients(db)
        db.commit()
        return jsonify({"ok": True})
    data = request.get_json(force=True) or {}
    if "checked" in data:
        db.execute("UPDATE shopping_items SET checked = ? WHERE id = ?", (1 if data["checked"] else 0, sid))
    if "quantity" in data:
        db.execute("UPDATE shopping_items SET quantity = ? WHERE id = ?", (parse_float(data["quantity"], 1), sid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/shopping/clear-checked", methods=["POST"])
def shopping_clear_checked():
    db = get_db()
    db.execute("DELETE FROM shopping_items WHERE checked = 1")
    delete_orphan_ingredients(db)
    db.commit()
    return jsonify({"ok": True})


def meal_clause(db, alias="mp"):
    """Filtro SQL dei soli pasti gestiti, con i valori da passare.

    Riducendo i pasti al giorno le righe dei pasti non più gestiti restano nel
    piano: senza questo filtro continuerebbero a contare nella spesa pur non
    essendo più visibili né modificabili, e i numeri non tornerebbero.
    """
    pasti = valid_meals(db)
    posti = ", ".join("?" for _ in pasti)
    return f"{alias}.meal IN ({posti})", pasti


def net_quantity(db, ingredient_id, unit, needed):
    """Quantità da comprare: fabbisogno meno dispensa, convertendo le unità compatibili."""
    have = 0.0
    for p in db.execute("SELECT quantity, unit FROM pantry WHERE ingredient_id = ?", (ingredient_id,)):
        converted = units.convert(p["quantity"], p["unit"], unit)
        if converted is not None:
            have += converted
    return max(needed - have, 0.0)


def rebuild_shopping(db):
    """Ricostruisce la parte generata della lista della spesa dal piano intero.

    La lista e' una fotografia del piano, non un registro di tutte le generazioni
    passate: si azzera la parte generata e si rifa' da capo, cosi' una ricetta
    tolta dal piano porta via i suoi ingredienti e rigenerare non raddoppia le
    quantita'. Le voci scritte a mano (`generated = 0`) non si toccano mai.

    Si guarda il piano intero e non un intervallo di date: i giorni in cui serve
    una voce (`_day_breakdown`) si calcolano gia' su tutto il piano, e limitare le
    quantita' a una settimana le faceva contraddire dai giorni.

    Restituisce (voci_aggiunte, voci_già_in_lista_a_mano).
    """
    filtro, pasti = meal_clause(db)
    plan = rows(db.execute(
        f"""SELECT mp.recipe_id, mp.servings AS plan_servings
           FROM meal_plan mp JOIN recipes r ON r.id = mp.recipe_id
           WHERE {filtro}""",
        pasti,
    ))

    # Ricette coinvolte, con le porzioni della ricetta base per scalare le quantità
    recipe_base = {r["id"]: (r["servings"] or 1) for r in db.execute(
        f"""SELECT DISTINCT r.id, r.servings FROM recipes r
           JOIN meal_plan mp ON mp.recipe_id = r.id
           WHERE {filtro}""",
        pasti,
    )}

    # Il fabbisogno si accumula nell'unità base della dimensione: così 'g' e 'kg'
    # dello stesso ingrediente confluiscono in un'unica voce.
    needed = {}
    for p in plan:
        factor = p["plan_servings"] / recipe_base[p["recipe_id"]]
        for it in db.execute(
            """SELECT ri.quantity, ri.unit, i.id AS ingredient_id, i.name, i.category
               FROM recipe_items ri JOIN ingredients i ON i.id = ri.ingredient_id
               WHERE ri.recipe_id = ?""",
            (p["recipe_id"],),
        ):
            key = (it["ingredient_id"], units.group_key(it["unit"]))
            entry = needed.setdefault(key, {
                "name": it["name"], "category": it["category"],
                "dim": units.dimension(it["unit"]), "preferred": it["unit"], "base_qty": 0.0,
            })
            qty, _base = units.to_base(it["quantity"] * factor, it["unit"])
            entry["base_qty"] += qty

    db.execute("DELETE FROM shopping_items WHERE generated = 1")

    added = 0
    marcate = 0
    for (iid, _group), entry in needed.items():
        dim = entry["dim"]
        base_qty = entry["base_qty"]
        # si confronta con la dispensa nell'unità base: la conversione rende
        # sommabili anche unità diverse dello stesso ingrediente
        check_unit = units.base_unit(dim) if dim else entry["preferred"]
        to_buy_base = net_quantity(db, iid, check_unit, base_qty)
        if to_buy_base <= 0:
            continue
        buy_unit = units.display_unit(to_buy_base, dim, entry["preferred"])
        to_buy = units.convert(to_buy_base, check_unit, buy_unit)
        if to_buy is None:
            to_buy = to_buy_base
        # una voce scritta a mano per lo stesso ingrediente e' di chi l'ha
        # scritta: non si duplica ne' si fonde, si lascia com'e'
        manuale = one(db.execute(
            "SELECT id FROM shopping_items WHERE ingredient_id = ? AND checked = 0",
            (iid,)))
        if manuale:
            marcate += 1
            continue
        db.execute(
            "INSERT INTO shopping_items (name, quantity, unit, category, ingredient_id, generated) VALUES (?, ?, ?, ?, ?, 1)",
            (entry["name"], units.format_quantity(to_buy), buy_unit, entry["category"], iid),
        )
        added += 1
    return added, marcate


@app.route("/api/shopping/generate", methods=["POST"])
def shopping_generate():
    """Rigenera la lista dal piano. Il piano la rigenera da solo a ogni modifica:
    l'endpoint resta per poterla forzare a mano."""
    db = get_db()
    if not one(db.execute("SELECT id FROM meal_plan LIMIT 1")):
        return bad_request("Nessun pasto pianificato", 404)
    added, marcate = rebuild_shopping(db)
    db.commit()
    return jsonify({"added": added, "already_listed": marcate})


# ---------------------------------------------------------------- progetti
def project_row(r):
    return {**dict(r), "done": bool(r["done"])}


def project_payload(data):
    """Normalizza e valida i campi di un progetto. Restituisce (campi, errore)."""
    title = (data.get("title") or "").strip()
    if not title:
        return None, "Il titolo è obbligatorio"
    priority = int(parse_float(data.get("priority"), 3))
    if not 1 <= priority <= 5:
        return None, "La priorità va da 1 a 5"
    start = (data.get("start_date") or "").strip()
    end = (data.get("end_date") or "").strip()
    if start and end and end < start:
        return None, "La data di fine non può precedere quella di inizio"
    return {
        "title": title,
        "description": (data.get("description") or "").strip(),
        "start_date": start,
        "end_date": end,
        "priority": priority,
    }, None


@app.route("/api/projects", methods=["GET", "POST"])
def projects():
    db = get_db()
    if request.method == "POST":
        campi, errore = project_payload(request.get_json(force=True) or {})
        if errore:
            return bad_request(errore)
        cur = db.execute(
            """INSERT INTO projects (title, description, start_date, end_date, priority)
               VALUES (?, ?, ?, ?, ?)""",
            (campi["title"], campi["description"], campi["start_date"],
             campi["end_date"], campi["priority"]),
        )
        db.commit()
        return jsonify(project_row(one(db.execute(
            "SELECT * FROM projects WHERE id = ?", (cur.lastrowid,))))), 201

    # aperti prima, poi per priorita' decrescente: l'ordine e' il senso della lista
    return jsonify([project_row(r) for r in db.execute(
        "SELECT * FROM projects ORDER BY done, priority DESC, end_date = '', end_date, id")])


@app.route("/api/projects/<int:pid>", methods=["PUT", "DELETE"])
def project_detail(pid):
    db = get_db()
    if not one(db.execute("SELECT id FROM projects WHERE id = ?", (pid,))):
        return bad_request("Progetto non trovato", 404)

    if request.method == "DELETE":
        db.execute("DELETE FROM projects WHERE id = ?", (pid,))
        db.commit()
        return jsonify({"ok": True})

    data = request.get_json(force=True) or {}
    attuale = one(db.execute("SELECT * FROM projects WHERE id = ?", (pid,)))
    # i campi si toccano solo se presenti: spuntare un progetto non deve
    # richiedere di rimandare tutto il resto
    if "done" in data:
        db.execute("UPDATE projects SET done = ? WHERE id = ?",
                   (1 if data["done"] else 0, pid))
    if set(data) - {"done"}:
        campi, errore = project_payload({**dict(attuale), **data})
        if errore:
            return bad_request(errore)
        db.execute(
            """UPDATE projects SET title = ?, description = ?, start_date = ?,
               end_date = ?, priority = ? WHERE id = ?""",
            (campi["title"], campi["description"], campi["start_date"],
             campi["end_date"], campi["priority"], pid),
        )
    db.commit()
    return jsonify(project_row(one(db.execute("SELECT * FROM projects WHERE id = ?", (pid,)))))


# ---------------------------------------------------------------- magazzino
@app.route("/api/storage", methods=["GET", "POST"])
def storage():
    db = get_db()
    if request.method == "POST":
        campi, errore = storage_payload(request.get_json(force=True) or {})
        if errore:
            return bad_request(errore)
        cur = db.execute(
            """INSERT INTO storage (name, category, place, quantity, unit, min_quantity, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (campi["name"], campi["category"], campi["place"], campi["quantity"],
             campi["unit"], campi["min_quantity"], campi["notes"]),
        )
        db.commit()
        return jsonify(storage_row(one(db.execute(
            "SELECT * FROM storage WHERE id = ?", (cur.lastrowid,))))), 201

    # prima quello che sta finendo, poi per categoria: e' l'ordine in cui si
    # guarda un magazzino, cioe' cosa manca
    return jsonify([storage_row(r) for r in db.execute(
        """SELECT * FROM storage
           ORDER BY (min_quantity > 0 AND quantity <= min_quantity) DESC, category, name""")])


def storage_payload(data, attuale=None):
    """Normalizza e valida i campi di una voce di magazzino. (campi, errore)."""
    base = dict(attuale) if attuale else {}
    name = (data["name"] if "name" in data else base.get("name", ""))
    name = (name or "").strip()
    if not name:
        return None, "Il nome è obbligatorio"
    return {
        "name": name,
        "category": (data.get("category") or base.get("category") or magazzino.CATEGORIA_DEFAULT).strip(),
        "place": (data.get("place") or base.get("place") or magazzino.LUOGO_DEFAULT).strip(),
        "quantity": parse_float(data.get("quantity", base.get("quantity", 0)), 0),
        "unit": (data.get("unit") or base.get("unit") or "pz").strip() or "pz",
        "min_quantity": parse_float(data.get("min_quantity", base.get("min_quantity", 0)), 0),
        "notes": (data.get("notes", base.get("notes", "")) or "").strip(),
    }, None


def storage_row(r):
    d = dict(r)
    # "sta finendo" e' una proprieta' derivata dalla giacenza e dalla soglia:
    # calcolarla qui evita che il client rifaccia il confronto e lo sbagli
    d["low"] = bool(d["min_quantity"] > 0 and d["quantity"] <= d["min_quantity"])
    return d


@app.route("/api/storage/<int:sid>", methods=["GET", "PUT", "PATCH", "DELETE"])
def storage_detail(sid):
    db = get_db()
    attuale = one(db.execute("SELECT * FROM storage WHERE id = ?", (sid,)))
    if not attuale:
        return bad_request("Voce non trovata", 404)

    if request.method == "DELETE":
        db.execute("DELETE FROM storage WHERE id = ?", (sid,))
        db.commit()
        return jsonify({"ok": True})

    data = request.get_json(force=True) or {}
    # PATCH e' per ritoccare solo la giacenza (il campo che si cambia piu'
    # spesso); PUT rimanda la voce intera
    if request.method == "PATCH":
        campi, errore = storage_payload(data, attuale)
    else:
        campi, errore = storage_payload({**dict(attuale), **data})
    if errore:
        return bad_request(errore)
    db.execute(
        """UPDATE storage SET name = ?, category = ?, place = ?, quantity = ?,
           unit = ?, min_quantity = ?, notes = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (campi["name"], campi["category"], campi["place"], campi["quantity"],
         campi["unit"], campi["min_quantity"], campi["notes"], sid),
    )
    db.commit()
    return jsonify(storage_row(one(db.execute("SELECT * FROM storage WHERE id = ?", (sid,)))))


@app.route("/api/magazzino/meta", methods=["GET"])
def magazzino_meta():
    return jsonify(magazzino.meta())


# ---------------------------------------------------------------- voce
@app.route("/api/voice", methods=["POST"])
def voice_command():
    """Comprende una frase dettata ed esegue il comando.

    Il riconoscimento vocale avviene nel browser (Web Speech API), che consegna
    solo testo: la comprensione resta qui, dove si può verificare con dei test
    senza microfono. La risposta contiene anche un messaggio di conferma in
    italiano, così il client non deve ricostruire da capo cosa è successo.
    """
    db = get_db()
    data = request.get_json(force=True) or {}
    cmd = voice.parse(data.get("text"))

    if cmd["intent"] == "pantry_add":
        unit = units.normalize(cmd["unit"] or "pz")
        qty = parse_float(cmd["quantity"], 1) or 1
        iid = get_or_create_ingredient(db, cmd["name"], unit)
        pantry_add_row(db, iid, cmd["name"], qty, unit)
        db.commit()
        return jsonify({**cmd, "message": f"Fatto. {cmd['name'].capitalize()} in dispensa, {units.format_quantity(qty)} {unit}.",
                        "reload": ["pantry", "shopping"]})

    if cmd["intent"] == "shopping_add":
        unit = units.normalize(cmd["unit"] or "pz")
        qty = parse_float(cmd["quantity"], 1) or 1
        row = one(db.execute("SELECT * FROM ingredients WHERE name = ? COLLATE NOCASE", (cmd["name"],)))
        category = row["category"] if row else "Altro"
        iid = get_or_create_ingredient(db, cmd["name"], unit, category)
        add_to_shopping(db, iid, cmd["name"], qty, unit, category)
        db.commit()
        return jsonify({**cmd, "message": f"Fatto. {cmd['name'].capitalize()} in lista, {units.format_quantity(qty)} {unit}.",
                        "reload": ["shopping"]})

    if cmd["intent"] == "storage_add":
        unit = units.normalize(cmd["unit"] or "pz")
        qty = parse_float(cmd["quantity"], 1) or 1
        campi, _ = storage_payload({
            "name": cmd["name"], "quantity": qty, "unit": unit,
            "category": cmd.get("category"), "place": cmd.get("place"),
        })
        # il magazzino non ha un vincolo di unicita' sul nome (due scatole di viti
        # in posti diversi sono due voci): si accoda solo se nome e luogo
        # coincidono, altrimenti si crea una voce nuova
        esistente = one(db.execute(
            "SELECT * FROM storage WHERE name = ? COLLATE NOCASE AND unit = ? AND place = ?",
            (campi["name"], campi["unit"], campi["place"])))
        if esistente:
            db.execute("UPDATE storage SET quantity = quantity + ?, updated_at = datetime('now') WHERE id = ?",
                       (campi["quantity"], esistente["id"]))
        else:
            db.execute(
                """INSERT INTO storage (name, category, place, quantity, unit, min_quantity, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (campi["name"], campi["category"], campi["place"], campi["quantity"],
                 campi["unit"], campi["min_quantity"], campi["notes"]))
        db.commit()
        dove = _preposizione_luogo(campi["place"])
        return jsonify({**cmd, "storage_name": campi["name"],
                        "message": f"Fatto. {campi['name'].capitalize()} in magazzino{dove}, {units.format_quantity(qty)} {unit}.",
                        "reload": ["magazzino"]})

    if cmd["intent"] == "term_add":
        current = get_profile(db)["restriction_list"]
        aggiunti = [t for t in cmd["terms"] if t.lower() not in {c.lower() for c in current}]
        profile = save_profile(db, {"restrictions": current + aggiunti})
        if not aggiunti:
            return jsonify({**cmd, "message": "Già presente nel profilo.",
                            "reload": []})
        return jsonify({**cmd, "message": "Annotato. " + ", ".join(aggiunti) + " nel profilo.",
                        "restriction_list": profile["restriction_list"],
                        "reload": ["profile"]})

    if cmd["intent"] == "recipe_add":
        # Non si crea una ricetta vuota: una ricetta senza ingredienti e senza
        # procedimento non serve a nessuno e resterebbe li' a sporcare l'elenco.
        # Si apre invece il modulo gia' compilato col nome, cosi' la voce fa il
        # lavoro noioso (trovare la scheda, aprire il modulo, scrivere il nome) e
        # l'utente aggiunge ingredienti e preparazione.
        if not cmd["name"]:
            return jsonify({**cmd, "open_recipe_form": True,
                            "message": "Apro il modulo per la nuova ricetta."})
        return jsonify({**cmd, "open_recipe_form": True,
                        "message": f"Nuova ricetta: {cmd['name']}. Completa ingredienti e preparazione."})

    if cmd["intent"] == "recipe_search":
        return jsonify({**cmd, "message": f"Cerco «{cmd['query']}».", "query": cmd["query"]})

    return jsonify({**cmd, "message": "Non ho capito. Riprova."}), 422


@app.route("/api/voce/config")
def voce_config():
    """Se la voce neurale e' disponibile, e con quali voci.

    Non espone la chiave ne' l'area: dice solo se la sintesi cloud e' pronta e
    l'elenco delle voci fra cui scegliere. Il client decide in base a questo se
    usare il cloud o ripiegare sulla voce del browser.
    """
    return jsonify({
        "cloud": voce_cloud.configurato(),
        "voci": voce_cloud.elenco_voci(),
        "predefinita": voce_cloud.VOCE_PREDEFINITA,
        "max_caratteri": voce_cloud.MAX_CARATTERI,
    })


@app.route("/api/voce/parla", methods=["POST"])
def voce_parla():
    """Restituisce l'audio MP3 di una frase, sintetizzato dalla voce neurale.

    La chiave del servizio resta sul server: il browser riceve solo l'audio. E'
    il motivo per cui questa rotta esiste invece di chiamare Azure dal client.

    L'audio si scarica e si consegna, senza salvarlo: una cache di frasi di casa
    su disco sarebbe un dato in piu' da custodire per un guadagno minimo.

    Va tenuto presente il costo: ogni frase non ripetuta e' una chiamata fatturata.
    Per questo il client **non** richiama il cloud per le frasi gia' sentite, e
    c'e' un limite di lunghezza.
    """
    if not voce_cloud.configurato():
        # 503 e non 500: non e' un guasto, e' una funzione non attivata. Il client
        # lo usa per ripiegare sulla voce del browser senza mostrare un errore.
        return jsonify({"error": "Sintesi vocale cloud non configurata"}), 503

    data = request.get_json(force=True) or {}
    testo = (data.get("text") or "").strip()
    voce = data.get("voice") or voce_cloud.VOCE_PREDEFINITA
    stile = data.get("style") or None

    try:
        audio = voce_cloud.sintetizza(
            testo, voce,
            rate=data.get("rate", 1.0),
            pitch=data.get("pitch", 0.0),
            stile=stile,
        )
    except voce_cloud.ErroreVoce as e:
        # il messaggio e' gia' pensato per l'utente: dice cosa non va senza
        # riportare dettagli della risorsa Azure
        return jsonify({"error": str(e)}), e.stato

    risposta = app.response_class(audio, mimetype="audio/mpeg")
    # la voce di conferma di un comando non cambia: si puo' riusare per un po'
    risposta.headers["Cache-Control"] = "private, max-age=300"
    return risposta


def _preposizione_luogo(luogo):
    """Preposizione giusta per il luogo, così la conferma si può anche ascoltare.

    "nel cantina" si sente subito sbagliato, e la conferma viene letta ad alta
    voce: la preposizione va scelta, non concatenata.
    """
    if not luogo:
        return ""
    articolo = {
        "Ripostiglio": "nel",       # nel ripostiglio, non "in ripostiglio"
        "Balcone": "sul", "Terrazzo": "sul",
    }
    return f" {articolo.get(luogo, 'in')} {luogo.lower()}"


def pantry_add_row(db, iid, name, qty, unit):
    """Accoda alla riga esistente se l'unità è compatibile, altrimenti ne crea una."""
    existing = one(db.execute(
        "SELECT * FROM pantry WHERE ingredient_id = ? AND unit = ?", (iid, unit)))
    if not existing:
        for cand in db.execute("SELECT * FROM pantry WHERE ingredient_id = ?", (iid,)):
            converted = units.convert(qty, unit, cand["unit"])
            if converted is not None:
                db.execute("UPDATE pantry SET quantity = quantity + ?, updated_at = datetime('now') WHERE id = ?",
                           (units.format_quantity(converted), cand["id"]))
                return
    if existing:
        db.execute("UPDATE pantry SET quantity = quantity + ?, updated_at = datetime('now') WHERE id = ?",
                   (units.format_quantity(qty), existing["id"]))
    else:
        db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, ?, ?)",
                   (iid, qty, unit))


def add_to_shopping(db, iid, name, qty, unit, category):
    """Fonde con una voce aperta dello stesso ingrediente, come la generazione."""
    row = one(db.execute(
        "SELECT * FROM shopping_items WHERE ingredient_id = ? AND checked = 0 AND unit = ?",
        (iid, unit)))
    if not row:
        for cand in db.execute(
            "SELECT * FROM shopping_items WHERE ingredient_id = ? AND checked = 0", (iid,)
        ):
            converted = units.convert(qty, unit, cand["unit"])
            if converted is not None:
                db.execute("UPDATE shopping_items SET quantity = ? WHERE id = ?",
                           (units.format_quantity(cand["quantity"] + converted), cand["id"]))
                return
    if row:
        db.execute("UPDATE shopping_items SET quantity = ? WHERE id = ?",
                   (units.format_quantity(row["quantity"] + qty), row["id"]))
    else:
        db.execute(
            "INSERT INTO shopping_items (name, quantity, unit, category, ingredient_id) VALUES (?, ?, ?, ?, ?)",
            (name, qty, unit, category, iid))


# ------------------------------------------------------------------ igiene
# Le attivita' di pulizia e quando vanno rifatte. Il catalogo sta in `chores`,
# la cronologia in `chore_log`; le scadenze si calcolano a ogni lettura da
# `igiene.scadenza`, non si salvano.

def _oggi(db):
    """La data di oggi, in un unico posto.

    Si puo' forzare con ?date= (aaaa-mm-gg): serve al calendario per mostrare un
    giorno scelto e ai test per non dipendere dalla data reale.
    """
    richiesta = (request.args.get("date") or "").strip()
    if richiesta:
        try:
            return datetime.date.fromisoformat(richiesta).isoformat()
        except ValueError:
            pass
    return datetime.date.today().isoformat()


def _ultime(db):
    """L'ultima volta che ogni attivita' e' stata fatta: {chore_id: 'aaaa-mm-gg'}."""
    cur = db.execute("SELECT chore_id, MAX(date) AS ultima FROM chore_log GROUP BY chore_id")
    return {r["chore_id"]: r["ultima"] for r in cur}


def _chore_o_404(db, cid):
    row = one(db.execute("SELECT * FROM chores WHERE id = ?", (cid,)))
    if row is None:
        return None, bad_request("Attività non trovata", 404)
    return row, None


@app.route("/api/chores/meta")
def chores_meta():
    """Le scelte fisse della sezione: frequenze, ambienti, mesi, giorni."""
    db = get_db()
    return jsonify({
        "frequencies": igiene.FREQUENZE,
        "areas": igiene.AMBIENTI,
        "days": [{"key": i, "label": g} for i, g in enumerate(igiene.GIORNI_SETTIMANA)],
        "months": igiene.mesi(),
        "chore_day": get_profile(db).get("chore_day") or 0,
    })


@app.route("/api/chores", methods=["GET"])
def chores_list():
    """Il catalogo con lo stato di scadenza, e cosa c'e' da fare oggi."""
    db = get_db()
    oggi = _oggi(db)
    ultime = _ultime(db)
    attivita = rows(db.execute("SELECT * FROM chores ORDER BY frequency, area, name"))

    for voce in attivita:
        voce.update(igiene.scadenza(voce["frequency"], ultime.get(voce["id"]), oggi, voce["month"]))

    giorno = get_profile(db).get("chore_day") or 0
    piano = igiene.piano(attivita, ultime, oggi, giorno)
    return jsonify({"oggi": oggi, "attivita": attivita, "piano": piano,
                    "attive": sum(1 for v in attivita if v["active"])})


@app.route("/api/chores", methods=["POST"])
def chores_add():
    db = get_db()
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return bad_request("Il nome è obbligatorio")
    freq = data.get("frequency") or "settimanale"
    if freq not in igiene.CADENZE and freq != "stagionale":
        return bad_request("Frequenza non valida")
    month = data.get("month")
    if freq == "stagionale":
        if not isinstance(month, int) or not 1 <= month <= 12:
            return bad_request("Un'attività annuale richiede un mese da 1 a 12")
    else:
        month = None
    try:
        cur = db.execute(
            """INSERT INTO chores (name, area, frequency, minutes, month)
               VALUES (?, ?, ?, ?, ?)""",
            (name, data.get("area") or "Tutta la casa", freq,
             max(0, int(data.get("minutes") or 15)), month))
    except sqlite3.IntegrityError:
        return bad_request("Esiste già un'attività con questo nome")
    db.commit()
    return jsonify(one(db.execute("SELECT * FROM chores WHERE id = ?", (cur.lastrowid,)))), 201


@app.route("/api/chores/<int:cid>", methods=["PUT", "DELETE"])
def chores_modify(cid):
    db = get_db()
    row, errore = _chore_o_404(db, cid)
    if errore:
        return errore
    if request.method == "DELETE":
        db.execute("DELETE FROM chores WHERE id = ?", (cid,))
        db.commit()
        return jsonify({"ok": True})

    data = request.get_json(force=True) or {}
    campi = {}
    if "name" in data:
        nome = (data.get("name") or "").strip()
        if not nome:
            return bad_request("Il nome è obbligatorio")
        campi["name"] = nome
    if "area" in data:
        campi["area"] = data["area"] or "Tutta la casa"
    if "minutes" in data:
        try:
            campi["minutes"] = max(0, int(data["minutes"]))
        except (TypeError, ValueError):
            return bad_request("Minuti non validi")
    if "active" in data:
        campi["active"] = 1 if data["active"] else 0
    if "frequency" in data:
        if data["frequency"] not in igiene.CADENZE and data["frequency"] != "stagionale":
            return bad_request("Frequenza non valida")
        campi["frequency"] = data["frequency"]
    # il mese segue la frequenza: si azzera quando l'attivita' non e' annuale,
    # altrimenti resterebbe un mese su una voce che non lo usa
    freq_finale = campi.get("frequency", row["frequency"])
    if freq_finale == "stagionale":
        mese = data.get("month", row["month"])
        if not isinstance(mese, int) or not 1 <= mese <= 12:
            return bad_request("Un'attività annuale richiede un mese da 1 a 12")
        campi["month"] = mese
    else:
        campi["month"] = None

    try:
        assignments = ", ".join(f"{k} = ?" for k in campi)
        db.execute(f"UPDATE chores SET {assignments} WHERE id = ?", [*campi.values(), cid])
    except sqlite3.IntegrityError:
        return bad_request("Esiste già un'attività con questo nome")
    db.commit()
    return jsonify(one(db.execute("SELECT * FROM chores WHERE id = ?", (cid,))))


@app.route("/api/chores/<int:cid>/done", methods=["POST", "DELETE"])
def chores_done(cid):
    """Segna un'attivita' come fatta oggi, o annulla l'ultima volta.

    I minuti sono il tempo impiegato davvero, se misurato: 0 significa "fatto,
    ma non cronometrato" e non va confuso con un'attivita' da zero minuti.
    """
    db = get_db()
    _row, errore = _chore_o_404(db, cid)
    if errore:
        return errore

    if request.method == "DELETE":
        ultima = one(db.execute(
            "SELECT * FROM chore_log WHERE chore_id = ? ORDER BY date DESC, id DESC LIMIT 1", (cid,)))
        if ultima is None:
            return bad_request("Nessun completamento da annullare", 404)
        db.execute("DELETE FROM chore_log WHERE id = ?", (ultima["id"],))
        db.commit()
        return jsonify({"ok": True, "annullata": ultima["date"]})

    data = request.get_json(silent=True) or {}
    try:
        minuti = max(0, int(data.get("minutes") or 0))
    except (TypeError, ValueError):
        return bad_request("Minuti non validi")
    giorno = (data.get("date") or _oggi(db))
    try:
        giorno = datetime.date.fromisoformat(str(giorno)[:10]).isoformat()
    except ValueError:
        return bad_request("Data non valida")

    db.execute("INSERT INTO chore_log (chore_id, date, minutes) VALUES (?, ?, ?)",
               (cid, giorno, minuti))
    db.commit()
    return jsonify({"ok": True, "date": giorno, "minutes": minuti})


@app.route("/api/chores/history")
def chores_history():
    """Le ultime pulizie fatte, con il tempo impiegato quando e' stato misurato."""
    db = get_db()
    limite = request.args.get("limit", type=int) or 30
    cur = db.execute(
        """SELECT l.id, l.chore_id, l.date, l.minutes, c.name, c.area, c.frequency
           FROM chore_log l JOIN chores c ON c.id = l.chore_id
           ORDER BY l.date DESC, l.id DESC LIMIT ?""",
        (max(1, min(limite, 200)),))
    return jsonify(rows(cur))


@app.route("/api/chores/summary")
def chores_summary():
    """Quanto tempo e' andato nelle pulizie: oggi, questa settimana, questo mese.

    Si contano solo i completamenti cronometrati: le attivita' spuntate senza
    timer non hanno un tempo, e contarle come zero abbasserebbe la media.
    """
    db = get_db()
    oggi = datetime.date.fromisoformat(_oggi(db))
    lunedi = oggi - datetime.timedelta(days=oggi.weekday())
    inizio_mese = oggi.replace(day=1)

    def totale(da):
        row = one(db.execute(
            "SELECT COUNT(*) AS volte, COALESCE(SUM(minutes), 0) AS minuti FROM chore_log WHERE date >= ?",
            (da.isoformat(),)))
        return {"volte": row["volte"], "minuti": row["minuti"]}

    return jsonify({
        "oggi": totale(oggi),
        "settimana": {**totale(lunedi), "dal": lunedi.isoformat()},
        "mese": {**totale(inizio_mese), "dal": inizio_mese.isoformat()},
    })


# ---------------------------------------------------------------------- faq
# Informazioni utili da consultare: Wi-Fi, indirizzi, contatti, codici. Le
# categorie stanno in `faq.py`, le voci nella tabella `faq`.
#
# La ricerca e' lato client, come per le ricette: l'elenco e' piccolo e filtrare
# in locale e' immediato, senza una richiesta a ogni lettera digitata.


def _faq_o_404(db, fid):
    row = one(db.execute("SELECT * FROM faq WHERE id = ?", (fid,)))
    if row is None:
        return None, bad_request("Voce non trovata", 404)
    return row, None


def _faq_campi(data, row=None):
    """I campi validati per un inserimento o una modifica.

    Restituisce (campi, errore). In modifica si toccano solo i campi presenti,
    come per il profilo: un salvataggio parziale non deve azzerare il resto.
    """
    campi = {}
    if row is None or "question" in data:
        domanda = (data.get("question") or "").strip()
        if not domanda:
            return None, bad_request("Il titolo è obbligatorio")
        campi["question"] = domanda
    if row is None or "answer" in data:
        campi["answer"] = (data.get("answer") or "").strip()
    if "category" in data:
        campi["category"] = faq.categoria_valida(data.get("category"))
    for chiave in ("secret", "pinned"):
        if chiave in data:
            campi[chiave] = 1 if data[chiave] else 0
    return campi, None


@app.route("/api/faq/meta")
def faq_meta():
    """Le scelte fisse della sezione: le categorie, con quante voci hanno."""
    db = get_db()
    conteggi = {r["category"]: r["n"] for r in db.execute(
        "SELECT category, COUNT(*) AS n FROM faq GROUP BY category")}
    return jsonify({
        "categories": [{**c, "count": conteggi.get(c["key"], 0)} for c in faq.categorie()],
        "default_category": faq.CATEGORIA_DEFAULT,
    })


@app.route("/api/faq", methods=["GET"])
def faq_list():
    """Tutte le voci, ordinate: in evidenza, poi per categoria, poi per titolo."""
    db = get_db()
    voci = rows(db.execute("SELECT * FROM faq"))
    for v in voci:
        # l'etichetta della categoria arriva dal server: il frontend non deve
        # avere una seconda copia della mappa, che si disallineerebbe
        v["category_label"] = faq.etichetta(v["category"])
    return jsonify({
        "voci": faq.ordina(voci),
        "totale": len(voci),
        "riservate": sum(1 for v in voci if v["secret"]),
    })


@app.route("/api/faq", methods=["POST"])
def faq_add():
    db = get_db()
    data = request.get_json(force=True) or {}
    campi, errore = _faq_campi(data)
    if errore:
        return errore
    cur = db.execute(
        """INSERT INTO faq (category, question, answer, secret, pinned)
           VALUES (?, ?, ?, ?, ?)""",
        (campi.get("category", faq.CATEGORIA_DEFAULT), campi["question"],
         campi.get("answer", ""), campi.get("secret", 0), campi.get("pinned", 0)))
    db.commit()
    return jsonify(one(db.execute("SELECT * FROM faq WHERE id = ?", (cur.lastrowid,)))), 201


@app.route("/api/faq/<int:fid>", methods=["PUT", "DELETE"])
def faq_modify(fid):
    db = get_db()
    _row, errore = _faq_o_404(db, fid)
    if errore:
        return errore
    if request.method == "DELETE":
        db.execute("DELETE FROM faq WHERE id = ?", (fid,))
        db.commit()
        return jsonify({"ok": True})

    data = request.get_json(force=True) or {}
    campi, errore = _faq_campi(data, row=_row)
    if errore:
        return errore
    if not campi:
        return jsonify(one(db.execute("SELECT * FROM faq WHERE id = ?", (fid,))))

    assignments = ", ".join(f"{k} = ?" for k in campi)
    db.execute(f"UPDATE faq SET {assignments} WHERE id = ?", [*campi.values(), fid])
    db.commit()
    return jsonify(one(db.execute("SELECT * FROM faq WHERE id = ?", (fid,))))


@app.route("/api/houses/password", methods=["PUT"])
def api_house_password():
    """Cambia la password della casa collegata."""
    slug = casa_attiva()
    data = request.get_json(force=True) or {}
    try:
        houses.cambia_password(slug, data.get("attuale"), data.get("nuova"))
    except ValueError as err:
        return bad_request(str(err))
    return jsonify({"ok": True})


def migra_case():
    """La prima casa raccoglie il database che c'era prima delle case.

    Se il registro e' vuoto e `cucina.db` esiste, quel database diventa la casa
    storica invece di restare orfano: senza questo passaggio i dati di mesi
    diventerebbero irraggiungibili, perche' nessuna sessione potrebbe puntarvi.
    La password e' generata e stampata una volta sola: va trascritta, non si
    recupera in seguito (nel registro c'e' solo l'impronta, non la password).
    """
    houses.init_registro()
    if houses.elenco():
        return
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        return
    password = secrets.token_urlsafe(9)
    houses.registra(houses.STORICA, "Casa", password, db_file=os.path.basename(DB_PATH))
    print("\n" + "=" * 64)
    print("Le case sono attive: il database esistente e' diventato la casa \"Casa\".")
    print(f"  Nome:     Casa")
    print(f"  Password: {password}")
    print("Annotala: nel registro c'e' solo l'impronta, non la password.")
    print("=" * 64 + "\n")


def avvia():
    """Avvia il server.

    Due modi, e la differenza conta:

    - **sviluppo** (`FLASK_DEBUG=1`): il ricaricatore di Flask, che riavvia da solo
      a ogni modifica del codice. Comodo mentre si scrive, inadatto a un server
      sempre acceso.
    - **produzione** (predefinito): un server vero, multi-thread, **senza
      ricaricatore**. Non e' un dettaglio: il ricaricatore tiene un processo
      supervisore che genera un figlio, quindi fermare "il server" ne lascia vivo
      uno dei due, e un sorvegliante che riavvia vedrebbe la porta occupata da un
      processo che credeva morto. In piu' il ricaricatore riavvia il server a ogni
      tocco di file: su una macchina di casa, con un editor aperto, significherebbe
      cadute continue.

    Si usa `waitress` se installato (regge piu' connessioni, pensato per questo),
    altrimenti il server di sviluppo senza ricaricatore: funziona, e non serve
    installare niente per partire.
    """
    host = os.environ.get("HOST", "0.0.0.0")
    porta = int(os.environ.get("PORT", 8000))

    # Il log finisce in un file, non in un terminale: senza flush riga l'annuncio
    # del server resterebbe invisibile finche' il processo non muore, cioe' proprio
    # quando serve leggerlo per capire cosa e' successo.
    def annuncia(testo):
        print(testo, flush=True)

    if os.environ.get("FLASK_DEBUG") == "1":
        annuncia(f"Server (sviluppo, con ricaricatore) su http://{host}:{porta}/")
        app.run(host=host, port=porta, debug=True)
        return

    try:
        from waitress import serve
        annuncia(f"Server (waitress) su http://{host}:{porta}/")
        serve(app, host=host, port=porta, threads=8)
    except ImportError:
        annuncia(f"Server (sviluppo, senza ricaricatore) su http://{host}:{porta}/")
        app.run(host=host, port=porta, debug=False, threaded=True)


if __name__ == "__main__":
    migra_case()
    init_db()
    avvia()
