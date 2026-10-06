"""TV: intrattenimento e notizie dal mondo, nella stessa sezione.

Due cose che non sono dati dell'app — una playlist YouTube e un feed di notizie
— tenute insieme perche' vivono nella stessa sezione e perche' hanno lo stesso
problema: **la rete**. Un feed si sposta, un sito cambia, e la casa puo' restare
senza connessione. La regola e' una sola e vale per entrambe: quello che si e'
gia' scaricato **resta**, e un guasto di rete non deve svuotare la sezione. Si
mostra l'ultima copia buona e si riprova piu' tardi.

Vale identica per le due fonti aggiunte dopo: il **quiz** (Open Trivia DB) con
un suggerimento di cosa fare dalla **Bored API**, e le **opere d'arte** della
collezione pubblica del **Met** (Metropolitan Museum) accanto ai video. Anche
loro passano dalla cache della casa, e un guasto non le fa sparire.

Nessuna dipendenza nuova: `urllib.request` per scaricare, `ElementTree` per
leggere i due formati dei feed (Atom per la playlist, RSS per le notizie) e
`json` per il resto. Sono formati semplici, e una libreria in piu' sarebbe una
cosa da aggiornare per leggere cinque campi.

Le notizie sono **max venti**, da piu' testate (ANSA), mescolate e si rinnovano
una volta al giorno: un titolo, una riga di sommario e un rimando alla fonte,
non l'articolo. Il testo e' di chi lo scrive, e la casa non e' il posto per
ricopiarlo.

Il modulo non apre database per conto suo: riceve una connessione. Cosi' non
importa `app` (che importa questo) e resta provabile da solo.
"""
from __future__ import annotations

import html
import json
import os
import random
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# La playlist di partenza e il feed delle notizie. Sono due indirizzi che
# cambiano con la casa, non con il codice: si possono sostituire dall'ambiente
# senza toccare il modulo, come le chiavi dei servizi.
#
# La playlist vera la sceglie la casa (tabella `tv_prefs`): all'ambiente resta
# il ruolo di **predefinita** per le case che non l'hanno ancora scelta, cosi'
# un'installazione esistente continua a funzionare senza toccare niente.
#
# La playlist e' "GIAGIA-Max":
#   https://www.youtube.com/playlist?list=PLQKkPe_OTLJygIqIViE5cqnWjxM1Cou0R
# Il feed Atom vuole il solo id (`list=...`), non l'indirizzo intero: l'id da
# solo e' opaco, quindi l'indirizzo completo resta qui accanto perche' si possa
# risalire a quale playlist sia.
PLAYLIST_PREDEFINITA = "PLQKkPe_OTLJygIqIViE5cqnWjxM1Cou0R"

# La playlist della sezione GYM: gli esercizi, separata dalla TV perche' e' una
# cosa diversa — si guarda per fare, non per passare il tempo — e perche' cosi'
# cambiare i video di casa non tocca l'allenamento. Stessa forma della TV: si
# puo' sostituire da `GYM_PLAYLIST` senza toccare il modulo.
PLAYLIST_GYM_PREDEFINITA = "PLQKkPe_OTLJzyy8sW19hxUvVgnk1GuYFo"
# Le notizie vengono dalle sezioni ANSA: il mondo da solo lascia fuori quello
# che succede in Italia, che e' la prima cosa che si guarda. Le sezioni sono
# argomenti, non fonti diverse: tutte ANSA, tutte in italiano. Ognuna ha una
# chiave stabile, cosi' la scelta dell'utente (`profile.news_topics`) non dipende
# dall'indirizzo del feed, che cambia.
FEED_PER_TEMA = {
    "mondo": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml",
    "cronaca": "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml",
    "politica": "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
    "economia": "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
}
FEED_PREDEFINITI = tuple(FEED_PER_TEMA.values())

# Le etichette degli argomenti, per l'onboarding e il Profilo. La chiave e'
# quella salvata in `news_topics`; l'etichetta e' quello che l'utente legge.
ARGOMENTI = [
    {"key": "mondo", "label": "Mondo"},
    {"key": "cronaca", "label": "Cronaca e Italia"},
    {"key": "politica", "label": "Politica"},
    {"key": "economia", "label": "Economia"},
]

# Quante notizie si tengono. Venti: dieci riempiono la prima schermata e il
# resto si scorre, ma il taglio non e' piu' cosi' stretto che una testata sola
# lo occupi tutto — con piu' fonti le notizie si alternano, e alternandosi ne
# servono di piu' perche' ognuna ne porti abbastanza.
MAX_NOTIZIE = 20

# Quante voci puo' portare un singolo feed al totale. Senza, un feed
# generalista riempirebbe da solo le notizie e le altre sezioni sparirebbero:
# le fonti si mescolano, non si sostituiscono.
MAX_PER_FEED = 10

# Tetto ai feed dichiarati: con `TV_FEED` se ne possono indicare altri, ma non
# un numero che moltiplichi le richieste a un sito altrui a ogni aggiornamento.
MAX_FEED = 12

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

# Il quiz: un servizio pubblico che da' contenuto pronto da leggere, non un
# elenco di dati della casa. Non e' della stessa natura delle notizie, ma vive
# nella stessa sezione e ha lo stesso problema — la rete — quindi segue la stessa
# regola: quello che si e' scaricato resta, e un guasto non svuota la sezione.
QUIZ_URL = os.environ.get(
    "TV_QUIZ", "https://opentdb.com/api.php?amount=10&difficulty=medium")
