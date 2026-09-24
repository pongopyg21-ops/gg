"""Case separate: registro, password e un database per ciascuna.

Ogni casa e' un'applicazione a se': ricette, dispensa, piano, spesa, pulizie,
FAQ, progetti e magazzino non si vedono fra loro. La separazione e' un **file di
database distinto** per casa, non una colonna `house_id` sulle tabelle: le
tabelle sono tredici e le query cinquanta, e una colonna dimenticata da qualche
parte farebbe trapelare i dati di una casa nell'altra. Cambiando il file, invece,
tutte le query esistenti restano com'e' sono.

Il registro delle case e' a parte (`houses.db`): sa quali esistono e con quale
password, ma non contiene nessun dato della casa. Cosi' cancellare una casa e'
cancellare un file, senza toccare le altre.

Le password sono in PBKDF2-SHA256 con sale casuale. Non e' una difesa contro un
attacco mirato a un'app di casa, ma evita che la password resti scritta in
chiaro nel registro: se un domani il file finisce in un backup, non e' leggibile.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from contextlib import closing

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dove vivono i dati. Normalmente accanto al codice, ma `MAGGIORDOMO_DATA` permette
# di tenerli altrove: e' quello che serve quando il codice sta in un'immagine
# (Docker) o viene aggiornato spesso, mentre i dati devono restare fermi e fare
# parte di un backup. I file sono tre - registro, case e database storico - e
# stanno insieme perche' separarli significherebbe dimenticarsene uno.
DATA_DIR = os.environ.get("MAGGIORDOMO_DATA", BASE_DIR)

# Il registro e' separato per casa per scelta: contiene solo nomi e password.
REGISTRY_PATH = os.path.join(DATA_DIR, "houses.db")

# Le case vivono qui, una per file: `case-<slug>.db`.
CASE_DIR = os.path.join(DATA_DIR, "case")

# Nome della casa che raccoglie il database storico (`cucina.db`), la prima
# creata. Serve alla migrazione: la casa che trova il database gia' pieno lo
# adotta invece di nascere vuota.
STORICA = "casa"

_ITERAZIONI = 200_000
_SALE_BYTE = 16


# --------------------------------------------------------------- password

def hash_password(password, iterations=_ITERAZIONI):
    """Restituisce `pbkdf2_sha256$iterazioni$sale$hash`, tutto in una stringa."""
    password = _pulita(password)
    if not password:
        raise ValueError("La password non può essere vuota")
    sale = secrets.token_bytes(_SALE_BYTE)
    impronta = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sale, iterations)
    return f"pbkdf2_sha256${iterations}${sale.hex()}${impronta.hex()}"


def _pulita(password) -> str:
    """Toglie gli spazi ai bordi della password.

    Nasce da un accesso impossibile: incollando la password dal telefono o
    scrivendola con la correzione automatica, resta uno spazio finale. Lo spazio
    non si vede — nel campo il testo e' nascosto — e il rifiuto e' identico a
    quello di una password sbagliata, quindi non si capisce cosa correggere.

    Uno spazio ai bordi non e' mai voluto: nessuno sceglie una password che
    comincia o finisce con uno spazio, mentre il copia-incolla lo aggiunge da
    solo. Toglierlo dentro le password di casa non cambia le regole per le
    altre: restano due confronti, `autentica` e `verifica_password`, e quello
    che conta e' che l'accesso e il salvataggio usino lo stesso.
    """
    return (password or "").strip()


def verifica_password(password, memorizzata):
    """Confronto a tempo costante: non rivela a che punto la password differisce."""
    try:
        algoritmo, iterazioni, sale_hex, atteso_hex = memorizzata.split("$")
    except (ValueError, AttributeError):
        return False
    if algoritmo != "pbkdf2_sha256":
        return False
    try:
        iterazioni = int(iterazioni)
        sale = bytes.fromhex(sale_hex)
        atteso = bytes.fromhex(atteso_hex)
    except ValueError:
        return False
    calcolato = hashlib.pbkdf2_hmac("sha256", _pulita(password).encode("utf-8"), sale, iterazioni)
    return hmac.compare_digest(calcolato, atteso)


# --------------------------------------------------------------- registro

def _connect_registro(percorso=None):
    db = sqlite3.connect(percorso or REGISTRY_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def one_registro(db, sql, parametri=()):
    riga = db.execute(sql, parametri).fetchone()
    return dict(riga) if riga else None


def init_registro(percorso=None):
    os.makedirs(CASE_DIR, exist_ok=True)
    with closing(_connect_registro(percorso)) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS houses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                slug       TEXT NOT NULL UNIQUE,
                nome       TEXT NOT NULL,
                password   TEXT NOT NULL,
                -- Dove sta il database della casa, relativo alla cartella del
                -- progetto. Vuoto = `case/case-<slug>.db` (il caso normale). La
                -- casa storica lo usa per puntare a `cucina.db`, che esisteva
                -- prima delle case e che non vogliamo spostare o copiare.
                db_file    TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            -- Il nome e' quello che l'utente scrive per entrare: due case con lo
            -- stesso nome renderebbero l'accesso ambiguo, quindi e' unico a meno
            -- di maiuscole ("Casa" e "casa" sono la stessa).
            CREATE UNIQUE INDEX IF NOT EXISTS idx_houses_nome
                ON houses (nome COLLATE NOCASE);
            -- La chiave che firma i biscotti di sessione. Sta qui e non in una
            -- variabile generata all'avvio: altrimenti ogni riavvio del server
            -- scollegherebbe tutti, e i riavvii qui sono frequenti.
            CREATE TABLE IF NOT EXISTS meta (
                chiave TEXT PRIMARY KEY,
                valore TEXT NOT NULL
            );
        """)
        db.commit()


