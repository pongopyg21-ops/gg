"""TV: intrattenimento e notizie dal mondo, nella stessa sezione.

Due cose che non sono dati dell'app — una playlist YouTube e un feed di notizie
— tenute insieme perche' vivono nella stessa sezione e perche' hanno lo stesso
problema: **la rete**. Un feed si sposta, un sito cambia, e la casa puo' restare
senza connessione. La regola e' una sola e vale per entrambe: quello che si e'
gia' scaricato **resta**, e un guasto di rete non deve svuotare la sezione. Si
mostra l'ultima copia buona e si riprova piu' tardi.

Nessuna dipendenza nuova: `urllib.request` per scaricare ed `ElementTree` per
leggere i due formati (Atom per la playlist, RSS per le notizie). Sono formati
semplici, e una libreria in piu' sarebbe una cosa da aggiornare per leggere
cinque campi.

Le notizie sono **max dieci** e si rinnovano una volta al giorno: un titolo, una
riga di sommario e un rimando alla fonte, non l'articolo. Il testo e' di chi lo
scrive, e la casa non e' il posto per ricopiarlo.

Il modulo non apre database per conto suo: riceve una connessione. Cosi' non
importa `app` (che importa questo) e resta provabile da solo.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# La playlist dell'utente e il feed delle notizie. Sono due indirizzi che
# cambiano con la casa, non con il codice: si possono sostituire dall'ambiente
# senza toccare il modulo, come le chiavi dei servizi.
#
# La playlist e' "GIAGIA-Max":
#   https://www.youtube.com/playlist?list=PLQKkPe_OTLJygIqIViE5cqnWjxM1Cou0R
# Il feed Atom vuole il solo id (`list=...`), non l'indirizzo intero: l'id da
# solo e' opaco, quindi l'indirizzo completo resta qui accanto perche' si possa
# risalire a quale playlist sia.
PLAYLIST_PREDEFINITA = "PLQKkPe_OTLJygIqIViE5cqnWjxM1Cou0R"
FEED_PREDEFINITO = "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml"

# Quante notizie si tengono. Dieci e' quello che si legge davvero; oltre, la
# sezione diventa un giornale e non la si scorre piu'.
MAX_NOTIZIE = 10

# Il sommario si accorcia: la notizia e' il titolo, il resto e' un assaggio con
# il rimando alla fonte.
MAX_SOMMARIO = 180

# Una volta al giorno, come chiesto. Non a mezzanotte: a distanza dall'ultimo
# scaricamento, cosi' un server acceso solo di pomeriggio non salta mai il giro.
ORE_NOTIZIE = 24
ORE_VIDEO = 24

TIMEOUT = 10.0

# Il tetto alla risposta scaricata. Un feed e' qualche decina di kilobyte: due
# megabyte sono gia' un'anomalia, e leggerla per intero sarebbe il modo in cui
# una pagina sbagliata (o ostile) riempie la memoria del server di casa.
MAX_BYTE = 2 * 1024 * 1024

UA = "IlMaggiordomo"


class NonDisponibile(Exception):
    """La fonte non risponde o risponde male. Chi chiama serve la copia vecchia."""


def playlist_id() -> str:
    return os.environ.get("TV_PLAYLIST") or PLAYLIST_PREDEFINITA


def feed_url() -> str:
    return os.environ.get("TV_FEED") or FEED_PREDEFINITO


def _apri(url: str) -> bytes:
    """Scarica un indirizzo. Unico punto di rete: nei test si sostituisce questo.

    Il tetto si applica leggendo `MAX_BYTE + 1` byte: se ne arrivano di piu' la
    risposta si scarta, invece di leggerla tutta per poi accorgersene.
    """
    richiesta = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:
            dati = risposta.read(MAX_BYTE + 1)
    except (OSError, ValueError) as errore:
        raise NonDisponibile(f"Non raggiungo {url}") from errore
    if len(dati) > MAX_BYTE:
        raise NonDisponibile(f"Risposta troppo grande da {url}")
    return dati


def _testo(elemento, percorso, ns=None, predefinito=""):
    """Il testo di un elemento, o `predefinito` se manca.

    `ns` va passato: senza la mappa dei namespace `find` cerca un tag letterale
    ("yt:videoId") e non trova niente, quindi ogni campo tornerebbe vuoto e la
    playlist sembrerebbe senza video.
    """
    trovato = elemento.find(percorso, ns) if ns else elemento.find(percorso)
    return (trovato.text or "").strip() if trovato is not None and trovato.text else predefinito


def video_playlist() -> list:
    """I video della playlist, nell'ordine in cui sono.

    Si legge il feed Atom che YouTube espone per ogni playlist pubblica. Non si
    interpreta la pagina: quella dipende dal consenso ai cookie e dal JavaScript,
    e cambia formato — il feed no.
    """
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id()}"
    dati = _apri(url)
    try:
        radice = ET.fromstring(dati)
    except ET.ParseError as errore:
        raise NonDisponibile("La playlist non e' leggibile") from errore

    ns = {"a": "http://www.w3.org/2005/Atom",
          "yt": "http://www.youtube.com/xml/schemas/2015"}
    video = []
    for voce in radice.findall("a:entry", ns):
        vid = _testo(voce, "yt:videoId", ns)
        titolo = _testo(voce, "a:title", ns)
        if not vid or not titolo:
            continue
        video.append({
            "id": vid,
            "titolo": titolo,
            "autore": _testo(voce, "a:author/a:name", ns),
            "data": _testo(voce, "a:published", ns)[:10],
        })
    if not video:
        # Una playlist privata o cancellata risponde cosi': nessuna voce. Meglio
        # dirlo che mostrare una sezione vuota senza spiegazione.
        raise NonDisponibile("La playlist non ha video leggibili")
    return video


def _nome_fonte(titolo: str, url: str) -> str:
    """Il nome leggibile della fonte da mostrare accanto alla notizia.

    Il titolo di un feed e' fatto per un lettore di feed, non per la pagina:
    "RSS di Mondo  - ANSA.it". Accanto a una notizia ci vuole "ANSA.it", che e'
    quello che dice da dove viene. Si prende l'ultimo pezzo dopo il trattino e,
    se non c'e', si toglie il prefisso "RSS".
    """
    titolo = (titolo or "").strip()
    if " - " in titolo:
        return titolo.rsplit(" - ", 1)[1].strip()
    pulito = re.sub(r"^rss\s+(di\s+|del\s+|della\s+)?", "", titolo, flags=re.I).strip()
    if pulito:
        return pulito
    # senza un titolo utile si mostra l'indirizzo, che almeno e' vero
    return urlparse(url).netloc or "Notizie"


def notizie_dal_feed() -> list:
    """Le ultime notizie, dalla piu' recente. Al massimo `MAX_NOTIZIE`."""
    url = feed_url()
    dati = _apri(url)
    try:
        radice = ET.fromstring(dati)
    except ET.ParseError as errore:
        raise NonDisponibile("Il feed delle notizie non e' leggibile") from errore

    canale = radice.find("channel")
    if canale is None:
        raise NonDisponibile("Il feed delle notizie non ha un canale")

    fonte = _nome_fonte(_testo(canale, "title"), url)
    voci = []
    for item in canale.findall("item"):
        titolo = _testo(item, "title")
        link = _testo(item, "link")
        if not titolo or not link:
            continue
        sommario = _testo(item, "description")
        if len(sommario) > MAX_SOMMARIO:
            # si taglia sulla parola: una parola mozzata a meta' si nota subito
            sommario = sommario[:MAX_SOMMARIO].rsplit(" ", 1)[0] + "…"
        voci.append({
            "titolo": titolo,
            "link": link,
            "sommario": sommario,
            "fonte": fonte,
            "data": _data_iso(_testo(item, "pubDate")),
        })
    # il feed e' gia' in ordine, ma non ci si appoggia: una fonte che cambia
    # ordine mostrerebbe le notizie vecchie in cima
    voci.sort(key=lambda v: v["data"], reverse=True)
    return voci[:MAX_NOTIZIE]