# Ogni quanto si rinnova: piu' spesso delle notizie, perche' e' un contenuto
# leggero e dieci domande gia' viste non divertono due volte.
ORE_EXTRA = 6
# La traduzione automatica delle domande. Open Trivia DB **non ha contenuti in
# italiano** (ignora `lang=it`): le domande arrivano in inglese, quindi si
# traducono con un servizio pubblico senza chiave (MyMemory). La traduzione e'
# un di piu': se non riesce, le domande restano in inglese e la sezione funziona
# lo stesso. `TV_TRADUZIONE` vuoto spegne la traduzione.
TRADUZIONE_URL = os.environ.get(
    "TV_TRADUZIONE", "https://api.mymemory.translated.net/get")
# La difficolta' e' una parola sola: si mappa invece di tradurla, cosi' non
# dipende dal servizio e non costa una richiesta.
DIFFICOLTA_IT = {"easy": "facile", "medium": "medio", "hard": "difficile"}

# --- Un suggerimento di cosa fare (Bored API) ------------------------------
# Nella scheda Quiz, sotto le domande, un'idea di cosa fare quando ci si annoia:
# e' il pubblico della Bored API (`bored-api.appbrewery.com`), un servizio
# pubblico senza chiave. La risposta e' in inglese, quindi passa dalla stessa
# traduzione delle domande; i campi strutturati (quanti partecipanti, se adatto
# ai bambini) si mostrano cosi' come sono.
#
# L'indirizzo base si puo' sostituire da `TV_BORED` senza toccare il modulo,
# come le altre fonti.
BORED_BASE = os.environ.get(
    "TV_BORED", "https://bored-api.appbrewery.com")
# Il tipo di attivita' che si accetta. La Bored API ne offre nove; quelle
# "cerebrali" (busywork, education, diy, charity) non sono un passatempo da
# mostrare a casa, e i tipi strambi — "relaxation", "cooking" — non sono
# affidabili. Si tengono i tre che sono davvero qualcosa da fare insieme o per
# svago.
#
# Si chiede **`/filter?type=`** e non `/random`: `/random` non accetta un filtro
# per tipo e restituisce spesso un tipo scartato, quindi con `/random` la meta'
# dei tentativi andrebbe buttata. `/filter` restituisce solo il tipo chiesto,
# quindi ogni risposta e' buona.
BORED_TIPI = ("recreational", "social", "music")
# Quanti tipi provare, se uno non risponde o non da' niente di usabile. Ogni
# tentativo e' una richiesta breve.
BORED_TENTATIVI = 4
# L'attivita' si rinnova spesso: e' un suggerimento, non una notizia.
ORE_BORED = 1

# --- Opere d'arte (Metropolitan Museum) ------------------------------------
# Nella scheda Intrattenimento, accanto ai video di casa, qualche opera della
# collezione pubblica del Met: e' una pausa di gusto fra un video e l'altro, non
# un catalogo da sfogliare. Il servizio e' pubblico e senza chiave.
#
# La ricerca (`/search`) e' passata a **v1.1** il 2026-10-01: la v1 risponde
# 410 con l'indicazione di usare la nuova, che e' paginata con `offset`/`limit`.
# Il dettaglio dell'opera resta su **v1** (`/objects/{id}`): sono due versioni
# diverse dello stesso servizio, e usarne una sola per tutto non funziona.
MET_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"
MET_RICERCA = MET_BASE + ".1/search"
# Il tema della ricerca. `q=painting` con `isHighlight=true` porta i dipinti
# scelti dagli editori del museo: sono i piu' riconoscibili, che e' quello che
# serve accanto ai video. `hasImages=true` esclude le opere senza foto, che in
# una striscia di immagini non si possono mostrare.
#
# `departmentId=11` e' il dipartimento **European Paintings**: senza, `painting`
# pesca anche un manuale a stampa e le pitture murali di Pompei — bei pezzi, ma
# un libro in una striscia di quadri non c'entra. E' il dipartimento dei quadri
# che si riconoscono, ed e' quello che ci si aspetta accanto ai video.
MET_QUERY = "painting"
MET_HIGHLIGHT = "true"
MET_DIPARTIMENTO = "11"
# Quante opere tenere, e il tetto ai dettagli chiesti: la ricerca puo' elencare
# centinaia di id, ma ogni opera e' una chiamata a parte e il tetto tiene basso
# il lavoro. Si chiede solo il necessario a riempire le opere tenute.
#
# `MET_MAX_DETTAGLI` e' piu' largo di `MET_QUANTE` perche' il gruppo si sceglie
# **a caso** fra i candidati: cosi' due giri danno gruppi diversi, e il pulsante
# «Altre opere» puo' saltare quelle gia' mostrate senza restare senza candidati.
MET_QUANTE = 12
MET_MAX_DETTAGLI = 60
# Le opere d'arte non cambiano: si rinnovano una volta al giorno come i video.
ORE_ARTE = 24

UA = "IlMaggiordomo"


class NonDisponibile(Exception):
    """La fonte non risponde o risponde male. Chi chiama serve la copia vecchia."""