def secret_key(percorso=None):
    """Chiave di firma delle sessioni, creata una volta e poi riusata."""
    init_registro(percorso)
    with closing(_connect_registro(percorso)) as db:
        riga = db.execute("SELECT valore FROM meta WHERE chiave = 'secret_key'").fetchone()
        if riga is None:
            valore = secrets.token_hex(32)
            db.execute("INSERT INTO meta (chiave, valore) VALUES ('secret_key', ?)", (valore,))
            db.commit()
            return valore
        return riga["valore"]


def slugify(nome):
    """`Casa di Anna!` -> `casa-di-anna`. Il nome resta come l'utente l'ha scritto."""
    piatto = unicodedata.normalize("NFKD", nome or "")
    piatto = "".join(c for c in piatto if not unicodedata.combining(c))
    piatto = re.sub(r"[^a-zA-Z0-9]+", "-", piatto).strip("-").lower()
    return piatto or "casa"


def db_path(slug, percorso=None):
    """Percorso del database di una casa. Lo slug e' validato: niente traversal."""
    if not re.fullmatch(r"[a-z0-9-]{1,60}", slug or ""):
        raise ValueError("Slug non valido")
    init_registro(percorso)
    with closing(_connect_registro(percorso)) as db:
        riga = db.execute("SELECT db_file FROM houses WHERE slug = ?", (slug,)).fetchone()
    # il nome del file non viene mai dall'esterno: lo scrive solo `registra`,
    # e per la casa storica e' la costante `cucina.db`. Va cercato in DATA_DIR e
    # non in BASE_DIR, altrimenti la casa storica resterebbe invisibile quando i
    # dati stanno altrove (es. un volume Docker).
    if riga is not None and riga["db_file"]:
        return os.path.join(DATA_DIR, os.path.basename(riga["db_file"]))
    return os.path.join(CASE_DIR, f"case-{slug}.db")


def elenco(percorso=None):
    """Le case esistenti, senza i dati della casa e senza le password."""
    init_registro(percorso)
    with closing(_connect_registro(percorso)) as db:
        return [{"slug": r["slug"], "nome": r["nome"]}
                for r in db.execute("SELECT slug, nome FROM houses ORDER BY nome COLLATE NOCASE")]


def esiste(slug, percorso=None):
    init_registro(percorso)
    with closing(_connect_registro(percorso)) as db:
        return db.execute("SELECT 1 FROM houses WHERE slug = ?", (slug,)).fetchone() is not None


def nome_di(slug, percorso=None):
    init_registro(percorso)
    with closing(_connect_registro(percorso)) as db:
        riga = db.execute("SELECT nome FROM houses WHERE slug = ?", (slug,)).fetchone()
        return riga["nome"] if riga else None


def per_nome(nome, percorso=None):
    """La casa con questo nome, o None. L'accesso parte dal nome scritto."""
    init_registro(percorso)
    with closing(_connect_registro(percorso)) as db:
        return one_registro(db, "SELECT slug, nome FROM houses WHERE nome = ? COLLATE NOCASE",
                            ((nome or "").strip(),))