def _data_iso(testo: str) -> str:
    """Da `Thu, 1 Oct 2026 16:58:22 +0200` a `2026-10-01T16:58:22`.

    Una data illeggibile non e' un motivo per perdere la notizia: resta vuota e
    la notizia si mostra comunque.
    """
    try:
        return parsedate_to_datetime(testo).isoformat()
    except (TypeError, ValueError):
        return ""


# ---------------------------------------------------------------- cache
# Quello che si e' scaricato sta nel database **della casa**, non in memoria: un
# riavvio del server (che qui succede spesso) non deve costringere a riscaricare,
# e soprattutto la sezione non deve restare vuota se in quel momento la rete non
# c'e'. E' la stessa idea delle copie automatiche: il dato che serve c'e' gia'.

def _leggi(db, chiave):
    try:
        riga = db.execute(
            "SELECT dati, aggiornato FROM tv_cache WHERE chiave = ?", (chiave,)).fetchone()
    except Exception:
        # la tabella non c'e' (database appena creato e non ancora migrato):
        # si comporta come "cache vuota" invece di far cadere la richiesta
        return None, 0.0
    if riga is None:
        return None, 0.0
    try:
        return json.loads(riga[0]), float(riga[1] or 0)
    except (ValueError, TypeError):
        return None, 0.0


