"""La cassaforte: i dati sensibili della casa, cifrati con una password.

Le FAQ sono una rubrica, non un posto sicuro: le loro voci viaggiano in chiaro
nella risposta dell'API e chi apre gli strumenti del browser le legge. La
**cassaforte** e' l'altra cosa — password, codici, PIN — e li' la riservatezza
deve essere vera, non un `••••`. Per questo le voci riservate si **cifrano** con
una password della cassaforte, che puo' essere **diversa** da quella con cui si
entra nell'app: aprire l'app non basta a leggere la cassaforte, serve la sua
password.

Qui c'e' solo la crittografia, senza database e senza Flask: `cifra` e `decifra`
lavorano su bytes, quindi si provano davvero, senza rete e senza browser. E'
la parte che, se sbaglia, non se ne accorge nessuno — un dato cifrato male
sembra cifrato bene — quindi e' anche quella con piu' test.

Cosa usa, e perche' solo questo:

- **PBKDF2-HMAC-SHA256** (`hashlib.pbkdf2_hmac`, nella libreria standard): dalla
  password deriva due chiavi, una per cifrare e una per firmare. Il sale e' nuovo
  a ogni scrittura, quindi la stessa password non produce mai lo stesso file, e
  le iterazioni sono tante quante ne servono perche' provare le password a forza
  bruta costi. Non si usa una libreria esterna (`cryptography`) perche' non e'
  fra le dipendenze e perche' con quello che offre la standard library si fa la
  stessa cosa in modo verificabile.
- **Un flusso (keystream) da HMAC** e' la cifratura vera e propria: AES non c'e'
  nella standard library, e scriverne uno a mano sarebbe il modo peggiore di
  proteggere dei dati. HMAC-SHA256 e' una primitiva che c'e' e che e' solida;
  usarlo come generatore di flusso e' lo schema classico (lo stesso di HKDF),
  non un'invenzione.
- **Encrypt-then-MAC** e' la firma: prima si cifra, poi si firma il testo
  cifrato. Cosi' un file manomesso non viene nemmeno provato a decifrare — la
  firma non torna — e una password sbagliata non produce "spazzatura" ma un
  rifiuto netto.

Il formato del file e' un dizionario JSON: `v` (versione), `i` (iterazioni),
`s` (sale), `d` (dati cifrati) e `m` (firma), tutti in base64. Niente di segreto
sta in chiaro: chi legge il file vede solo bytes casuali e i parametri, che
servono a riaprire il file con un'altra versione del programma.
"""

import base64
import hashlib
import hmac
import json
import os

VERSIONE = 1
# Quante volte si ripete PBKDF2. Tante da rendere costoso provare le password a
# forza bruta, poche da non far aspettare chi apre la cassaforte: circa un
# decimo di secondo su una macchina normale.
ITERAZIONI = 200_000
# Lunghezza della chiave derivata: 32 byte per il flusso + 32 per la firma.
_LUNGHEZZA_CHIAVE = 32
# Il sale: 16 byte bastano per garantire che due file non coincidano mai.
_LUNGHEZZA_SALE = 16


class CassaforteErrore(Exception):
    """La cifratura o la decifratura non sono riuscite.

    La password sbagliata e il file manomesso danno lo stesso errore, di
    proposito: distinguerli direbbe a chi prova che il file esiste ed e' integro,
    cioe' che sta indovinando la password giusta.
    """


def _b64(dati: bytes) -> str:
    return base64.b64encode(dati).decode("ascii")


def _da_b64(testo: str) -> bytes:
    return base64.b64decode(testo.encode("ascii"))


def _chiavi(password: str, sale: bytes, iterazioni: int):
    """Le due chiavi, da una sola password: una cifra, una firma.

    Sono separate apposta. Usare la stessa chiave per cifrare e per firmare e'
    una scorciatoia che sembra innocua e che lega due usi diversi: se un giorno
    uno dei due va cambiato, cambia anche l'altro. Costano un solo PBKDF2, quindi
    non c'e' motivo di risparmiare.
    """
    materiale = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), sale, iterazioni,
        dklen=_LUNGHEZZA_CHIAVE * 2)
    return materiale[:_LUNGHEZZA_CHIAVE], materiale[_LUNGHEZZA_CHIAVE:]


def _flusso(chiave: bytes, quanti: int) -> bytes:
    """Il flusso di byte da combinare col testo: HMAC(chiave, contatore).

    E' il generatore di flusso classico (lo stesso di HKDF, senza la parte di
    estrazione): a ogni blocco si firma un contatore che avanza, e i blocchi si
    concatenano. Il contatore e' a 64 bit, quindi non si ripete mai per un file
    di dimensioni ragionevoli, che e' l'unica condizione perche' il flusso resti
    sicuro.
    """
    blocchi = []
    prodotto = 0
    contatore = 0
    while prodotto < quanti:
        blocchi.append(hmac.new(chiave, contatore.to_bytes(8, "big"),
                                hashlib.sha256).digest())
        prodotto += 32
        contatore += 1
    return b"".join(blocchi)[:quanti]


def _combina(dati: bytes, flusso: bytes) -> bytes:
    """XOR fra due sequenze, fatto sugli interi: `bytes` e' immutabile, e un
    ciclo byte per byte sarebbe la parte piu' lenta di tutta la cassaforte."""
    return (int.from_bytes(dati, "big") ^ int.from_bytes(flusso, "big")).to_bytes(
        len(dati), "big")


