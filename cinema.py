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
# La copia vale mezza giornata: un catalogo non cambia di ora in ora.
ORE_CINEMA = 12

REGIONE_PREDEFINITA = "IT"

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


def _piattaforme(voce: dict) -> list:
    """I servizi di streaming su cui il film e' compreso, in abbonamento.

    Si legge da `watch/providers`, che TMDB allega alla richiesta. Si tengono
    solo i servizi in abbonamento (`flatrate`): a noleggio o acquisto non e'
    quello che si cerca — non e' "presente su una piattaforma" nel senso in cui
    lo si intende quando si cerca cosa guardare stasera.
    """
    fornitori = (voce.get("watch/providers") or {}).get("results") or {}
    nella_regione = fornitori.get(regione()) or {}
    elenco = nella_regione.get("flatrate") or []
    return [p.get("provider_name") for p in elenco if p.get("provider_name")]


def _scheda(voce: dict) -> dict:
    """Da una voce di TMDB alla scheda che serve alla sezione.

    Si tengono solo i campi che si mostrano, e si scarta un film senza locandina:
    e' una sezione di immagini, e una senza immagine non ispira niente.
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
        "piattaforme": _piattaforme(voce),
    }


def _scarica(_db) -> list:
    """I film del momento, ordinati per popolarita' fra i piu' apprezzati."""
    dati = _chiama("/discover/movie", {
        "sort_by": "popularity.desc",
        "watch_region": regione(),
        "with_watch_monetization_types": "flatrate",
        "vote_count.gte": 50,
        "vote_average.gte": 6.0,
        "include_adult": "false",
        "page": 1,
        "append_to_response": "watch/providers",
    })
    schede = [_scheda(v) for v in dati.get("results", [])]
    return [s for s in schede if s][:QUANTI]


def aggiorna(db, forse=True) -> bool:
    """Aggiorna la copia dei film. Non solleva mai: e' chiamata in sottofondo."""
    return tv._aggiorna(db, "cinema", ORE_CINEMA, _scarica, forse=forse)


def film(db) -> list:
    return tv._leggi(db, "cinema")[0] or []


def quando_aggiornato(db):
    return tv._leggi(db, "cinema")[1] or None
