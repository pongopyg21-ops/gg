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
import urllib.error
import urllib.request

# Voci italiane neurali, dall'elenco ufficiale Azure. "standard" e' la qualita'
# normale; "multilingua" e "HD" sono piu' recenti e piu' naturali. Il nome tecnico
# e' quello che va nel campo `name` dell'SSML.
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

# Limiti di accordo sui valori prosodici che il client puo' chiedere.
RATE_MIN, RATE_MAX = 0.5, 2.0
PITCH_MIN, PITCH_MAX = -50, 50  # in percentuale


def chiave() -> str:
    """La chiave del servizio, dall'ambiente. Stringa vuota se non configurata."""
    return os.environ.get("AZURE_SPEECH_KEY", "").strip()


def regione() -> str:
    """L'area della risorsa: determina l'indirizzo, non si puo' indovinare."""
    return os.environ.get("AZURE_SPEECH_REGION", "").strip()


def formato_audio() -> str:
    """Formato dell'audio richiesto ad Azure.

    MP3 e non WAV: un WAV da 24 kHz di una frase intera pesa centinaia di kB,
    mentre l'MP3 e' una frazione. Conta perche' l'audio passa dalla rete, e su
    telefono in 4G la differenza si sente.
    """
    return os.environ.get("AZURE_SPEECH_FORMAT", "audio-24khz-48kbitrate-mono-mp3").strip()


def configurato() -> bool:
    return bool(chiave() and regione())


def elenco_voci() -> list[dict]:
    return VOCI


def voce_valida(nome: str | None) -> bool:
    return bool(nome) and nome in NOMI_VALIDI


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
        return "Il servizio vocale ha rifiutato il testo o la voce"
    if e.code == 429:
        return "Troppe richieste al servizio vocale: riprova fra poco"
    return f"Il servizio vocale ha risposto con errore {e.code}"