def registra(slug, nome, password, db_file="", percorso=None):
    """Registra una casa con slug e nome espliciti. Usata dalla migrazione."""
    with closing(_connect_registro(percorso)) as db:
        db.execute("INSERT INTO houses (slug, nome, password, db_file) VALUES (?, ?, ?, ?)",
                   (slug, nome, hash_password(password), db_file))
        db.commit()


def crea(nome, password, percorso=None):
    """Crea una casa con la sua password. Ritorna lo slug. Non crea il DB.

    Il database lo crea `app.init_db()` una volta che la casa esiste nel
    registro: cosi' il ricettario di partenza si semina nell'unico posto che
    gia' sa farlo per il database storico.
    """
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Il nome della casa è obbligatorio")
    if not password or len(password) < 4:
        raise ValueError("La password deve avere almeno 4 caratteri")
    init_registro(percorso)
    if per_nome(nome, percorso):
        raise ValueError("Esiste già una casa con questo nome")
    with closing(_connect_registro(percorso)) as db:
        slug = slugify(nome)
        # due case possono chiamarsi "Casa" senza confondersi: lo slug si allunga
        if db.execute("SELECT 1 FROM houses WHERE slug = ?", (slug,)).fetchone():
            base, n = slug, 2
            while db.execute("SELECT 1 FROM houses WHERE slug = ?", (slug,)).fetchone():
                slug = f"{base}-{n}"
                n += 1
        db.execute("INSERT INTO houses (slug, nome, password) VALUES (?, ?, ?)",
                   (slug, nome, hash_password(password)))
        db.commit()
    return slug


def autentica(slug, password, percorso=None):
    """True se la password e' quella della casa. False per casa inesistente.

    Il caso "casa inesistente" fa comunque il confronto su una password finta:
    senza, il tempo di risposta direbbe quali case esistono.
    """
    init_registro(percorso)
    with closing(_connect_registro(percorso)) as db:
        riga = db.execute("SELECT password FROM houses WHERE slug = ?", (slug,)).fetchone()
    if riga is None:
        verifica_password(password or "", hash_password("inesistente"))
        return False
    return verifica_password(password or "", riga["password"])


# ------------------------------------------------- tentativi di accesso
# Le password sono protette bene (PBKDF2 con sale), ma nulla impediva di
# provarne quante se ne vuole: il server ascolta su `0.0.0.0` per farsi
# raggiungere dal telefono, quindi chiunque sia sulla stessa rete puo' tentare
# all'infinito. Le impronte sono lente apposta, e questo gia' rallenta, ma un
# attacco che continua per giorni prima o poi trova una password debole.
#
# Non serve un sistema sofisticato: serve togliere la comodita' del tentativo
# illimitato. Dopo qualche errore si risponde "aspetta ancora N secondi", e
# l'attesa raddoppia a ogni errore fino a un tetto. Chi sbaglia la password una
# volta aspetta un secondo; chi la indovina provando passa la notte su poche
# decine di tentativi.

TENTATIVI_LIBERI = 3
ATTESA_BASE = 1.0
ATTESA_MASSIMA = 30.0
# Dopo mezz'ora senza errori il contatore si azzera da solo: una password
# sbagliata di sera non deve far aspettare la mattina dopo.
DIMENTICARE_DOPO = 30 * 60

_tentativi = {}
_tentativi_lock = threading.Lock()


def _adesso():
    return time.monotonic()


def _pulisci(adesso):
    """Toglie i contatori vecchi: senza, la memoria cresce a ogni nome provato."""
    for chiave in [c for c, s in _tentativi.items() if adesso - s["ultimo"] > DIMENTICARE_DOPO]:
        del _tentativi[chiave]


def chiavi_tentativi(indirizzo, nome):
    """Due contatori per lo stesso tentativo: chi lo fa e per quale casa.

    Uno solo non basterebbe. Contando solo per indirizzo, dietro un tunnel o un
    port forwarding tutti i dispositivi risultano lo stesso indirizzo, e un
    errore di uno farebbe aspettare anche gli altri. Contando solo per casa, chi
    prova nomi diversi non verrebbe mai fermato. Si contano entrambi e vince
    l'attesa piu' lunga.
    """
    nome = (nome or "").strip().lower()
    chiavi = [f"ip:{indirizzo or '?'}"]
    if nome:
        chiavi.append(f"casa:{nome}")
    return chiavi


