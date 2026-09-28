"""Le telecamere di casa: validazione dell'indirizzo e lettura del flusso.

Perche' un modulo a parte e non dentro `app.py`: qui c'e' la parte che parla
con il telefono (scaricare un fotogramma, aprire il flusso), ed e' quella che
si puo' provare senza un server vero — come `voce_cloud.py` per la sintesi
vocale. `app.py` resta le rotte.

Il flusso **non** arriva mai al browser direttamente: da fuori casa la pagina e'
in HTTPS e un browser non caricherebbe mai un flusso `http://` (contenuto misto).
In piu' l'indirizzo della telecamera (e la sua eventuale password) resterebbe
nella pagina, leggibile da chi apre gli strumenti di sviluppo. Passa tutto dal
server, come la chiave di Azure.
"""

import base64
import socket
import urllib.error
import urllib.parse
import urllib.request

# Come si legge il flusso. `mjpeg` e' quello di IP Webcam (`/video`),
# `snapshot` e' il fotogramma singolo (`/shot.jpg`) interrogato a intervalli.
# Il tipo si chiede all'utente perche' l'indirizzo vero dipende da come e'
# configurata l'app del telefono: indovinarlo darebbe un errore che sembra un
# guasto della telecamera.
#
# RTSP non c'e': `urllib` non lo sa leggere, servirebbe `ffmpeg` come dipendenza
# esterna. Offrirlo nel menu darebbe un tipo che non si puo' mai salvare.
TIPI = ("mjpeg", "snapshot")

# Un fotogramma di una telecamera di sorveglianza sta abbondantemente sotto
# questo; il tetto serve a non riempire la memoria se l'indirizzo punta a
# qualcos'altro (un file grande, una pagina). Oltre, si tronca invece di
# crescere all'infinito.
MAX_FOTO = 8 * 1024 * 1024

# Quanto si aspetta la telecamera. Breve di proposito: una telecamera spenta
# deve dire "non raggiungibile" in pochi secondi, non bloccare la pagina.
TIMEOUT = 6.0

# Tetto al tempo **complessivo** di uno scarico. `TIMEOUT` vale per la singola
# lettura del socket, non per il totale: su un flusso che non finisce (MJPEG di
# IP Webcam su `/video`) ogni pezzo arriva entro il timeout, quindi il tetto per
# lettura non scatta mai e lo scarico non si ferma. Visto davvero: uno snapshot
# verso `/video` e' restato appeso oltre quindici secondi, e ognuno di quelli
# occupava per sempre uno degli otto thread di `waitress` — fino a bloccare
# l'app intera, voce compresa. Il tetto complessivo e' la difesa che mancava.
SCADENZA = 8.0

# Il confine fra i fotogrammi di un flusso MJPEG. IP Webcam usa `--frame`, ma il
# confine e' dichiarato nel `Content-Type` (`boundary=...`), quindi si legge da
# li' invece di indovinarlo.
_CONFINE_TIPO = "multipart/"

# Lo `User-Agent` di un client vero. Alcune app di streaming rispondono in modo
# diverso a una richiesta che non sembra un browser; senza, si vedrebbe un
# errore che non e' un errore della telecamera.
USER_AGENT = "IlMaggiordomo/1.0 (telecamere di casa)"


def url_valido(url):
    """(url, errore). Accetta solo `http` e `https`.

    Non e' una limitazione di comodo: `urllib` sa aprire anche `file://`, e con
    quello un indirizzo scritto nella scheda della telecamera diventerebbe un
    modo di leggere i file del server. Tenendo fuori gli altri schemi, la
    telecamera puo' puntare solo a un indirizzo di rete, che e' l'unica cosa che
    deve fare.
    """
    url = (url or "").strip()
    if not url:
        return None, "L'indirizzo è obbligatorio"
    if len(url) > 2000:
        return None, "L'indirizzo è troppo lungo"
    pezzi = urllib.parse.urlsplit(url)
    if pezzi.scheme not in ("http", "https"):
        return None, "L'indirizzo deve cominciare con http:// o https://"
    if not pezzi.netloc:
        return None, "Nell'indirizzo manca il nome del telefono o il suo indirizzo"
    return url, None


