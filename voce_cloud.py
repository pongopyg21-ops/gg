"""Sintesi vocale neurale su cloud (Azure Speech), con la chiave sul server.

Perche' non direttamente dal browser: per usare una voce neurale Azure servirebbe
la chiave del servizio nel client, dove chiunque apra gli strumenti di sviluppo la
legge. La chiave resta qui, il browser chiede l'audio a noi e noi lo inoltriamo.

Le voci sono quelle **ufficiali** di Azure: si indicano per nome completo
(`it-IT-IsabellaNeural`), e l'elenco in VOCI e' un sottoinsieme di quelle italiane.
Nomi inventati vengono rifiutati da Azure con un 400: meglio tenerli qui, dove
l'errore e' leggibile e non costa una chiamata.

Con `requests` assente si usa `urllib` della libreria standard: una dipendenza in
meno e' una cosa in meno che si rompe quando l'ambiente viene azzerato.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MAGGIORDOMO_DATA", BASE_DIR)

# Voci italiane neurali. L'elenco e' quello ufficiale di Azure, ma **non tutte
# esistono in ogni area**: le due voci "HD" mancano, per esempio, in italynorth,
# e sceglierle li' fa rispondere 400. Un elenco scritto a mano promette voci che
# l'area puo' non avere, quindi si preferisce chiedere l'elenco ad Azure
# (`elenco_voci`) e usare questo solo come ripiego, quando non si puo' chiedere.
VOCI = [
    {"nome": "it-IT-ElsaNeural", "etichetta": "Elsa", "genere": "femminile", "tipo": "standard"},
    {"nome": "it-IT-IsabellaNeural", "etichetta": "Isabella", "genere": "femminile", "tipo": "standard"},
    {"nome": "it-IT-ImeldaNeural", "etichetta": "Imelda", "genere": "femminile", "tipo": "standard"},
    {"nome": "it-IT-FabiolaNeural", "etichetta": "Fabiola", "genere": "femminile", "tipo": "standard"},
    {"nome": "it-IT-PalmiraNeural", "etichetta": "Palmira", "genere": "femminile", "tipo": "standard"},
    {"nome": "it-IT-IrmaNeural", "etichetta": "Irma", "genere": "femminile", "tipo": "standard"},
    {"nome": "it-IT-FiammaNeural", "etichetta": "Fiamma", "genere": "femminile", "tipo": "standard"},
    {"nome": "it-IT-DiegoNeural", "etichetta": "Diego", "genere": "maschile", "tipo": "standard"},
    {"nome": "it-IT-GianniNeural", "etichetta": "Gianni", "genere": "maschile", "tipo": "standard"},
    {"nome": "it-IT-CataldoNeural", "etichetta": "Cataldo", "genere": "maschile", "tipo": "standard"},
    {"nome": "it-IT-LisandroNeural", "etichetta": "Lisandro", "genere": "maschile", "tipo": "standard"},
    {"nome": "it-IT-RinaldoNeural", "etichetta": "Rinaldo", "genere": "maschile", "tipo": "standard"},
    {"nome": "it-IT-BenignoNeural", "etichetta": "Benigno", "genere": "maschile", "tipo": "standard"},
    {"nome": "it-IT-CalimeroNeural", "etichetta": "Calimero", "genere": "maschile", "tipo": "standard"},
    {"nome": "it-IT-GiuseppeNeural", "etichetta": "Giuseppe", "genere": "maschile", "tipo": "standard"},
    {"nome": "it-IT-IsabellaMultilingualNeural", "etichetta": "Isabella (multilingua)", "genere": "femminile", "tipo": "multilingua"},
    {"nome": "it-IT-AlessioMultilingualNeural", "etichetta": "Alessio (multilingua)", "genere": "maschile", "tipo": "multilingua"},
    {"nome": "it-IT-GiuseppeMultilingualNeural", "etichetta": "Giuseppe (multilingua)", "genere": "maschile", "tipo": "multilingua"},
    {"nome": "it-IT-MarcelloMultilingualNeural", "etichetta": "Marcello (multilingua)", "genere": "maschile", "tipo": "multilingua"},
    # "HD" e' il modello piu' naturale; puo' non essere disponibile in tutte le
    # aree, e in quel caso Azure risponde 400 e il client ripiega da solo
    {"nome": "it-IT-Isabella:DragonHDLatestNeural", "etichetta": "Isabella HD", "genere": "femminile", "tipo": "hd"},
    {"nome": "it-IT-Alessio:DragonHDLatestNeural", "etichetta": "Alessio HD", "genere": "maschile", "tipo": "hd"},
]

NOMI_VALIDI = {v["nome"] for v in VOCI}
VOCE_PREDEFINITA = "it-IT-IsabellaNeural"

# Oltre questa lunghezza non si sintetizza: la conferma vocale e' una frase, non un
# testo da leggere. Un limite tiene anche il costo prevedibile.
MAX_CARATTERI = 600

# L'elenco delle voci si chiede ad Azure, e l'elenco cambia di rado: tenerlo per
# un po' evita che ogni apertura del pannello vocale sia una chiamata di rete.
VOCI_CACHE_SECONDI = 6 * 60 * 60
_voci_cache: dict = {"area": None, "quando": 0.0, "elenco": None}

# Limiti di accordo sui valori prosodici che il client puo' chiedere.
RATE_MIN, RATE_MAX = 0.5, 2.0
PITCH_MIN, PITCH_MAX = -50, 50  # in percentuale


_FILE_LETTI = False


def _leggi_file_segreto() -> None:
    """Se l'ambiente non ha la chiave, la cerca in un file accanto all'app.

    Due forme, perche' i sistemi sono due: `segreto.bat` su Windows (lo crea
    `windows\\voce.bat`) e `segreto.sh` sul server, dove l'app parte da
    `avvia.sh`. Il file sta fuori da git, quindi la chiave non finisce nel
    codice.

    Serve perche' altrimenti la chiave andrebbe esportata a mano a ogni avvio:
    chi riavvia l'app dovrebbe ricordarsene, e un riavvio senza chiave fa
    tornare la voce meccanica senza che si capisca il perche'.
    """
    global _FILE_LETTI
    if _FILE_LETTI:
        return
    _FILE_LETTI = True

    cartelle = [BASE_DIR, DATA_DIR]
    nomi = ["segreto.sh", "segreto.bat"]
    for cartella in dict.fromkeys(cartelle):
        for nome in nomi:
            percorso = os.path.join(cartella, nome)
            if not os.path.exists(percorso):
                continue
            try:
                testo = open(percorso, encoding="utf-8-sig", errors="replace").read()
            except OSError:
                continue
            for riga in testo.splitlines():
                riga = riga.strip()
                if not riga or riga.startswith(("#", "REM ", "rem ", "@")):
                    continue
                m = re.match(
                    r"(?:set\s+\"?|export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
                    r"(?:\"([^\"]*)\"|'([^']*)'|(.*))$", riga)
                if not m:
                    continue
                nome = m.group(1)
                valore = (m.group(2) or m.group(3) or m.group(4) or "").strip()
                # in `set "NOME=valore"` la virgoletta sta solo all'inizio;
                # se il valore ne porta una in coda, e' quella di chiusura
                valore = valore.rstrip('"').strip()
                if nome.startswith("AZURE_SPEECH_") and valore and not os.environ.get(nome):
                    os.environ[nome] = valore
            return


def chiave() -> str:
    """La chiave del servizio.

    In ordine: l'ambiente, `segreto.sh`/`segreto.bat`, i segreti di GitHub.
    L'ultimo ripiego c'e' perche' il file vive nel workspace, che non e' eterno:
    quando il workspace viene ricreato la chiave sparisce, e senza il ripiego
    bisognerebbe incollarla di nuovo a mano.
    """
    _leggi_file_segreto()
    return os.environ.get("AZURE_SPEECH_KEY", "").strip()


def regione() -> str:
    """L'area della risorsa: determina l'indirizzo, non si puo' indovinare.

    Sempre in minuscolo: l'indirizzo del servizio non esiste in altre forme, e
    scriverla male e' un errore silenzioso — la sintesi fallisce senza dire che
    il problema e' una maiuscola.
    """
    _leggi_file_segreto()
    return os.environ.get("AZURE_SPEECH_REGION", "").strip().lower()


def formato_audio() -> str:
    """Formato dell'audio richiesto ad Azure.

    MP3 e non WAV: un WAV da 24 kHz di una frase intera pesa centinaia di kB,
    mentre l'MP3 e' una frazione. Conta perche' l'audio passa dalla rete, e su
    telefono in 4G la differenza si sente.
    """
    return os.environ.get("AZURE_SPEECH_FORMAT", "audio-24khz-48kbitrate-mono-mp3").strip()


def configurato() -> bool:
    return bool(chiave() and regione())


def salva_config(chiave_val: str, regione_val: str) -> str:
    """Scrive la chiave nel file segreto ed espone il valore subito.

    Il file lo scrive l'app, non l'utente: e' l'unica forma che non si puo'
    sbagliare. Scritto a mano, una virgoletta o uno spazio di troppo fanno
    fallire la sintesi senza un messaggio che lo dica.

    Si scrive `segreto.sh` perche' il lettore accetta entrambi i nomi su
    qualunque sistema, e cosi' la configurazione vale sia su Windows sia sul
    server. Scrittura atomica: un file scritto a meta' lascerebbe la voce senza
    chiave, ed e' proprio il caso da evitare.
    """
    chiave_val = (chiave_val or "").strip().strip("'\"")
    regione_val = (regione_val or "").strip().lower().strip("'\"")
    if not chiave_val or not regione_val:
        raise ValueError("Servono sia la chiave sia l'area")

    testo = (
        "# Chiave della voce neurale, scritta dall'app.\n"
        "# Escluso da git: la chiave resta su questo computer.\n"
        f"export AZURE_SPEECH_KEY='{chiave_val}'\n"
        f"export AZURE_SPEECH_REGION='{regione_val}'\n"
    )
    percorso = os.path.join(BASE_DIR, "segreto.sh")
    provvisorio = percorso + ".tmp"
    with open(provvisorio, "w", encoding="utf-8") as f:
        f.write(testo)
    os.replace(provvisorio, percorso)
    try:
        os.chmod(percorso, 0o600)      # leggibile solo da chi lo possiede
    except OSError:
        pass                            # su Windows puo' non essere supportato

    global _FILE_LETTI
    _FILE_LETTI = True
    os.environ["AZURE_SPEECH_KEY"] = chiave_val
    os.environ["AZURE_SPEECH_REGION"] = regione_val
    return percorso


def verifica(chiave_val: str, regione_val: str) -> tuple[bool, str]:
    """Prova la chiave su Azure **prima** di salvarla.

    Chiedendo l'elenco delle voci si scoprono insieme tre cose: che la chiave
    vale, che l'area e' quella giusta e che il servizio risponde. Salvandola
    senza provarla, un errore si scoprirebbe solo alla prima frase letta, dove
    sembra un guasto dell'app invece di una chiave sbagliata.
    """
    chiave_val = (chiave_val or "").strip().strip("'\"")
    regione_val = (regione_val or "").strip().lower().strip("'\"")
    if not chiave_val or not regione_val:
        return False, "Servono sia la chiave sia l'area."

    url = f"https://{regione_val}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    richiesta = urllib.request.Request(
        url, headers={"Ocp-Apim-Subscription-Key": chiave_val})
    try:
        with urllib.request.urlopen(richiesta, timeout=15.0) as risposta:
            dati = json.loads(risposta.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, ("La chiave non e' valida, oppure l'area non e' quella "
                           "della risorsa. Controlla entrambe nella pagina "
                           "\"Chiavi ed endpoint\" di Azure.")
        return False, f"Azure ha risposto {e.code}. Riprova fra poco."
    except Exception as e:
        return False, f"Non riesco a contattare Azure ({type(e).__name__}). Controlla la connessione."

    italiane = [v for v in (dati if isinstance(dati, list) else [])
                if str(v.get("ShortName", "")).startswith("it-IT-")]
    if not italiane:
        return False, (f"La chiave funziona, ma l'area \"{regione_val}\" non offre "
                       "voci italiane. Usa un'area che le abbia, per esempio italynorth.")
    return True, f"Chiave valida. L'area \"{regione_val}\" offre {len(italiane)} voci italiane."


def _etichetta(nome: str) -> str:
    """Nome leggibile: "it-IT-IsabellaNeural" -> "Isabella".

    Il genere non si mette qui: lo aggiunge il client in fondo, con " · ". Un
    elenco il cui genere compare due volte si legge male.
    """
    return nome.split("-")[-1].replace("Neural", "").strip() or nome


def _genere_it(g: str) -> str:
    return "femminile" if (g or "").lower().startswith("f") else "maschile"


def _voci_dal_servizio() -> list[dict] | None:
    """Le voci italiane che l'area ha davvero, chieste ad Azure.

    Scritto l'elenco a mano, si offrono voci che l'area puo' non avere: e' quello
    che succedeva con le due "HD", assenti in italynorth, dove sceglierle faceva
    rispondere 400. Chiedendolo, l'elenco e' vero per costruzione.

    Restituisce `None` se non si riesce a chiedere: in quel caso si ripiega
    sull'elenco scritto a mano, meglio un elenco forse imperfetto che nessuno.
    """
    url = f"https://{regione()}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    richiesta = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": chiave()})
    try:
        with urllib.request.urlopen(richiesta, timeout=8.0) as risposta:
            dati = json.loads(risposta.read().decode("utf-8"))
    except Exception:
        return None

    fuori = []
    for v in dati if isinstance(dati, list) else []:
        nome = v.get("ShortName", "")
        if not nome.startswith("it-IT-"):
            continue
        genere = _genere_it(v.get("Gender", ""))
        fuori.append({
            "nome": nome,
            "etichetta": _etichetta(nome),
            "genere": genere,
            "tipo": "multilingua" if "Multilingual" in nome else "standard",
        })
    fuori.sort(key=lambda v: (v["tipo"] != "standard", v["etichetta"]))
    # la predefinita resta la prima della lista: e' quella che si sente senza scegliere
    fuori.sort(key=lambda v: v["nome"] != VOCE_PREDEFINITA)
    return fuori or None


def elenco_voci() -> list[dict]:
    """Le voci fra cui si puo' scegliere: quelle vere dell'area, se si sa chiederle."""
    if not configurato():
        return VOCI

    adesso = time.time()
    if (_voci_cache["elenco"] and _voci_cache["area"] == regione()
            and adesso - _voci_cache["quando"] < VOCI_CACHE_SECONDI):
        return _voci_cache["elenco"]

    dal_servizio = _voci_dal_servizio()
    if dal_servizio:
        _voci_cache.update({"area": regione(), "quando": adesso, "elenco": dal_servizio})
        return dal_servizio
    return VOCI


def voce_valida(nome: str | None) -> bool:
    """Se il nome e' una voce che questa area conosce.

    Il controllo non e' piu' su un elenco scritto a mano ma su quello vero
    dell'area, cosi' una voce assente qui viene fermata prima della chiamata
    invece di far rispondere 400 al servizio.
    """
    return bool(nome) and any(v["nome"] == nome for v in elenco_voci())


def escape_xml(testo: str) -> str:
    """Mette al riparo il testo dentro l'SSML.

    Il testo arriva dall'utente (una conferma vocale contiene nomi di ingredienti)
    e finisce dentro un documento XML: senza escape, un `&` farebbe fallire la
    sintesi con un 400 di Azure, e un `<` potrebbe iniettare tag. L'escape va fatto
    per primo, prima di aggiungere qualunque markup.
    """
    return (
        (testo or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _limita(valore, minimo, massimo, predefinito):
    try:
        n = float(valore)
    except (TypeError, ValueError):
        return predefinito
    return max(minimo, min(massimo, n))


def costruisci_ssml(testo: str, voce: str, rate=1.0, pitch=0.0, stile: str | None = None) -> str:
    """L'SSML da mandare ad Azure.

    `rate` e' un moltiplicatore (1.0 = normale) e viene convertito in percentuale,
    che e' quello che vuole SSML. `pitch` e' gia' in percentuale, e **0 e' il
    valore neutro**: un `<prosody pitch="1%">` non e' "quasi zero", e' un tono
    leggermente alterato che cambia la lettura di alcune voci senza motivo.
    """
    velocita = round((_limita(rate, RATE_MIN, RATE_MAX, 1.0) - 1) * 100)
    tono = round(_limita(pitch, PITCH_MIN, PITCH_MAX, 0))

    prosodia = ""
    if velocita != 0 or tono != 0:
        prosodia = f'<prosody rate="{velocita}%" pitch="{tono}%">{escape_xml(testo)}</prosody>'
    else:
        prosodia = escape_xml(testo)

    if stile:
        prosodia = f'<mstts:express-as style="{escape_xml(stile)}">{prosodia}</mstts:express-as>'

    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="it-IT">'
        f'<voice name="{escape_xml(voce)}">{prosodia}</voice></speak>'
    )


class ErroreVoce(Exception):
    """Fallimento nella sintesi cloud.

    `stato` permette all'endpoint di distinguere "non configurato" (503, e il
    client usa la voce del browser) da "testo o voce rifiutati" (400, un errore
    vero da far vedere) senza interpretare il testo del messaggio.
    """

    def __init__(self, messaggio: str, stato: int = 502):
        super().__init__(messaggio)
        self.stato = stato


def sintetizza(testo: str, voce: str, rate=1.0, pitch=0.0, stile: str | None = None,
               timeout: float = 12.0) -> bytes:
    """Chiede l'audio ad Azure e restituisce i byte (MP3).

    L'audio non viene salvato da nessuna parte: si scarica e si consegna. Tenerlo
    su disco significherebbe gestire una cache e la sua scadenza, per un guadagno
    che non vale il rischio di lasciare frasi di casa in un file.
    """
    if not configurato():
        raise ErroreVoce("Sintesi cloud non configurata", stato=503)
    if not voce_valida(voce):
        raise ErroreVoce("Voce non riconosciuta", stato=400)
    testo = (testo or "").strip()
    if not testo:
        raise ErroreVoce("Testo vuoto", stato=400)
    if len(testo) > MAX_CARATTERI:
        raise ErroreVoce(f"Testo troppo lungo (massimo {MAX_CARATTERI} caratteri)", stato=400)

    url = f"https://{regione()}.tts.speech.microsoft.com/cognitiveservices/v1"
    richiesta = urllib.request.Request(
        url,
        data=costruisci_ssml(testo, voce, rate, pitch, stile).encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": chiave(),
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": formato_audio(),
            "User-Agent": "IlMaggiordomo",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
            audio = risposta.read()
    except urllib.error.HTTPError as e:
        # i dettagli di Azure possono contenere la chiave o l'indirizzo interno:
        # al client va un messaggio breve, i particolari restano nel log
        raise ErroreVoce(_spiega_errore(e), stato=400 if e.code in (400, 401, 403) else 502)
    except urllib.error.URLError as e:
        raise ErroreVoce(f"Servizio vocale non raggiungibile: {e.reason}", stato=502)
    except TimeoutError:
        raise ErroreVoce("Il servizio vocale non ha risposto in tempo", stato=502)

    if not audio:
        raise ErroreVoce("Il servizio vocale ha restituito audio vuoto", stato=502)
    return audio


def _spiega_errore(e: urllib.error.HTTPError) -> str:
    """Messaggio leggibile per gli errori piu' comuni di Azure.

    Non si riporta il corpo della risposta: puo' contenere dettagli della risorsa
    che non devono finire nel browser.
    """
    if e.code in (401, 403):
        # Azure non distingue in modo affidabile "chiave sbagliata" da "area
        # sbagliata": sono lo stesso intreccio, e separarli manderebbe fuori strada
        return "Chiave o area del servizio vocale non valide"
    if e.code == 400:
        # 400 qui vuol dire quasi sempre una voce che l'area non ha: si dice cosa
        # fare, non solo che e' andata male. Le voci dell'area sono ora in elenco,
        # quindi il caso resta raro.
        return "Voce non disponibile in questa area: scegline un'altra"
    if e.code == 429:
        return "Troppe richieste al servizio vocale: riprova fra poco"
    return f"Il servizio vocale ha risposto con errore {e.code}"
