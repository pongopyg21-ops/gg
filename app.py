import os
import re
import sqlite3
from contextlib import closing

from flask import Flask, g, jsonify, request, send_from_directory

import allergens
import units

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("CUCINA_DB", os.path.join(BASE_DIR, "cucina.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

app = Flask(__name__, static_folder="static", static_url_path="/static")

MEALS = ["pranzo", "cena"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as db:
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            db.executescript(fh.read())
        db.commit()


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


def one(cur):
    r = cur.fetchone()
    return dict(r) if r else None


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


def get_profile(db):
    """Profilo utente; la riga viene creata al primo accesso."""
    cur = db.execute("SELECT * FROM profile WHERE id = 1")
    profile = one(cur)
    if profile is None:
        db.execute("INSERT INTO profile (id) VALUES (1)")
        db.commit()
        profile = one(db.execute("SELECT * FROM profile WHERE id = 1"))
    profile["restriction_list"] = parse_terms(profile["restrictions"])
    return profile


PROFILE_FIELDS = {"full_name", "restrictions", "onboarded"}


def save_profile(db, data):
    # la riga singola deve esistere prima dell'UPDATE, altrimenti non aggiorna nulla
    get_profile(db)
    values = {k: data[k] for k in PROFILE_FIELDS if k in data}
    if "restrictions" in values:
        values["restrictions"] = ", ".join(parse_terms(values["restrictions"]))
    if "onboarded" in values:
        values["onboarded"] = 1 if values["onboarded"] else 0
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
    return jsonify({"meals": MEALS, "units": ["pz", "g", "kg", "ml", "l", "cucchiaio", "cucchiaino", "confezione", "fetta"],
                    "categories": ["Frutta e Verdura", "Carne e Pesce", "Latticini", "Dispensa",
                                   "Pane e Cereali", "Surgelati", "Bevande", "Dolci", "Altro"],
                    "allergens": [{"key": k, "label": v} for k, v in allergens.ALLERGENS.items()]})


# ---------------------------------------------------------------- profilo
@app.route("/api/profile", methods=["GET", "PUT"])
def profile():
    db = get_db()
    if request.method == "PUT":
        data = request.get_json(force=True) or {}
        return jsonify(save_profile(db, data))
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
                return jsonify({"ok": True}), 201
        db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, ?, ?)", (iid, qty, unit))
    else:
        db.execute("UPDATE pantry SET quantity = quantity + ?, updated_at = datetime('now') WHERE id = ?",
                   (qty, existing["id"]))
    db.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/pantry/<int:pid>", methods=["PATCH", "DELETE"])
def pantry_modify(pid):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM pantry WHERE id = ?", (pid,))
        db.commit()
        return jsonify({"ok": True})
    data = request.get_json(force=True) or {}
    db.execute("UPDATE pantry SET quantity = ?, updated_at = datetime('now') WHERE id = ?",
               (parse_float(data.get("quantity"), 0), pid))
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
    return rec


@app.route("/api/recipes", methods=["GET", "POST"])
def recipes():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return bad_request("Il nome è obbligatorio")
        cur = db.execute(
            "INSERT INTO recipes (name, servings, time_minutes, difficulty, instructions) VALUES (?, ?, ?, ?, ?)",
            (name, int(parse_float(data.get("servings"), 2)), data.get("time_minutes") or None,
             data.get("difficulty") or "facile", data.get("instructions") or ""),
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
        out = []
        for i in ids:
            rec = recipe_full(db, i)
            tags, hits = recipe_safety(db, i, restriction_list)
            rec["allergens"] = sorted(allergens.label_for(t) for t in tags)
            rec["conflicts"] = hits
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
        db.commit()
        return jsonify({"ok": True})

    if request.method == "PUT":
        data = request.get_json(force=True) or {}
        db.execute(
            """UPDATE recipes SET name = ?, servings = ?, time_minutes = ?, difficulty = ?, instructions = ?
               WHERE id = ?""",
            ((data.get("name") or "").strip(), int(parse_float(data.get("servings"), 2)),
             data.get("time_minutes") or None, data.get("difficulty") or "facile",
             data.get("instructions") or "", rid),
        )
        db.execute("DELETE FROM recipe_items WHERE recipe_id = ?", (rid,))
        for it in data.get("items") or []:
            iname = (it.get("name") or "").strip()
            if not iname:
                continue
            iid = get_or_create_ingredient(db, iname, units.normalize(it.get("unit")), it.get("category") or "Altro")
            db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)",
                       (rid, iid, parse_float(it.get("quantity"), 0), units.normalize(it.get("unit"))))
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
    if data["meal"] not in MEALS:
        return bad_request("Pasto non valido")
    db.execute(
        """INSERT INTO meal_plan (date, meal, recipe_id, servings) VALUES (?, ?, ?, ?)
           ON CONFLICT(date, meal) DO UPDATE SET recipe_id = excluded.recipe_id, servings = excluded.servings""",
        (data["date"], data["meal"], int(data["recipe_id"]), int(parse_float(data.get("servings"), 2))),
    )
    db.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/plan/<int:pid>", methods=["DELETE"])
def plan_delete(pid):
    db = get_db()
    db.execute("DELETE FROM meal_plan WHERE id = ?", (pid,))
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
    return jsonify(items)


@app.route("/api/shopping/<int:sid>", methods=["PATCH", "DELETE"])
def shopping_modify(sid):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM shopping_items WHERE id = ?", (sid,))
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
    db.commit()
    return jsonify({"ok": True})


def net_quantity(db, ingredient_id, unit, needed):
    """Quantità da comprare: fabbisogno meno dispensa, convertendo le unità compatibili."""
    have = 0.0
    for p in db.execute("SELECT quantity, unit FROM pantry WHERE ingredient_id = ?", (ingredient_id,)):
        converted = units.convert(p["quantity"], p["unit"], unit)
        if converted is not None:
            have += converted
    return max(needed - have, 0.0)


@app.route("/api/shopping/generate", methods=["POST"])
def shopping_generate():
    db = get_db()
    data = request.get_json(force=True) or {}
    start = data.get("start")
    end = data.get("end")
    if not start or not end:
        return bad_request("start e end sono obbligatori")

    plan = rows(db.execute(
        """SELECT mp.recipe_id, mp.servings AS plan_servings
           FROM meal_plan mp JOIN recipes r ON r.id = mp.recipe_id
           WHERE mp.date BETWEEN ? AND ?""",
        (start, end),
    ))
    if not plan:
        return bad_request("Nessun pasto pianificato nel periodo indicato", 404)

    # Ricette coinvolte, con le porzioni della ricetta base per scalare le quantità
    recipe_base = {r["id"]: (r["servings"] or 1) for r in db.execute(
        """SELECT DISTINCT r.id, r.servings FROM recipes r
           JOIN meal_plan mp ON mp.recipe_id = r.id
           WHERE mp.date BETWEEN ? AND ?""",
        (start, end),
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

    added = 0

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
        row = one(db.execute(
            "SELECT * FROM shopping_items WHERE ingredient_id = ? AND checked = 0 AND unit = ?",
            (iid, buy_unit)))
        if not row:
            # voce aperta in un'altra unità compatibile: ci si accoda convertendo
            for cand in db.execute(
                "SELECT * FROM shopping_items WHERE ingredient_id = ? AND checked = 0", (iid,)
            ):
                converted = units.convert(to_buy, buy_unit, cand["unit"])
                if converted is not None:
                    row = cand
                    to_buy = converted
                    break
        if row:
            db.execute("UPDATE shopping_items SET quantity = ? WHERE id = ?",
                       (units.format_quantity(row["quantity"] + to_buy), row["id"]))
        else:
            db.execute(
                "INSERT INTO shopping_items (name, quantity, unit, category, ingredient_id) VALUES (?, ?, ?, ?, ?)",
                (entry["name"], units.format_quantity(to_buy), buy_unit, entry["category"], iid),
            )
        added += 1
    db.commit()
    return jsonify({"added": added})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
