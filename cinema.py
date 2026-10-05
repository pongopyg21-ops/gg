"""Cinema: le locandine dei film del momento, per ispirare una serata.

Non sono dati dell'app — sono un catalogo che sta su un servizio esterno
(TMDB) — e hanno lo stesso problema della TV: **la rete**. La regola e' quella
di `tv.py`, e vale identica: quello che si e' gia' scaricato **resta**, e un
guasto di rete non deve svuotare la sezione. Si mostra l'ultima copia buona e
si riprova piu' tardi, tenendo la copia in `tv_cache`, sotto la chiave `cinema`.

Il servizio chiede una **chiave** (`TMDB_API_KEY`). Senza, la sezione non e' un
guasto: e' una cosa da accendere, e lo dice con `messaggio_stato()`. La chiave
si legge dall'ambiente o da un file `segreto.*` accanto all'app (stessa regola
di `voce_cloud` e `comprensione`): **non si salva mai dall'app**.

Nessuna dipendenza nuova: `urllib.request` per scaricare e `json` per leggere.
Il modulo non apre database per conto suo: riceve una connessione, come `tv.py`,
cosi' non importa `app` e resta provabile da solo.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

import tv  # riusa la cache e i lucchetti: la forma e' la stessa della TV

NonDisponibile = tv.NonDisponibile

# Il servizio: TMDB. `discover` ordina per popolarita' e filtra per voto, cosi'
# "i migliori" non sono i film appena usciti senza voti ma quelli che la gente
# guarda e apprezza. Il filtro `with_watch_monetization_types=flatrate` tiene
# solo cio' che e' compreso in un abbonamento: e' la richiesta — film presenti
# sulle piattaforme di streaming, non al cinema.
BASE_URL = "https://api.themoviedb.org/3"
IMMAGINE_BASE = "https://image.tmdb.org/t/p/w500"
UA = "IlMaggiordomo/1.0 (app di casa; contatta chi amministra)"
TIMEOUT = 12
MAX_BYTE = 2_000_000

# Quanti film tenere. Uno alla volta se ne guarda uno; il resto e' per sfogliare.
QUANTI = 20
# Quanti film di nicchia in coda ai film del momento.
QUANTI_NICCHIA = 8
# La copia vale mezza giornata: un catalogo non cambia di ora in ora.
ORE_CINEMA = 12

REGIONE_PREDEFINITA = "IT"

# Cosa si toglie dal giro. Si toglie per **genere** e per **casa** di
# produzione, non per titolo: cosi' un film nuovo non va aggiunto a mano.
#
# 28 = Azione: e' il genere piu' popolare, quindi da solo riempirebbe il
# carosello e coprirebbe tutto il resto.
#
# 16 = Animazione, 10751 = Famiglia: sono i film destinati a bambini e ragazzi.
# Si tolgono per genere e non per eta' perche' la certificazione di TMDB non e'
# affidabile qui: gli operatori `.lte`/`.gte` vengono ignorati (restituiscono
# sempre lo stesso totale), i valori esatti coprono pochissimi film e molti —
# Harry Potter, Interstellar — non hanno alcuna certificazione italiana. Il
# genere invece c'e' sempre. Restano fuori anche i film d'animazione "per
# tutti" (Studio Ghibli, anime): e' il prezzo di una regola che non sbaglia.
#
# 420 = Marvel Studios, 7505 = Marvel Entertainment: con `without_companies`
# spariscono anche i film Marvel che Azione non marca (es. un film Marvel
# d'animazione). `|` separa le case in OR.
GENERI_ESCLUSI = "28"
GENERI_BAMBINI = "16,10751"
CASE_ESCLUSE = "420|7505"

# --- Non commerciale ---
# Il segno che un film "l'ha visto tutti" non e' il voto (che i film di
# cassetta hanno alto) ma **quanti** voti ha: i blockbuster viaggiano a decine
# di migliaia (Interstellar 41k, Blade Runner 2049 16k), un film che si scopre
# no. Si mette quindi un **tetto** ai voti, non solo un minimo: cosi' i titoli
# da grande distribuzione che restano popolari per anni escono dal giro, e
# restano i film nuovi o meno battuti. Il minimo tiene fuori i film senza
# pubblico, che non e' la stessa cosa di un film di nicchia.
VOTI_MIN = 50
VOTI_MAX = 3000
VOTO_MIN = 6.5

# --- Film di nicchia ---
# Cinema d'autore, cult, fuori dal coro. Si cercano per **tag** (le keyword di
# TMDB) e non per titolo: un film nuovo che porta quel tag entra da solo, come
# per generi e case. Sono i tag che TMDB assegna alle opere fuori dal
# mainstream: cinema indipendente, d'autore, cult, commedia nera, surrealismo,
# stop motion, realismo magico. Non e' una lista di film, e' un indizio di
# "fuori dal coro", quindi non va ampliata a caso.
PAROLE_NICCHIA = (
    "281237",   # independent film
    "318182",   # arthouse
    "374649",   # cult film
    "9887",     # surrealism
    "10123",    # dark comedy
    "10121",    # stop motion
    "293336",   # experimental film
    "382621",   # black comedy
    "156597",   # magic realism
)
VOTI_NICCHIA_MIN = 300
VOTI_NICCHIA_MAX = 10000
VOTO_NICCHIA_MIN = 6.8

# La chiave: l'ambiente, o uno di questi file accanto all'app. Stessi nomi di
# `voce_cloud` e `comprensione`.
_FILE_SEGRETI = ["segreto.txt", "segreto", "segreto.sh", "segreto.bat"]
_letto = {"fatto": False}


def _pulisci(valore: str) -> str:
    return (valore or "").strip().strip("'\"")


def _riga_chiave(riga: str):
    """Legge una riga di `segreto.*` in una delle forme accettate.

    Come `comprensione._riga_chiave`: `NOME=valore`, `chiave: valore`,
    `export ...`, oppure il valore nudo. Qui i nomi sono quelli di TMDB, e le
    etichette leggibili (`tmdb`, `cinema`) vengono ricondotte al nome vero.
    """
    riga = riga.strip()
    if not riga or riga.startswith(("#", "REM ", "rem ", "@")):
        return None
    m = re.match(r"(?:set\s+\"?|export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*"
                 r"(?:\"([^\"]*)\"|'([^']*)'|(.*))$", riga)
    if m:
        nome = m.group(1).lower()
        valore = _pulisci(m.group(2) or m.group(3) or m.group(4) or "")
        alias = {
            "tmdb_api_key": "TMDB_API_KEY", "tmdb_key": "TMDB_API_KEY",
            "tmdb": "TMDB_API_KEY", "cinema_api_key": "TMDB_API_KEY",
            "cinema_key": "TMDB_API_KEY", "api_key": "TMDB_API_KEY",
            "cinema_region": "CINEMA_REGION", "tmdb_region": "CINEMA_REGION",
            "regione_cinema": "CINEMA_REGION",
        }
        return alias.get(nome, nome.upper()), valore
    if " " not in riga and riga.isprintable():
        # nudo: una chiave TMDB e' esadecimale (32 caratteri). Il resto — l'area,
        # una parola minuscola — non ci riguarda: la legge `voce_cloud`.
        if re.fullmatch(r"[0-9a-fA-F]{32}", riga):
            return "TMDB_API_KEY", riga
        return None
    return None


def _leggi_file() -> None:
    """Se l'ambiente non ha la chiave, la cerca in un file accanto all'app.

    La chiave **non** si salva dall'app: si mette prima di avviare, come quella
    Azure. Nei sandbox, dove i file spariscono, si usa l'ambiente.
    """
    if _letto["fatto"]:
        return
    _letto["fatto"] = True
    cartelle = [os.path.dirname(os.path.abspath(__file__)),
                os.environ.get("MAGGIORDOMO_DATA", "")]
    for cartella in dict.fromkeys(c for c in cartelle if c):
        for nome in _FILE_SEGRETI:
            percorso = os.path.join(cartella, nome)
            if not os.path.exists(percorso):
                continue
            try:
                testo = open(percorso, encoding="utf-8-sig", errors="replace").read()
            except OSError:
                continue
            for riga in testo.splitlines():
                letto = _riga_chiave(riga)
                if not letto:
                    continue
                nome_var, valore = letto
                if valore and not os.environ.get(nome_var):
                    os.environ[nome_var] = valore


def chiave() -> str:
    """La chiave di TMDB: l'ambiente per primo, poi il file."""
    _leggi_file()
    return _pulisci(os.environ.get("TMDB_API_KEY", ""))