def normalizza_playlist(valore: str) -> str:
    """Estrae e valida l'id di una playlist da quello che l'utente ha incollato.

    Nessuno incolla `PLQKkPe...`: si incolla l'indirizzo della barra del
    browser, o un indirizzo con altri parametri dentro. L'id e' il valore di
    `list=`, l'unica cosa che il feed Atom accetta; restituirlo sbagliato vuol
    dire una sezione vuota senza spiegazione, quindi si accettano le forme note
    e per il resto si prende il testo cosi' com'e' (potrebbe gia' essere un id).

    Solleva `ValueError` se non si capisce.
    """
    valore = (valore or "").strip()
    if not valore:
        return ""
    m = re.search(r"[?&]list=([A-Za-z0-9_-]+)", valore)
    if m:
        return m.group(1)
    if re.match(r"^https?://", valore):
        # un indirizzo senza `list=`: e' un video, un canale o una pagina, non
        # una playlist — meglio dirlo che costruire un feed che non esiste
        raise ValueError("Nell'indirizzo non c'è una playlist (manca «list=»)")
    # gia' un id: gli id di YouTube sono alfanumerici con `-` e `_`
    if re.fullmatch(r"[A-Za-z0-9_-]{10,60}", valore):
        return valore
    raise ValueError("Playlist non riconosciuta: incolla l'indirizzo o l'id")


def playlist_id(db=None) -> str:
    """L'id della playlist della casa.

    L'ordine: quello **scelto dalla casa** (`tv_prefs`), poi `TV_PLAYLIST`
    dall'ambiente, poi la predefinita. La casa viene prima dell'ambiente perche'
    e' una scelta dell'utente, e l'ambiente e' il valore di partenza per chi non
    ha ancora scelto.
    """
    scelta = _playlist_salvata(db)
    return scelta or os.environ.get("TV_PLAYLIST") or PLAYLIST_PREDEFINITA


def _playlist_salvata(db) -> str:
    if db is None:
        return ""
    try:
        riga = db.execute("SELECT playlist FROM tv_prefs WHERE id = 1").fetchone()
    except Exception:
        # tabella assente (database non ancora migrato): si ricade sui valori
        # di partenza invece di far cadere la richiesta
        return ""
    if riga is None:
        return ""
    valore = riga[0] if not hasattr(riga, "keys") else riga["playlist"]
    return (valore or "").strip()


def imposta_playlist(db, valore: str) -> str:
    """Salva la playlist scelta dalla casa e azzera la copia dei video.

    L'id si valida **prima** di salvarlo: una playlist storta salvata sarebbe
    una sezione vuota che non si capisce da dove venga. La cache si azzera
    perche' i video di prima sono di un'altra playlist: tenerli mostrerebbe la
    scelta vecchia fino al prossimo giro, e `aggiorna` li salta perche' la copia
    e' ancora fresca.
    """
    scelto = normalizza_playlist(valore)
    db.execute(
        "INSERT INTO tv_prefs (id, playlist) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET playlist = excluded.playlist", (scelto,))
    db.execute("DELETE FROM tv_cache WHERE chiave = 'video'")
    db.commit()
    return scelto


def argomenti_scelti(valore) -> list:
    """Gli argomenti delle notizie scelti dall'utente, in chiavi valide.

    Si accetta testo separato da virgole o una lista, e si tengono solo le chiavi
    note: un argomento sconosciuto (o un refuso) non deve svuotare le notizie.
    Una lista **vuota** e' legittima e significa "tutti gli argomenti" — e' il
    caso di chi non ha ancora scelto, e non si vuole una sezione vuota.
    """
    if isinstance(valore, (list, tuple)):
        parti = [str(p) for p in valore]
    else:
        parti = re.split(r"[,;\n]+", str(valore or ""))
    visti = []
    for parte in parti:
        chiave = parte.strip().lower()
        if chiave in FEED_PER_TEMA and chiave not in visti:
            visti.append(chiave)
    return visti


def feed_urls(db=None) -> list:
    """Gli indirizzi dei feed delle notizie, in ordine.

    `TV_FEED` ne puo' indicare piu' d'uno separati da virgola o da a capo, cosi'
    si sostituiscono i predefiniti senza toccare il modulo (come `TV_PLAYLIST`).
    Senza `TV_FEED` si usano le sezioni ANSA predefinite, ristrette a quelle
    scelte dalla casa: gli argomenti dichiarati in `profile.news_topics` (vuoto =
    tutti), cosi' le notizie che non interessano non occupano l'elenco.
    """
    dichiarati = os.environ.get("TV_FEED", "").strip()
    if dichiarati:
        urls = [u.strip() for u in re.split(r"[,\n]", dichiarati) if u.strip()]
        return urls[:MAX_FEED]
    scelti = _argomenti_dal_db(db)
    if scelti:
        return [FEED_PER_TEMA[k] for k in scelti][:MAX_FEED]
    return list(FEED_PREDEFINITI)[:MAX_FEED]


def _argomenti_dal_db(db) -> list:
    """Gli argomenti delle notizie scelti dalla casa, se c'e' un database.

    Il modulo non apre database per conto suo: la lettura e' tollerante, perche'
    `feed_urls` viene chiamata anche senza una connessione (i test, la prima
    installazione) e un profilo assente non deve impedire di scaricare.
    """
    if db is None:
        return []
    try:
        riga = db.execute("SELECT news_topics FROM profile WHERE id = 1").fetchone()
    except Exception:
        return []
    if riga is None:
        return []
    return argomenti_scelti(riga[0])


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


def video_playlist(db=None) -> list:
    """I video della playlist della casa, nell'ordine in cui sono.

    Si legge il feed Atom che YouTube espone per ogni playlist pubblica. Non si
    interpreta la pagina: quella dipende dal consenso ai cookie e dal JavaScript,
    e cambia formato — il feed no.

    L'id lo risolve `playlist_id(db)`: la playlist della casa, se c'e'.
    """
    return _video_di(playlist_id(db))