def payload(data, attuale=None):
    """Normalizza e valida i campi di una telecamera. Restituisce (campi, errore).

    Campi assenti in `attuale` non vengono toccati solo se il chiamante li passa:
    qui si parte sempre dai valori attuali (o dai predefiniti) e si sovrascrive
    quello che arriva, cosi' una modifica parziale non azzera il resto.
    """
    data = data or {}
    base = dict(attuale) if attuale else {}
    name = (data.get("name", base.get("name", "")) or "").strip()
    if not name:
        return None, "Il nome è obbligatorio"
    kind = (data.get("kind", base.get("kind", "mjpeg")) or "mjpeg").strip().lower()
    if kind not in TIPI:
        return None, "Tipo non riconosciuto: scegli fra " + ", ".join(TIPI)
    url, errore = url_valido(data.get("url", base.get("url", "")))
    if errore:
        return None, errore
    enabled = data.get("enabled", base.get("enabled", 1))
    return {
        "name": name,
        "place": (data.get("place", base.get("place", "")) or "").strip(),
        "url": url,
        "kind": kind,
        "enabled": 1 if enabled in (1, True, "1", "true", "True") else 0,
    }, None


def _richiesta(url):
    """La richiesta per la telecamera, con le credenziali se ce ne sono.

    Utente e password si possono scrivere **dentro** l'indirizzo IP Webcam ha
    un login opzionale, e quello e' il modo naturale di scriverlo). `urllib` non
    le legge da solo: le lascia attaccate al nome dell'host, e la risoluzione
    fallisce con "Name or service not known" anche quando la telecamera e'
    raggiungibile. Qui si tolgono dall'indirizzo e si mettono nell'header
    `Authorization`, che e' la forma che il server della telecamera si aspetta.

    Le credenziali restano **sul server**: l'header lo costruiamo noi, e il
    browser non vede mai l'indirizzo (chiede sempre una rotta dell'app).
    """
    pezzi = urllib.parse.urlsplit(url)
    intestazioni = {"User-Agent": USER_AGENT}
    if pezzi.username or pezzi.password:
        coppia = f"{urllib.parse.unquote(pezzi.username or '')}:{urllib.parse.unquote(pezzi.password or '')}"
        intestazioni["Authorization"] = "Basic " + base64.b64encode(coppia.encode()).decode()
        host = pezzi.hostname or ""
        if pezzi.port:
            host += f":{pezzi.port}"
        url = urllib.parse.urlunsplit(
            (pezzi.scheme, host, pezzi.path, pezzi.query, pezzi.fragment))
    return urllib.request.Request(url, headers=intestazioni)


def _socket_di(risposta):
    """Il socket sotto una risposta HTTP, o `None`.

    Serve per imporre un tetto di tempo **complessivo**: dall'oggetto risposta
    non si puo' impostare una scadenza, si puo' solo cambiare il timeout di ogni
    singola lettura, che e' troppo debole per un flusso che non finisce. Il
    percorso `fp.raw._sock` vale per `http.client`, che e' quello che usa
    `urlopen`; se la struttura cambia si ripiega senza rompere nulla.
    """
    try:
        return risposta.fp.raw._sock
    except AttributeError:
        return None


def _leggi_pezzo(risposta, quanti):
    """Legge quel che c'e' **adesso**, senza aspettare il resto.

    `read(n)` di `http.client` non torna finche' non ha raccolto esattamente `n`
    byte: su un flusso MJPEG lento ha bloccato sedici secondi prima di
    consegnare il primo fotogramma. `read1` invece fa una sola lettura dal
    socket e torna con quello che e' arrivato, quindi il primo JPEG si riconosce
    subito. Chi non ha `read1` (una sorgente finta nei test) usa `read`.
    """
    leggi = getattr(risposta, "read1", None)
    if leggi is None:
        return risposta.read(quanti)
    return leggi(quanti)