def regione() -> str:
    """La regione delle piattaforme: da dove si guarda.

    Determina **quali** servizi di streaming sono disponibili (Netflix in Italia
    non ha lo stesso catalogo che negli Stati Uniti). Si puo' cambiare con
    `CINEMA_REGION`, ma il predefinito e' l'Italia: e' un'app di casa italiana.
    """
    _leggi_file()
    return (os.environ.get("CINEMA_REGION") or REGIONE_PREDEFINITA).strip().upper()[:2]


def configurato() -> bool:
    """C'e' una chiave per chiedere i film?"""
    return bool(chiave())


def messaggio_stato() -> str:
    """Cosa manca, in una frase, per dirlo nella sezione. Vuoto = a posto.

    Il messaggio dice **come** accendere la sezione, non solo che e' spenta: una
    sezione vuota senza spiegazione fa pensare a un guasto.
    """
    if configurato():
        return ""
    return ("Per vedere i film serve una chiave TMDB. Registrane una su "
            "themoviedb.org e mettila in `TMDB_API_KEY` (ambiente o file "
            "`segreto.txt`), poi riavvia l'app.")


def _apri(url: str) -> bytes:
    """Scarica un indirizzo. Unico punto di rete: nei test si sostituisce questo."""
    richiesta = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:
            dati = risposta.read(MAX_BYTE + 1)
    except (OSError, ValueError) as errore:
        raise NonDisponibile(f"Non raggiungo {url}") from errore
    if len(dati) > MAX_BYTE:
        raise NonDisponibile(f"Risposta troppo grande da {url}")
    return dati