def attesa_accesso(indirizzo, nome, adesso=None):
    """Quanti secondi mancano prima di poter riprovare. Zero se si puo' subito.

    Non fa dormire la richiesta: un server che aspetta tiene occupato un filo, e
    con piu' tentativi in corso i fili finirebbero, cioe' l'app sembrerebbe
    piantata. Si risponde subito dicendo quanto aspettare.
    """
    adesso = adesso if adesso is not None else _adesso()
    with _tentativi_lock:
        _pulisci(adesso)
        attese = [_tentativi[k]["bloccato_fino"] - adesso
                  for k in chiavi_tentativi(indirizzo, nome) if k in _tentativi]
    return max([0.0] + attese)


def segnala_fallimento(indirizzo, nome, adesso=None):
    """Registra un tentativo sbagliato e allunga l'attesa per i prossimi."""
    adesso = adesso if adesso is not None else _adesso()
    with _tentativi_lock:
        _pulisci(adesso)
        for chiave in chiavi_tentativi(indirizzo, nome):
            stato = _tentativi.setdefault(chiave, {"errori": 0, "ultimo": adesso,
                                                   "bloccato_fino": 0.0})
            stato["errori"] += 1
            stato["ultimo"] = adesso
            # Si tollerano `TENTATIVI_LIBERI` errori: sbagliare la password un
            # paio di volte capita a tutti, e far aspettare al primo errore
            # sarebbe solo fastidioso. Raggiunta la soglia, il tentativo
            # successivo trova l'attesa, che raddoppia a ogni errore in piu'.
            oltre = stato["errori"] - TENTATIVI_LIBERI + 1
            if oltre >= 1:
                attesa = min(ATTESA_BASE * (2 ** (oltre - 1)), ATTESA_MASSIMA)
                stato["bloccato_fino"] = adesso + attesa


def segnala_successo(indirizzo, nome):
    """L'accesso riuscito azzera il contatore: e' la password giusta."""
    with _tentativi_lock:
        for chiave in chiavi_tentativi(indirizzo, nome):
            _tentativi.pop(chiave, None)


def dimentica_tentativi():
    """Azzera tutti i contatori. Usata dai test per non dipendere dall'ordine."""
    with _tentativi_lock:
        _tentativi.clear()


def rinomina(slug, nome, percorso=None):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Il nome della casa è obbligatorio")
    with closing(_connect_registro(percorso)) as db:
        db.execute("UPDATE houses SET nome = ? WHERE slug = ?", (nome, slug))
        db.commit()


def cambia_password(slug, vecchia, nuova, percorso=None):
    if not autentica(slug, vecchia, percorso):
        raise ValueError("La password attuale non è corretta")
    if not nuova or len(nuova) < 4:
        raise ValueError("La nuova password deve avere almeno 4 caratteri")
    with closing(_connect_registro(percorso)) as db:
        db.execute("UPDATE houses SET password = ? WHERE slug = ?", (hash_password(nuova), slug))
        db.commit()


def reimposta_password(slug, nuova, percorso=None):
    """Mette una password nuova **senza chiedere quella vecchia**.

    Serve a chi la password l'ha persa: nel registro c'e' solo l'impronta, quindi
    non si puo' recuperare, si puo' solo sostituire. Non e' una scorciatoia per
    l'app: li' la vecchia resta obbligatoria (`cambia_password`). Chi ha accesso
    ai file ha gia' i dati, quindi togliere il controllo non apre niente di nuovo.
    """
    if not nuova or len(nuova) < 4:
        raise ValueError("La nuova password deve avere almeno 4 caratteri")
    if not esiste(slug, percorso):
        raise ValueError(f"La casa \"{slug}\" non esiste")
    with closing(_connect_registro(percorso)) as db:
        db.execute("UPDATE houses SET password = ? WHERE slug = ?", (hash_password(nuova), slug))
        db.commit()


def elimina(slug, percorso=None):
    """Toglie la casa dal registro. Il file del database resta su disco.

    Non lo si cancella di proposito: un errore di click non deve distruggere
    mesi di ricette. Chi vuole ripulire davvero trova i file in `case/`.
    """
    with closing(_connect_registro(percorso)) as db:
        db.execute("DELETE FROM houses WHERE slug = ?", (slug,))
        db.commit()
