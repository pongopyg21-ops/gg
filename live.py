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


def scarica_foto(url, timeout=TIMEOUT):
    """Scarica un fotogramma. Restituisce (dati, content_type, errore).

    Legge al massimo `MAX_FOTO` byte: un indirizzo che punta a un file grande
    non deve riempire la memoria del server, e un fotogramma entra comunque in
    quel tetto.
    """
    try:
        with urllib.request.urlopen(_richiesta(url), timeout=timeout) as risposta:
            tipo = risposta.headers.get("Content-Type", "image/jpeg")
            dati = risposta.read(MAX_FOTO)
    except urllib.error.HTTPError as e:
        return None, None, f"La telecamera ha risposto {e.code}"
    except urllib.error.URLError as e:
        return None, None, f"Telecamera non raggiungibile ({e.reason})"
    except (TimeoutError, OSError) as e:
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