def _video_di(playlist: str) -> list:
    """I video di una playlist, dato il suo id.

    E' il pezzo comune fra TV e GYM: cambia solo quale playlist si legge. Il
    messaggio di errore dice l'id, cosi' un feed storto si riconosce dal log
    invece di sembrare un guasto generico.
    """
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist}"
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
        raise NonDisponibile(f"La playlist {playlist} non ha video leggibili")
    return video


def video_gym(db=None) -> list:
    """I video della playlist GYM.

    Stessa lettura della TV (`_video_di`), playlist diversa: gli esercizi non
    devono seguire i cambi della TV, e viceversa.
    """
    return _video_di(gym_playlist_id(db))


def gym_playlist_id(db=None) -> str:
    """L'id della playlist GYM.

    L'ordine e' quello della TV: prima la scelta della casa (`tv_prefs`), poi
    `GYM_PLAYLIST` dall'ambiente, poi la predefinita. La scelta sta in una
    colonna **sua** (`gym_playlist`), non in quella della TV: cambiare i video
    di casa non deve toccare l'allenamento, ne' viceversa.
    """
    return (_playlist_gym_salvata(db) or os.environ.get("GYM_PLAYLIST")
            or PLAYLIST_GYM_PREDEFINITA)


def _playlist_gym_salvata(db) -> str:
    """La playlist GYM scelta dalla casa, se c'e'.

    Tollerante come `_playlist_salvata`: una colonna assente (database non
    ancora migrato) si comporta come nessuna scelta, invece di far cadere la
    sezione.
    """
    if db is None:
        return ""
    try:
        riga = db.execute("SELECT gym_playlist FROM tv_prefs WHERE id = 1").fetchone()
    except Exception:
        return ""
    if riga is None:
        return ""
    valore = riga[0] if not hasattr(riga, "keys") else riga["gym_playlist"]
    return (valore or "").strip()


def imposta_playlist_gym(db, valore: str) -> str:
    """Salva la playlist GYM scelta dalla casa e azzera la copia dei suoi video.

    Stessa regola di `imposta_playlist`, ma sulla colonna e sulla cache del GYM:
    l'id si valida **prima** di salvarlo, e si azzera solo `gym`, cosi' la TV
    non si tocca. La riga di `tv_prefs` e' una sola (id = 1): si crea se manca,
    altrimenti si aggiorna la sola colonna del GYM.
    """
    scelto = normalizza_playlist(valore)
    db.execute(
        "INSERT INTO tv_prefs (id, gym_playlist) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET gym_playlist = excluded.gym_playlist",
        (scelto,))
    db.execute("DELETE FROM tv_cache WHERE chiave = 'gym'")
    db.commit()
    return scelto


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


def _voci_del_feed(url: str) -> list:
    """Le notizie di **un** feed, con la fonte gia' risolta.

    Un feed che non risponde o non si legge solleva `NonDisponibile`: chi chiama
    lo salta e tiene gli altri, perche' le sezioni sono indipendenti e una ferma
    non deve svuotare le altre.
    """
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
    return voci


def _chiave_titolo(titolo: str) -> str:
    """La chiave di confronto di un titolo, per i quasi-doppioni.

    Lo stesso fatto esce in piu' sezioni con titoli che differiscono per un
    dettaglio minimo: "Giuseppe Graviano: 'Mio nonno...'" e "Giuseppe Graviano,
    'mio nonno...'". Il link cambia, il titolo no: si confronta il titolo
    ridotto a lettere minuscole e spazi, senza punteggiatura. Non e' la stessa
    cosa del link — quello prende i doppioni identici, questa i titoli uguali a
    meno di virgolette e trattini.
    """
    return re.sub(r"[^a-z0-9 ]", "", (titolo or "").lower()).strip()


def _ordina_per_data(voci: list) -> list:
    """Dalla piu' recente. Una data vuota (illeggibile) finisce in fondo, non in
    cima: senza data una notizia non e' «nuova», e' solo senza data."""
    return sorted(voci, key=lambda v: v["data"] or "", reverse=True)


def _mescola_per_fonte(voci: list) -> list:
    """Alterna le testate, partendo dalla notizia piu' recente.

    Un elenco ordinato solo per data puo' diventare una testata sola, quando una
    pubblica molto piu' spesso delle altre. Qui si prende a turno la notizia piu'
    recente di ogni testata, cosi' le fonti si alternano, e dentro ogni testata
    l'ordine resta per data.
    """
    per_fonte = {}
    for voce in _ordina_per_data(voci):
        per_fonte.setdefault(voce["fonte"], []).append(voce)
    gruppi = list(per_fonte.values())
    totale = sum(len(g) for g in gruppi)
    miste = []
    while len(miste) < totale:
        for gruppo in gruppi:
            if gruppo:
                miste.append(gruppo.pop(0))
    return miste