def _scrivi(db, chiave, dati):
    db.execute(
        "INSERT INTO tv_cache (chiave, dati, aggiornato) VALUES (?, ?, ?) "
        "ON CONFLICT(chiave) DO UPDATE SET dati = excluded.dati, "
        "aggiornato = excluded.aggiornato",
        (chiave, json.dumps(dati, ensure_ascii=False), time.time()))
    db.commit()


def _fresco(quando: float, ore: float) -> bool:
    return quando > 0 and (time.time() - quando) < ore * 3600


# Un lucchetto per chiave: il giro di avvio, la richiesta della pagina e il
# pulsante «Aggiorna» possono chiedere lo stesso scaricamento insieme, e senza
# questo partirebbero due volte per la stessa cosa. Chi arriva secondo aspetta
# il primo e poi ritrova la copia fresca.
_lucchetti = {}
_lucchetti_guardia = threading.Lock()


def _lucchetto(chiave):
    with _lucchetti_guardia:
        if chiave not in _lucchetti:
            _lucchetti[chiave] = threading.Lock()
        return _lucchetti[chiave]


def _aggiorna(db, chiave, ore, scarica, forse=True):
    """Tiene la cache buona: scarica solo se serve, e mai a costo di svuotarla.

    `forse=True` (il comportamento normale) salta lo scaricamento quando la
    copia e' recente. Se lo scaricamento fallisce, **la copia vecchia resta**:
    e' l'unica cosa che non si deve perdere, perche' e' quello che permette alla
    sezione di funzionare senza rete.
    """
    with _lucchetto(chiave):
        dati, quando = _leggi(db, chiave)
        if forse and _fresco(quando, ore):
            return False
        try:
            nuovi = scarica()
        except NonDisponibile:
            # rete assente o fonte cambiata: si tiene quello che c'e' e si riprova
            # al giro dopo. Nessuna eccezione al chiamante: la sezione si apre lo
            # stesso, con i dati di ieri.
            return False
        if nuovi:
            _scrivi(db, chiave, nuovi)
            return True
        return False


def aggiorna_video(db, forse=True) -> bool:
    return _aggiorna(db, "video", ORE_VIDEO, video_playlist, forse=forse)


def aggiorna_notizie(db, forse=True) -> bool:
    return _aggiorna(db, "notizie", ORE_NOTIZIE, notizie_dal_feed, forse=forse)


def aggiorna(db, forse=True) -> dict:
    """Aggiorna entrambe le cose. Non solleva mai: e' chiamata in sottofondo."""
    return {"video": aggiorna_video(db, forse=forse),
            "notizie": aggiorna_notizie(db, forse=forse)}


def video(db) -> list:
    return _leggi(db, "video")[0] or []


def notizie(db) -> list:
    return _leggi(db, "notizie")[0] or []


def quando_aggiornate(db) -> dict:
    """Quando la copia e' stata presa, per dirlo nella sezione.

    Senza, l'utente non sa se sta guardando le notizie di oggi o quelle di una
    settimana fa quando la rete non ha risposto.
    """
    esito = {}
    for chiave in ("video", "notizie"):
        _, quando = _leggi(db, chiave)
        esito[chiave] = quando or None
    return esito


def incorpora(video_id: str) -> str:
    """L'indirizzo del player per un video.

    `youtube-nocookie` invece di `youtube`: la pagina della casa non deve
    consegnare a YouTube i cookie di chi la apre per il solo fatto di mostrare
    un video. Il player funziona identicamente.
    """
    return f"https://www.youtube-nocookie.com/embed/{video_id}"