def _primo_fotogramma(risposta):
    """Il primo JPEG di un flusso MJPEG, letto a pezzi.

    `read1` consegna quel che arriva senza aspettare un blocco intero, e appena
    compare un `FF D9` il fotogramma e' completo: si smette li' e non si aspetta
    mai la fine del flusso, che non arriva.

    La ricerca e' incrementale di proposito. Riunire i pezzi e ricercare da capo
    a ogni giro sarebbe quadratico: su un corpo grande ma senza JPEG (un
    indirizzo sbagliato con tipo `multipart/`) diventerebbe un blocco a vuoto
    che tiene il thread occupato per minuti — lo stesso guasto che si sta
    evitando, solo con la CPU invece della rete.
    """
    buf = bytearray()
    inizio = -1
    scan = 0
    letto = 0
    while letto < MAX_FOTO:
        pezzo = _leggi_pezzo(risposta, 4096)
        if not pezzo:
            break
        letto += len(pezzo)
        buf += pezzo
        if inizio < 0:
            inizio = buf.find(b"\xff\xd8")
            if inizio < 0:
                # il fotogramma non e' ancora cominciato: basta l'ultimo byte,
                # perche' il marcatore puo' essere spezzato fra due letture.
                # Il tetto e' su `letto`, non su `buf`: scartando il corpo si
                # terrebbe il buffer corto per sempre e il ciclo non finirebbe.
                del buf[:-1]
                continue
        fine = buf.find(b"\xff\xd9", max(inizio + 2, scan))
        if fine >= 0:
            # dall'inizio del JPEG, non dall'inizio del buffer: davanti c'e'
            # l'involucro del flusso (`--frame`, intestazioni), che non fa parte
            # dell'immagine e la renderebbe illeggibile
            return bytes(buf[inizio:fine + 2])
        scan = len(buf) - 1
    return b""


def scarica_foto(url, timeout=TIMEOUT):
    """Scarica un fotogramma. Restituisce (dati, content_type, errore).

    Legge al massimo `MAX_FOTO` byte: un indirizzo che punta a un file grande
    non deve riempire la memoria del server, e un fotogramma entra comunque in
    quel tetto.

    Il caso che conta e' l'indirizzo sbagliato: se si punta lo **snapshot** a
    `/video` (il flusso continuo di IP Webcam), la risposta e' un MJPEG che non
    finisce mai. Senza difese lo scarico resta appeso — e ogni scarico appeso
    tiene occupato un thread del server per sempre, fino a bloccare l'app
    intera. Qui un flusso `multipart/` si legge a pezzi e ci si ferma alla fine
    del **primo** JPEG; una risposta normale si legge tutta in una volta come
    prima. In ogni caso il socket ha una scadenza, cosi' una telecamera che
    smette di mandare byte libera il thread invece di tenerlo per sempre.
    """
    try:
        with urllib.request.urlopen(_richiesta(url), timeout=timeout) as risposta:
            sock = _socket_di(risposta)
            if sock is not None:
                try:
                    sock.settimeout(SCADENZA)   # telecamera muta: non si aspetta oltre
                except OSError:
                    pass
            tipo = risposta.headers.get("Content-Type", "image/jpeg")
            if _CONFINE_TIPO in tipo.lower():
                dati = _primo_fotogramma(risposta)
                if dati:
                    return dati, "image/jpeg", None
                return None, None, "La telecamera ha risposto, ma senza immagine"
            dati = risposta.read(MAX_FOTO)
    except urllib.error.HTTPError as e:
        return None, None, f"La telecamera ha risposto {e.code}"
    except urllib.error.URLError as e:
        return None, None, f"Telecamera non raggiungibile ({e.reason})"
    except (TimeoutError, OSError, socket.timeout) as e:
        return None, None, f"Telecamera non raggiungibile ({e})"
    if not dati:
        return None, None, "La telecamera ha risposto, ma senza immagine"
    return dati, tipo, None


def apri_flusso(url, timeout=TIMEOUT):
    """Apre il flusso continuo. Restituisce (risposta, errore).

    La risposta va letta a pezzi e chiusa dal chiamante: e' un flusso, non un
    file, e non si puo' tenere tutto in memoria.
    """
    try:
        risposta = urllib.request.urlopen(_richiesta(url), timeout=timeout)
    except urllib.error.HTTPError as e:
        return None, f"La telecamera ha risposto {e.code}"
    except urllib.error.URLError as e:
        return None, f"Telecamera non raggiungibile ({e.reason})"
    except (TimeoutError, OSError) as e:
        return None, f"Telecamera non raggiungibile ({e})"
    return risposta, None


def prova(url, timeout=TIMEOUT):
    """Prova a leggere un fotogramma e dice se la telecamera risponde.

    Restituisce (ok, messaggio). Serve al pulsante "Prova": dire se una
    telecamera e' raggiungibile **prima** di salvarla evita di aggiungere una
    riga che poi non funziona, senza capire perche'.
    """
    _, _, errore = scarica_foto(url, timeout=timeout)
    if errore:
        return False, errore
    return True, "La telecamera risponde"