def notizie_dal_feed(db=None) -> list:
    """Le ultime notizie, mescolate fra le testate, dalla piu' recente.

    Al massimo `MAX_NOTIZIE`. Un feed fermo non ferma gli altri: si tiene quello
    che si e' letto, e solo se **nessuno** risponde si solleva `NonDisponibile`,
    cosi' la cache buona non viene sovrascritta con il vuoto.

    Ogni feed porta al massimo `MAX_PER_FEED` voci e ogni **testata** una fetta
    del totale: un generalista pubblica decine di notizie e senza tetto
    occuperebbe da solo l'elenco, facendo sparire le sezioni. Cosi' invece le
    fonti convivono e si alternano (`_mescola_per_fonte`).
    """
    voci = []
    letti = 0
    for url in feed_urls(db):
        try:
            voci.extend(_voci_del_feed(url)[:MAX_PER_FEED])
            letti += 1
        except NonDisponibile:
            continue
    if not letti:
        raise NonDisponibile("Nessun feed delle notizie risponde")

    # lo stesso fatto compare in piu' sezioni, con lo stesso link o con titoli
    # che differiscono di poco: due chiavi, e tenere due volte la stessa notizia
    # occuperebbe il posto di un'altra che si sarebbe letta
    visti_link = set()
    visti_titoli = set()
    uniche = []
    for voce in voci:
        chiave = _chiave_titolo(voce["titolo"])
        if voce["link"] in visti_link or (chiave and chiave in visti_titoli):
            continue
        visti_link.add(voce["link"])
        if chiave:
            visti_titoli.add(chiave)
        uniche.append(voce)

    # Si scelgono prima le piu' recenti, poi si taglia per testata: il tetto per
    # feed non basta, perche' una testata con piu' sezioni (ANSA ne ha quattro)
    # porta voci recenti piu' numerose delle altre e occuperebbe comunque
    # l'elenco. La fetta per testata e' **proporzionale al numero di testate** —
    # con una sola fonte non si taglia niente, con due si fa meta' per uno —
    # cosi' le fonti convivono anche quando una pubblica molto piu' spesso
    # dell'altra.
    testate = {v["fonte"] for v in uniche}
    tetto = max(1, MAX_NOTIZIE // len(testate)) if testate else MAX_NOTIZIE
    per_testata = {}
    scelte = []
    for voce in _ordina_per_data(uniche):
        fonte = voce["fonte"]
        if per_testata.get(fonte, 0) >= tetto:
            continue
        per_testata[fonte] = per_testata.get(fonte, 0) + 1
        scelte.append(voce)

    return _mescola_per_fonte(scelte)[:MAX_NOTIZIE]


# ------------------------------------------------------------------ quiz
# Una fonte diversa dalle notizie, letta allo stesso modo: si scarica un JSON e
# si tiene solo cio' che serve. Vale la stessa regola di tutto il modulo: se la
# risposta non e' quella che ci si aspetta si solleva `NonDisponibile`, cosi' la
# copia vecchia resta e la sezione non si svuota per un guasto di rete.

def _json(url: str):
    """Scarica e interpreta una risposta JSON.

    `_apri` resta l'unico punto di rete (e' quello che si sostituisce nei test);
    qui si aggiunge solo la lettura del JSON, che un feed XML non ha.
    """
    try:
        return json.loads(_apri(url).decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError) as errore:
        raise NonDisponibile(f"Risposta non leggibile da {url}") from errore


def _pulisci(testo) -> str:
    """Il testo di una domanda, senza entita' HTML.

    Open Trivia DB manda `&quot;` e `&#039;`: senza `unescape` la domanda si
    legge con i codici in mezzo.
    """
    return html.unescape(str(testo or "")).strip()


def _traduci(testo: str) -> str:
    """Traduce una stringa dall'inglese all'italiano con un servizio pubblico.

    Ritorna la stringa vuota se la traduzione non riesce: chi chiama la ignora e
    tiene l'originale. Non e' un errore, e' la rete che non c'e' — la sezione
    deve funzionare lo stesso.
    """
    if not TRADUZIONE_URL or not testo.strip():
        return ""
    url = TRADUZIONE_URL + "?" + urllib.parse.urlencode(
        {"q": testo, "langpair": "en|it"})
    try:
        dati = _json(url)
    except NonDisponibile:
        return ""
    if not isinstance(dati, dict):
        return ""
    tradotto = (dati.get("responseData") or {}).get("translatedText") or ""
    return str(tradotto).strip()


def _mescola_risposte(domanda: dict) -> list:
    """Le risposte possibili mescolate, cosi' quella giusta non e' sempre prima.

    Open Trivia DB mette la risposta giusta in un campo a parte: senza mescolare
    sarebbe sempre la prima e il quiz si indovinerebbe senza sapere. La risposta
    giusta resta segnata con `giusta`, che il client usa per dire se si e'
    indovinato.
    """
    giusta = _pulisci(domanda.get("correct_answer"))
    sbagliate = [_pulisci(a) for a in (domanda.get("incorrect_answers") or [])]
    risposte = [{"testo": giusta, "giusta": True}]
    risposte += [{"testo": a, "giusta": False} for a in sbagliate if a]
    random.shuffle(risposte)
    return risposte


def _traduci_domande(domande: list) -> list:
    """Traduce in italiano domanda, risposte e categoria, una domanda per volta.

    Si manda un blocco di righe (domanda, poi le risposte, poi la categoria) e il
    servizio conserva i ritorni a capo, quindi le righe restano allineate. Si
    controlla comunque che il numero di righe torni: se il servizio le
    accorpasse, si tiene l'inglese invece di rimescolare le risposte.

    La traduzione e' **per domanda**, non per l'intero elenco: il servizio
    tronca i testi lunghi, e un blocco unico perderebbe le domande in fondo.
    Il campo `giusta` resta al suo posto: si cambiano solo i testi.
    """
    tradotte = []
    for d in domande:
        risposte = d.get("risposte") or []
        righe = [d["testo"]] + [r["testo"] for r in risposte] + [d.get("categoria", "")]
        fuori = _traduci("\n".join(righe))
        parti = fuori.split("\n") if fuori else []
        if len(parti) != len(righe):
            tradotte.append(d)  # traduzione inaffidabile: resta l'inglese
            continue
        nuova = dict(d)
        nuova["testo"] = parti[0].strip() or d["testo"]
        nuova["risposte"] = [
            {**r, "testo": parti[i + 1].strip() or r["testo"]}
            for i, r in enumerate(risposte)
        ]
        if d.get("categoria"):
            nuova["categoria"] = parti[-1].strip() or d["categoria"]
        tradotte.append(nuova)
    return tradotte


def quiz_dal_servizio(db=None, quanti=10) -> list:
    """Le domande del quiz, cosi' come le da' Open Trivia DB.

    `response_code` diverso da zero vuol dire "nessuna domanda" (il servizio usa
    5 per il vuoto, 1 per parametri storti): si solleva `NonDisponibile` e la
    copia vecchia resta, invece di sovrascriverla con un elenco vuoto.

    `quanti` e' il numero di domande: la copia ne tiene dieci, le domande di
    riserva che si accodano quando si indovina ne prendono altre.
    """
    return _interpreta_quiz(_json(_url_quiz(quanti)))


def _url_quiz(quanti: int) -> str:
    """L'indirizzo del quiz con `amount` impostato, mantenendo gli altri
    parametri (la difficolta') e **l'ordine** di `QUIZ_URL`: cosi' i test che
    sostituiscono l'indirizzo continuano a riconoscerlo."""
    parti = urllib.parse.urlsplit(QUIZ_URL)
    query = [(k, (str(quanti) if k == "amount" else v))
             for (k, v) in urllib.parse.parse_qsl(parti.query)]
    if not any(k == "amount" for k, _ in query):
        query.append(("amount", str(quanti)))
    return urllib.parse.urlunsplit(parti._replace(query=urllib.parse.urlencode(query)))


def _interpreta_quiz(dati) -> list:
    """Da una risposta JSON di Open Trivia DB all'elenco delle domande."""
    if not isinstance(dati, dict) or dati.get("response_code") != 0:
        raise NonDisponibile("Il servizio del quiz non ha domande")
    voci = [v for v in (_mescola_una(d) for d in (dati.get("results") or [])) if v]
    if not voci:
        raise NonDisponibile("Il servizio del quiz non ha dato domande")
    return _traduci_domande(voci)


def _mescola_una(d) -> dict | None:
    """Una domanda del servizio nella forma della copia, o `None` se non valida.

    Una domanda senza testo o con meno di due risposte non e' un guasto: si
    scarta, come fa `_interpreta_quiz`. La risposta giusta resta segnata con
    `giusta` (vedi `_mescola_risposte`).
    """
    if not isinstance(d, dict):
        return None
    testo = _pulisci(d.get("question"))
    risposte = _mescola_risposte(d)
    if not testo or len(risposte) < 2:
        return None
    difficolta = _pulisci(d.get("difficulty")).lower()
    return {"testo": testo, "risposte": risposte,
            "categoria": _pulisci(d.get("category")),
            "difficolta": DIFFICOLTA_IT.get(difficolta, difficolta)}


# ------------------------------------------------------- suggerimento (Bored)
# Un'idea di cosa fare, per la scheda Quiz. E' una fonte diversa dalle domande,
# letta allo stesso modo: si scarica un JSON e si tiene solo cio' che serve.

# Le etichette italiane dei campi strutturati. Si mappano invece di tradurle:
# sono valori chiusi, non frasi, quindi non vale una richiesta di rete — la
# stessa scelta di `DIFFICOLTA_IT`.
TIPI_IT = {"recreational": "svago", "social": "in compagnia", "music": "musica"}
ACCESSIBILITA_IT = {
    "Few to no challenges": "Poche difficolta'",
    "Minor challenges": "Qualche difficolta'",
    "Major challenges": "Impegnativa",
}


def _intero(valore, predefinito=1) -> int:
    try:
        return int(valore)
    except (TypeError, ValueError):
        return predefinito


def _decimale(valore, predefinito=0.0) -> float:
    try:
        return float(valore)
    except (TypeError, ValueError):
        return predefinito


def _suggerimento(dati) -> dict | None:
    """Da una risposta della Bored API al suggerimento, o `None` se non va bene.

    Un'attivita' di un tipo che non si vuole mostrare, o senza testo, non e' un
    guasto: si scarta e si passa al tipo successivo (vedi
    `suggerimento_dal_servizio`). Il campo `type` e' l'unico obbligatorio: il
    resto si mostra se c'e'. I numeri si convertono con cautela: un campo non
    numerico non deve far cadere l'aggiornamento (sarebbe un errore in un filo
    di sottofondo, dove non lo si vede).
    """
    if not isinstance(dati, dict):
        return None
    attivita = _pulisci(dati.get("activity"))
    tipo = _pulisci(dati.get("type")).lower()
    if not attivita or tipo not in BORED_TIPI:
        return None
    return {
        "attivita": attivita,
        "tipo": TIPI_IT.get(tipo, tipo),
        "partecipanti": _intero(dati.get("participants")),
        "accessibilita": ACCESSIBILITA_IT.get(_pulisci(dati.get("accessibility")),
                                              _pulisci(dati.get("accessibility"))),
        "bambini": bool(dati.get("kidFriendly")),
        "prezzo": _decimale(dati.get("price")),
        "link": _pulisci(dati.get("link")),
        "chiave": _pulisci(dati.get("key")),
    }


def _url_bored(tipo: str) -> str:
    """L'indirizzo della Bored API per un tipo di attivita'."""
    return f"{BORED_BASE}/filter?{urllib.parse.urlencode({'type': tipo})}"


def suggerimento_dal_servizio() -> dict:
    """Un suggerimento dalla Bored API, tradotto in italiano.

    Si chiede `/filter?type=` per un tipo che si vuole mostrare e si sceglie una
    voce a caso fra quelle. `/random` restituirebbe spesso un tipo scartato (le
    attivita' "cerebrali", di cui non si vuole mostrare niente), quindi la meta'
    dei tentativi andrebbe buttata. Se un tipo non risponde si passa al
    successivo; se nessuno risponde si solleva `NonDisponibile`, e la copia
    vecchia resta, come per ogni altra fonte. La traduzione e' un di piu' (come
    per le domande): se non riesce, il suggerimento resta in inglese e si mostra
    lo stesso.
    """
    tipi = list(BORED_TIPI)
    random.shuffle(tipi)
    for tipo in tipi[:max(1, BORED_TENTATIVI)]:
        try:
            dati = _json(_url_bored(tipo))
        except NonDisponibile:
            continue
        if not isinstance(dati, list) or not dati:
            continue
        scelto = _suggerimento(random.choice(dati))
        if not scelto:
            continue
        tradotto = _traduci(scelto["attivita"])
        if tradotto:
            scelto["attivita"] = tradotto
        return scelto
    raise NonDisponibile("La Bored API non ha dato un'attivita' adatta")


def aggiorna_suggerimento(db, forse=True) -> bool:
    return _aggiorna(db, "suggerimento", ORE_BORED,
                     lambda _db: suggerimento_dal_servizio(), forse=forse)


def suggerimento(db) -> dict:
    return _leggi(db, "suggerimento")[0] or {}


# --------------------------------------------------- opere d'arte (Met Museum)
# Qualche opera della collezione pubblica del Metropolitan Museum, accanto ai
# video di casa. Due chiamate: la ricerca (che da' gli id) e il dettaglio di
# ogni opera (che da' titolo, autore, data e foto). La ricerca e' su **v1.1**,
# il dettaglio su **v1**: sono due versioni diverse dello stesso servizio.

def _opere_id() -> list:
    """Gli id delle opere da mostrare: i dipinti scelti dal museo, con foto."""
    parametri = {
        "isHighlight": MET_HIGHLIGHT,
        "hasImages": "true",
        "q": MET_QUERY,
        "departmentId": MET_DIPARTIMENTO,
        "limit": str(MET_MAX_DETTAGLI),
    }
    dati = _json(f"{MET_RICERCA}?{urllib.parse.urlencode(parametri)}")
    if not isinstance(dati, dict):
        raise NonDisponibile("La ricerca del Met non e' leggibile")
    return [i for i in (dati.get("objectIDs") or []) if isinstance(i, int)]


def _opera(id_opera) -> dict | None:
    """Una singola opera, nella forma della copia, o `None` se non si mostra.

    Si tiene solo cio' che e' **pubblico dominio** e ha una foto: un'immagine di
    un'opera ancora coperta da diritto d'autore non si ridistribuisce, e in una
    striscia di immagini un'opera senza foto non si puo' mostrare. Il resto si
    scarta in silenzio: non e' un guasto, e' il criterio.
    """
    try:
        dati = _json(f"{MET_BASE}/objects/{id_opera}")
    except NonDisponibile:
        return None
    if not isinstance(dati, dict):
        return None
    titolo = _pulisci(dati.get("title"))
    foto = _pulisci(dati.get("primaryImageSmall")) or _pulisci(dati.get("primaryImage"))
    grande = _pulisci(dati.get("primaryImage")) or foto
    if not titolo or not foto or not dati.get("isPublicDomain"):
        return None
    return {
        "id": dati.get("objectID"),
        "titolo": titolo,
        "autore": _pulisci(dati.get("artistDisplayName")),
        "data": _pulisci(dati.get("objectDate")),
        "tecnica": _pulisci(dati.get("medium")),
        "museo": _pulisci(dati.get("department")),
        "foto": foto,
        # la foto grande serve all'ingrandimento: si mostra in una finestra a
        # schermo intero, e li' la misura `web-large` (~600 px) non basta. Si
        # scarica **solo al clic**, quindi non pesa sull'apertura della sezione.
        "foto_grande": grande,
        "link": _pulisci(dati.get("objectURL")),
    }


def _gruppo(id_opere: list, quante: int, escludi: set) -> list:
    """Da un elenco di id a un gruppo di opere, saltando quelle da escludere.

    Si chiedono i dettagli **a caso** fra i candidati, cosi' due giri danno
    gruppi diversi: e' quello che rende utile il pulsante «Altre opere». Se
    scartandone troppe non si arriva a `quante`, ci si ferma con quello che c'e'
    (un gruppo piu' corto e' meglio di nessun gruppo).
    """
    candidati = [i for i in id_opere if i not in escludi]
    random.shuffle(candidati)
    tenute = []
    for id_opera in candidati:
        if len(tenute) >= quante:
            break
        opera = _opera(id_opera)
        if opera:
            tenute.append(opera)
    return tenute


def arte_dal_servizio(escludi=None) -> list:
    """Le opere da mostrare: pubblico dominio, con foto, fino a `MET_QUANTE`.

    Il dettaglio si chiede solo finche' non si sono riempite le opere tenute:
    la ricerca puo' elencare centinaia di id, e chiederli tutti sarebbe centinaia
    di richieste per mostrarne dodici. Il tetto `MET_MAX_DETTAGLI` limita anche
    il caso in cui molte opere vengano scartate.

    `escludi` sono gli id gia' mostrati: il pulsante «Altre opere» li passa per
    non ripescare le stesse. Se il filtro svuota i candidati, si ripiega su
    tutti: meglio ripetere un'opera che non darne nessuna.
    """
    id_opere = _opere_id()[:MET_MAX_DETTAGLI]
    if not id_opere:
        raise NonDisponibile("Il Met non ha dato opere")
    tenute = _gruppo(id_opere, MET_QUANTE, set(escludi or ()))
    if not tenute and escludi:
        tenute = _gruppo(id_opere, MET_QUANTE, set())
    if not tenute:
        raise NonDisponibile("Nessuna opera del Met mostrabile")
    return tenute


def aggiorna_arte(db, forse=True) -> bool:
    return _aggiorna(db, "arte", ORE_ARTE, lambda _db: arte_dal_servizio(), forse=forse)


def arte(db) -> list:
    return _leggi(db, "arte")[0] or []


def altre_arte(db) -> list:
    """Un gruppo **nuovo** di opere, diverse da quelle in copia, e lo salva.

    E' il pulsante «Altre opere»: si genera un gruppo saltando gli id gia'
    mostrati, cosi' il pulsante porta davvero qualcosa di nuovo invece di
    ripescare le stesse. Il gruppo nuovo **sostituisce** la copia: ricaricando
    la pagina si rivedono le stesse opere, non quelle di prima. Non passa da
    `_aggiorna` (che salta lo scaricamento se la copia e' fresca): qui l'utente
    ha **chiesto** opere nuove, quindi si scarica subito.

    Solleva `NonDisponibile` se non si ottiene niente: la copia vecchia resta,
    e chi chiama risponde con quello che c'era invece di svuotare il riquadro.
    """
    with _lucchetto("arte"):
        attuali = {o.get("id") for o in arte(db)}
        nuove = arte_dal_servizio(escludi=attuali)
        _scrivi(db, "arte", nuove)
        return nuove


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
            nuovi = scarica(db)
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


def aggiorna_gym(db, forse=True) -> bool:
    return _aggiorna(db, "gym", ORE_VIDEO, video_gym, forse=forse)


def aggiorna_notizie(db, forse=True) -> bool:
    return _aggiorna(db, "notizie", ORE_NOTIZIE, notizie_dal_feed, forse=forse)


def aggiorna_quiz(db, forse=True) -> bool:
    return _aggiorna(db, "quiz", ORE_EXTRA, quiz_dal_servizio, forse=forse)


def _domanda_nuova(quanti=1):
    """Domande nuove dal servizio, o `[]` se non si riesce.

    Non e' un guasto: una domanda in piu' e' un di piu' (il gioco funziona lo
    stesso senza), quindi una rete assente non deve far fallire la risposta ne'
    svuotare la copia.
    """
    if quanti <= 0:
        return []
    try:
        return quiz_dal_servizio(quanti=quanti)
    except NonDisponibile:
        return []


def rispondi(db, indice) -> dict | None:
    """Segna una domanda come indovinata: la toglie e ne mette una nuova.

    E' quello che fa cambiare domanda a ogni risposta esatta. Si toglie quella
    indovinata (non si rivede) e se ne accoda una nuova scaricata al volo, cosi'
    il quiz resta lungo uguale; se la rete non risponde la domanda si toglie lo
    stesso — ripetere una domanda a cui si e' appena risposto e' peggio di
    averne una in meno.

    Restituisce il quiz aggiornato, o `None` se l'indice non esiste.
    """
    voci = quiz(db)
    if not isinstance(indice, int) or not (0 <= indice < len(voci)):
        return None
    domanda = voci[indice]
    resto = [d for i, d in enumerate(voci) if i != indice]
    nuove = _domanda_nuova(1)
    if nuove:
        resto.append(nuove[0])
    _scrivi(db, "quiz", resto)
    return {"quiz": resto, "risposta": domanda,
            "quando": quando_aggiornate(db)["quiz"]}


def aggiorna(db, forse=True) -> dict:
    """Aggiorna TV, notizie, GYM, quiz, suggerimento e opere d'arte. Non solleva mai."""
    return {"video": aggiorna_video(db, forse=forse),
            "notizie": aggiorna_notizie(db, forse=forse),
            "gym": aggiorna_gym(db, forse=forse),
            "quiz": aggiorna_quiz(db, forse=forse),
            "suggerimento": aggiorna_suggerimento(db, forse=forse),
            "arte": aggiorna_arte(db, forse=forse)}


def video(db) -> list:
    return _leggi(db, "video")[0] or []


def gym(db) -> list:
    return _leggi(db, "gym")[0] or []


def notizie(db) -> list:
    return _leggi(db, "notizie")[0] or []


def quiz(db) -> list:
    return _leggi(db, "quiz")[0] or []


def quando_aggiornate(db) -> dict:
    """Quando la copia e' stata presa, per dirlo nella sezione.

    Senza, l'utente non sa se sta guardando le notizie di oggi o quelle di una
    settimana fa quando la rete non ha risposto.
    """
    esito = {}
    for chiave in ("video", "notizie", "gym", "quiz", "suggerimento", "arte"):
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