def _chiama(percorso: str, parametri: dict) -> dict:
    """Una chiamata a TMDB, con la chiave e la lingua.

    La lingua e' l'italiano: il titolo e la trama devono leggersi, non essere un
    indizio da tradurre.
    """
    if not configurato():
        raise NonDisponibile("Manca la chiave TMDB")
    query = {**parametri, "api_key": chiave(), "language": "it-IT"}
    url = f"{BASE_URL}{percorso}?{urllib.parse.urlencode(query)}"
    try:
        return json.loads(_apri(url))
    except (ValueError, TypeError) as errore:
        raise NonDisponibile(f"Risposta illeggibile da {url}") from errore


def _piattaforme(dati: dict) -> list:
    """I servizi di streaming in abbonamento nella regione della casa.

    Si legge dalla risposta di `movie/{id}/watch/providers`. Si tengono solo i
    servizi in abbonamento (`flatrate`): a noleggio o acquisto non e' quello che
    si cerca — non e' "presente su una piattaforma" nel senso in cui lo si
    intende quando si cerca cosa guardare stasera.
    """
    fornitori = (dati or {}).get("results") or {}
    if not isinstance(fornitori, dict):
        return []
    nella_regione = fornitori.get(regione()) or {}
    if not isinstance(nella_regione, dict):
        return []
    elenco = nella_regione.get("flatrate") or []
    if not isinstance(elenco, list):
        return []
    return [p.get("provider_name") for p in elenco
            if isinstance(p, dict) and p.get("provider_name")]


def _fornitori(id_film) -> list:
    """I servizi di un film, chiesti a parte.

    `discover` **non** allega `watch/providers`: l'`append_to_response` vale solo
    sugli endpoint di dettaglio, e su `discover` viene ignorato in silenzio. I
    fornitori vanno quindi chiesti film per film. Sono un di piu': se la chiamata
    non riesce, il film resta, solo senza le piattaforme.
    """
    try:
        return _piattaforme(_chiama(f"/movie/{id_film}/watch/providers", {}))
    except NonDisponibile:
        return []


def _scheda(voce: dict) -> dict:
    """Da una voce di TMDB alla scheda che serve alla sezione.

    Si tengono solo i campi che si mostrano, e si scarta un film senza locandina:
    e' una sezione di immagini, e una senza immagine non ispira niente. Le
    piattaforme non sono qui: si aggiungono dopo, con `_fornitori`.
    """
    locandina = voce.get("poster_path") or ""
    titolo = (voce.get("title") or voce.get("original_title") or "").strip()
    if not locandina or not titolo:
        return {}
    data = (voce.get("release_date") or "").strip()
    voto = voce.get("vote_average")
    return {
        "id": voce.get("id"),
        "titolo": titolo,
        "anno": data[:4],
        "data": data,
        "voto": round(float(voto), 1) if isinstance(voto, (int, float)) and voto else None,
        "voti": int(voce.get("vote_count") or 0),
        "trama": (voce.get("overview") or "").strip(),
        "locandina": IMMAGINE_BASE + locandina,
    }


def _escludi(parametri: dict) -> dict:
    """Aggiunge i filtri di esclusione: via azione, bambini e film Marvel.

    `without_genres` accetta piu' generi separati da virgola, in OR: un film
    resta fuori se ha **uno qualunque** dei generi elencati.
    """
    return {
        **parametri,
        "without_genres": f"{GENERI_ESCLUSI},{GENERI_BAMBINI}",
        "without_companies": CASE_ESCLUSE,
    }