def _firma(chiave_firma: bytes, versione: int, iterazioni: int, sale: bytes,
           cifrato: bytes) -> bytes:
    """La firma sul testo **cifrato**, non su quello chiaro (Encrypt-then-MAC).

    Si firma anche la versione e le iterazioni: senza, chi manomette il file
    potrebbe abbassare le iterazioni per rendere piu' facile indovinare la
    password, e la firma non se ne accorgerebbe.
    """
    messaggio = b"|".join([
        str(versione).encode("ascii"),
        str(iterazioni).encode("ascii"),
        sale,
        cifrato,
    ])
    return hmac.new(chiave_firma, messaggio, hashlib.sha256).digest()


def cifra(chiaro: bytes, password: str, iterazioni: int = ITERAZIONI,
          sale: bytes | None = None) -> str:
    """Cifra e firma `chiaro` con `password`, e restituisce il file (JSON).

    Il sale e' nuovo a ogni chiamata, a meno che non lo si passi: passarlo serve
    ai test, che devono poter ripetere la cifratura e confrontarla.
    """
    if not password:
        raise CassaforteErrore("Serve una password per la cassaforte")
    if sale is None:
        sale = os.urandom(_LUNGHEZZA_SALE)
    chiave_cifra, chiave_firma = _chiavi(password, sale, iterazioni)
    cifrato = _combina(chiaro, _flusso(chiave_cifra, len(chiaro)))
    firma = _firma(chiave_firma, VERSIONE, iterazioni, sale, cifrato)
    return json.dumps({
        "v": VERSIONE,
        "i": iterazioni,
        "s": _b64(sale),
        "d": _b64(cifrato),
        "m": _b64(firma),
    }, separators=(",", ":"))


def decifra(file_cifrato: str, password: str) -> bytes:
    """Il testo in chiaro, o `CassaforteErrore`.

    Prima si verifica la firma e **poi** si decifra: se il file e' stato toccato
    si esce subito, senza restituire spazzatura. La password sbagliata fa fallire
    la firma, quindi il risultato e' lo stesso errore netto.
    """
    try:
        dati = json.loads(file_cifrato)
        versione = int(dati["v"])
        iterazioni = int(dati["i"])
        sale = _da_b64(dati["s"])
        cifrato = _da_b64(dati["d"])
        firma = _da_b64(dati["m"])
    except (ValueError, KeyError, TypeError):
        raise CassaforteErrore("File della cassaforte non leggibile")
    if versione != VERSIONE:
        raise CassaforteErrore(f"Versione della cassaforte non supportata: {versione}")
    if not password:
        raise CassaforteErrore("Serve la password della cassaforte")
    _, chiave_firma = _chiavi(password, sale, iterazioni)
    attesa = _firma(chiave_firma, versione, iterazioni, sale, cifrato)
    if not hmac.compare_digest(attesa, firma):
        raise CassaforteErrore("Password sbagliata o cassaforte danneggiata")
    chiave_cifra, _ = _chiavi(password, sale, iterazioni)
    return _combina(cifrato, _flusso(chiave_cifra, len(cifrato)))


def password_giusta(file_cifrato: str, password: str) -> bool:
    """La password apre il file? Non solleva: serve a un controllo, non a un
    percorso di errore — la cassaforte chiusa e' uno stato normale."""
    try:
        decifra(file_cifrato, password)
        return True
    except CassaforteErrore:
        return False


# --------------------------------------------------------- impronta della pw
# La password della cassaforte **non** entra nella sessione: la sessione e' un
# biscotto che il client puo' leggere, quindi ci finirebbe in chiaro (senza
# chiave, cifrarla o firmarla non basta: il client la vedrebbe comunque). Si
# tiene invece l'**impronta** PBKDF2: serve a verificare che la password sia
# giusta, ma non a decifrare la scatola — per quella serve il testo in chiaro,
# che vive solo sul server, in memoria, per il tempo dell'apertura.

IMPRONTA_ITERAZIONI = 200_000
_IMPRONTA_ALGORITMO = "psha256"


def impronta(password: str, iterazioni: int = IMPRONTA_ITERAZIONI) -> str:
    """L'impronta della password, nel formato `psha256$<iterazioni>$<sale>$<hash>`.

    Il sale e' nuovo a ogni calcolo. Non e' un segreto (sta nel registro): serve
    solo a evitare che due case con la stessa password abbiano la stessa impronta.
    """
    if not password:
        raise CassaforteErrore("Serve una password per la cassaforte")
    sale = os.urandom(_LUNGHEZZA_SALE)
    derivata = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sale, iterazioni)
    return "$".join((_IMPRONTA_ALGORITMO, str(iterazioni), _b64(sale), _b64(derivata)))


def impronta_giusta(impronta_salvata: str, password: str) -> bool:
    """La password corrisponde all'impronta? Non solleva: un'impronta assente o
    malformata non e' un guasto, e' 'non ancora creata'."""
    if not impronta_salvata or not password:
        return False
    try:
        algoritmo, iterazioni, sale, attesa = impronta_salvata.split("$")
        if algoritmo != _IMPRONTA_ALGORITMO:
            return False
        derivata = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _da_b64(sale), int(iterazioni))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(_b64(derivata), attesa)