def _schede_di(risposta: dict) -> list:
    """Da una risposta di `discover` alle schede, scartando quelle vuote."""
    return [s for s in (_scheda(v) for v in risposta.get("results", [])) if s]


def _nicchia() -> list:
    """Film di nicchia: cinema d'autore, cult, fuori dal coro.

    Si cercano per tag (`PAROLE_NICCHIA`), con lo stesso tetto ai voti dei film
    del momento: un film che l'ha visto tutti porta spesso un tag "cult" senza
    essere quello che si cerca. Si ordina per voto, non per popolarita': qui
    conta la qualita' riconosciuta, non il momento. Se la chiamata non riesce,
    non e' un guasto: la sezione ha gia' i film del momento.
    """
    try:
        risposta = _chiama("/discover/movie", _escludi({
            "sort_by": "vote_average.desc",
            "with_keywords": "|".join(PAROLE_NICCHIA),
            "vote_count.gte": VOTI_NICCHIA_MIN,
            "vote_count.lte": VOTI_NICCHIA_MAX,
            "vote_average.gte": VOTO_NICCHIA_MIN,
            "include_adult": "false",
            "page": 1,
        }))
    except NonDisponibile:
        return []
    return _schede_di(risposta)


def _scarica(_db) -> list:
    """I film del momento (non commerciali), piu' qualche film di nicchia.

    Azione, film per bambini/ragazzi e film Marvel restano fuori (vedi
    `_escludi`). Il tetto ai voti (`VOTI_MAX`) tiene fuori i blockbuster che
    restano popolari per anni: sono i titoli che "l'ha visto tutti". La nicchia
    si accoda e si tolgono i doppioni: un film non compare due volte.
    """
    dati = _chiama("/discover/movie", _escludi({
        "sort_by": "popularity.desc",
        "vote_count.gte": VOTI_MIN,
        "vote_count.lte": VOTI_MAX,
        "vote_average.gte": VOTO_MIN,
        "include_adult": "false",
        "page": 1,
    }))
    schede = _schede_di(dati)[:QUANTI]
    visti = {s["id"] for s in schede}
    for scheda in _nicchia():
        if len(schede) >= QUANTI + QUANTI_NICCHIA:
            break
        if scheda["id"] not in visti:
            visti.add(scheda["id"])
            schede.append(scheda)
    for scheda in schede:
        scheda["piattaforme"] = _fornitori(scheda["id"])
    return schede


def aggiorna(db, forse=True) -> bool:
    """Aggiorna la copia dei film. Non solleva mai: e' chiamata in sottofondo."""
    return tv._aggiorna(db, "cinema", ORE_CINEMA, _scarica, forse=forse)


def film(db) -> list:
    return tv._leggi(db, "cinema")[0] or []


def preferiti(db) -> list:
    """Le schede dei film segnati come preferiti, i piu' recenti per primi.

    La scheda salvata e' completa: un preferito si vede anche dopo che e'
    uscito dal giro dei film del momento.
    """
    righe = db.execute(
        "SELECT dati FROM cinema_preferiti ORDER BY created_at DESC, movie_id DESC"
    ).fetchall()
    fuori = []
    for riga in righe:
        try:
            scheda = json.loads(riga["dati"])
        except (ValueError, TypeError):
            continue
        if isinstance(scheda, dict):
            fuori.append(scheda)
    return fuori


def e_preferito(db, movie_id) -> bool:
    return db.execute(
        "SELECT 1 FROM cinema_preferiti WHERE movie_id = ?", (movie_id,)
    ).fetchone() is not None


def segna(db, movie_id, scheda: dict) -> None:
    """Segna un film come preferito, salvandone la scheda."""
    db.execute(
        "INSERT OR REPLACE INTO cinema_preferiti (movie_id, dati, created_at) "
        "VALUES (?, ?, datetime('now'))",
        (movie_id, json.dumps(scheda, ensure_ascii=False)),
    )
    db.commit()


def togli(db, movie_id) -> None:
    db.execute("DELETE FROM cinema_preferiti WHERE movie_id = ?", (movie_id,))
    db.commit()


def trova(db, movie_id):
    """La scheda di un film nella copia corrente, se c'e'."""
    for scheda in film(db):
        if scheda.get("id") == movie_id:
            return scheda
    return None


def quando_aggiornato(db):
    return tv._leggi(db, "cinema")[1] or None
