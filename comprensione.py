"""Comprensione dei comandi con un modello linguistico (facoltativa).

Il parser a regole di `voice.py` capisce le frasi che erano state previste e
lascia fuori le altre: "dammi la lista della spesa", "fammi vedere la dispensa",
"metti via il vino in cantina". Non e' un difetto del riconoscimento — la
trascrizione e' buona — e' che le regole sono una grammatica scritta a mano, e
la lingua parlata non ci sta dentro.

Qui c'e' la stessa comprensione fatta da un modello. La scelta ha una
conseguenza precisa: **fallisce in modo aperto**. Una frase che il parser non
conosce diventa `unknown` (`"Non ho capito"`); se il modello risponde male o non
risponde, si ricade sullo stesso `voice.parse` e il comportamento e' identico a
prima. Non c'e' un modo in cui questa funzione peggiori il parser: o capisce di
piu', o non cambia niente.

La chiave dell'LLM resta sul server, come quella di Azure, e arriva dagli stessi
posti: l'ambiente (i segreti della conversazione), o un file accanto all'app per
chi la usa su una macchina propria. Non c'e' un pannello che la salvi: l'app non
deve poter riscrivere il proprio segreto, ed e' la stessa regola della voce.

Il costo e' quello di una chiamata breve per comando, ed e' il motivo per cui
il modello predefinito e' il piu' economico: la scelta non e' un dettaglio di
qualita' ma di conto a fine mese. Si puo' cambiare con `LLM_MODEL`.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import date
from urllib.parse import urlparse

# L'endpoint e' quello compatibile con OpenAI. Il predefinito e' il **modello di
# casa** (Ollama): nessuna chiave, nessun costo, niente che esce di casa. Chi
# vuole un servizio in rete lo punta con `LLM_BASE_URL`.
BASE_URL_PREDEFINITA = "http://127.0.0.1:11434/v1"

# Il modello di casa scaricato di norma (`ollama pull qwen2.5:7b-instruct`).
# Se non c'e', la chiamata fallisce e si ricade sul parser a regole: non rompe.
MODELLO_PREDEFINITO = "qwen2.5:7b-instruct"

TIMEOUT = 60.0  # un modello di casa su CPU impiega secondi a rispondere: il
                # primo comando dopo l'avvio puo' arrivare a mezzo minuto. Su un
                # servizio in rete, che risponde subito, questo tetto non si vede.

# Il tetto di token della risposta. Sembra alto per un oggetto JSON di poche
# chiavi, ed e' voluto: i modelli di ragionamento spendono lo stesso budget prima
# di scrivere la risposta. Con un tetto stretto il ragionamento lo esaurisce e il
# JSON arriva troncato o vuoto — l'app ripiega in silenzio sulle regole, e sembra
# che il modello "non capisca". Un tetto largo non costa nulla sugli altri
# modelli: si fermano da soli quando hanno finito.
MAX_TOKENS = 1024


def timeout() -> float:
    """Quanto aspettare il modello, in secondi.

    Il predefinito (`TIMEOUT`) va bene per un servizio in cloud, che risponde in
    frazioni di secondo. Un modello **locale** (Ollama su CPU) impiega diversi
    secondi: con il tetto stretto la chiamata scadrebbe sempre, si ricadrebbe in
    silenzio sul parser a regole e non si capirebbe perche' il modello "non
    capisca". Si alza con `LLM_TIMEOUT`, letto all'avvio come le altre variabili.
    """
    try:
        return max(0.1, float(os.environ.get("LLM_TIMEOUT") or TIMEOUT))
    except (TypeError, ValueError):
        return TIMEOUT


# Gli intenti che il parser sa eseguire. Il modello **non ne inventa di nuovi**:
# fuori da questo elenco la risposta vale `unknown`, che e' il modo in cui una
# comprensione sbagliata non diventa un'azione sbagliata.
INTENTI = {
    "pantry_add", "pantry_remove", "pantry_consume",
    "shopping_add", "shopping_remove", "shopping_check",
    "storage_add", "term_add", "event_add",
    "recipe_search", "recipe_add", "recipe_cooked",
    "domanda", "unknown",
}

# Le unita' dell'app: il modello sceglie fra queste, non scrive quello che vuole.
UNITA = ["g", "kg", "ml", "l", "cucchiaio", "cucchiaino", "pz", "confezione", "fetta"]

# Le aree di una domanda, quelle che `_rispondi_domanda` sa servire.
AREE = ["pantry", "shopping", "storage", "recipes", "chores", "profile"]

# Il modello risponde con **un solo** oggetto JSON. Si chiede l'italiano e una
# temperatura bassa: non serve creativita', serve la stessa frase letta allo
# stesso modo due volte.
ISTRUZIONI = """Sei il modulo di comprensione dei comandi di un'app di casa italiana.
Ricevi una frase dettata a voce e restituisci SOLO un oggetto JSON, senza testo attorno.

Intenti possibili e campi:
- "pantry_add": aggiunge alla dispensa. Campi: name, quantity, unit.
- "pantry_remove": toglie/sostituisce dalla dispensa ("togli", "butta", "non c'e' piu'"). Campi: name, quantity, unit.
- "pantry_consume": scala dalla dispensa quello che si e' usato ("ho finito", "ho usato"). Campi: name, quantity, unit.
- "shopping_add": aggiunge alla lista della spesa. Campi: name, quantity, unit.
- "shopping_remove": toglie dalla lista. Campi: name.
- "shopping_check": spunta in lista quello che si e' comprato. Campi: name.
- "storage_add": aggiunge al magazzino (cose che non si mangiano: detersivi, attrezzi). Campi: name, quantity, unit, place, category.
- "term_add": allergie/intolleranze/restrizioni. Campi: terms (elenco di stringhe).
- "event_add": un impegno con una data (appuntamento, scadenza, promemoria). Campi: name (titolo), when_date (data ISO YYYY-MM-DD), time (ora HH:MM, o vuoto), category (lavoro, casa, salute, famiglia, altro), reminder_days (quanti giorni prima avvisare).
- "recipe_search": cerca fra le ricette. Campo: query.
- "recipe_add": vuole creare/nuova ricetta. Campi: name, items (elenco di {name, quantity, unit}).
- "recipe_cooked": "ho cucinato/ho fatto". Campo: name.
- "domanda": una DOMANDA (non un ordine). Campi: area, query.
- "unknown": non e' un comando per l'app, o non capisci.

Regole importanti:
- Un ordine contiene un verbo d'azione o una quantita'. Una frase senza verbo,
  destinazione o quantita' e' chiacchiera: rispondi "unknown".
- "metti", "aggiungi", "segna" senza destinazione esplicita = spesa.
- Un alimento va in dispensa o spesa; un detersivo o un attrezzo nel magazzino.
- Un "ricordami"/"segnami" con una data o un'ora e' "event_add", non una spesa.
- Le domande ("che cosa c'e'", "quanto", "dove", "hai") sono "domanda": NON
  eseguirle come ordini.
- L'unita' deve essere una di: g, kg, ml, l, cucchiaio, cucchiaino, pz, confezione, fetta.
- L'area di una domanda deve essere una di: pantry, shopping, storage, recipes, chores, profile.
- I luoghi del magazzino comuni: Ripostiglio, Cantina, Garage, Soffitta, Bagno, Cucina.

Rispondi esattamente in questa forma (solo le chiavi che servono, ma sempre "intent"):
{"intent": "shopping_add", "name": "latte", "quantity": 1, "unit": "pz"}
"""


def istruzioni(oggi: str | None = None) -> str:
    """Le istruzioni per il modello, con la data di **oggi** in testa.

    Il modello non sa che giorno e': senza l'ancora risolve "domani" contro il
    suo senso interno del tempo, e un promemoria per domani finisce nel passato
    remoto (2023, tre anni fa), non nel giorno dopo. Il parser a regole lo sa
    (`_data_detta`), e per `event_add` la sua data vince comunque; ma l'ancora
    evita l'errore anche sugli altri campi e rende la risposta coerente.
    """
    giorno = oggi or date.today().isoformat()
    return ISTRUZIONI + (
        f"\nOggi è {giorno}. Risolvi ogni data relativa (domani, dopodomani, "
        "lunedì prossimo, fra una settimana) a partire da oggi, in formato "
        "YYYY-MM-DD."
    )


# Da dove si prende la chiave: l'ambiente, o uno di questi file accanto all'app.
# E' la stessa regola e gli stessi nomi della chiave Azure, piu' `segreto.txt`
# per chi non vuole esportare nulla.
_FILE_SEGRETI = ["segreto.txt", "segreto", "segreto.sh", "segreto.bat"]
_letto = {"fatto": False}


def _pulisci_chiave(valore: str) -> str:
    return (valore or "").strip().strip("'\"")


def _riga_chiave(riga: str) -> tuple[str, str] | None:
    """Legge una riga di `segreto.txt` in una delle forme accettate.

    Le stesse di `voce_cloud`: `NOME=valore`, `chiave: valore`, `export ...`,
    oppure il valore nudo su una riga. Il nome nudo non ha etichetta, quindi si
    riconosce **dalla forma**: una parola tutta minuscola e' l'area, una parola
    che sembra una chiave (`sk-...`) e' la chiave LLM.
    """
    riga = riga.strip()
    if not riga or riga.startswith(("#", "REM ", "rem ", "@")):
        return None
    m = re.match(r"(?:set\s+\"?|export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*"
                 r"(?:\"([^\"]*)\"|'([^']*)'|(.*))$", riga)
    if m:
        nome = m.group(1).lower()
        valore = _pulisci_chiave(m.group(2) or m.group(3) or m.group(4) or "")
        # etichette leggibili ricondotte al nome vero della variabile
        alias = {
            "llm_api_key": "LLM_API_KEY", "openai_api_key": "LLM_API_KEY",
            "api_key": "LLM_API_KEY", "chiave": "LLM_API_KEY", "key": "LLM_API_KEY",
            "llm_model": "LLM_MODEL", "model": "LLM_MODEL", "modello": "LLM_MODEL",
            "llm_base_url": "LLM_BASE_URL", "base_url": "LLM_BASE_URL",
        }
        return alias.get(nome, nome.upper()), valore
    if " " not in riga and riga.isprintable():
        # nudo: una parola minuscola corta e' l'area Azure (non ci riguarda),
        # tutto il resto e' la chiave LLM
        if re.fullmatch(r"[a-z]{3,24}", riga):
            return None
        return "LLM_API_KEY", riga.strip("'\"")
    return None


def _leggi_file() -> None:
    """Se l'ambiente non ha la chiave, la cerca in un file accanto all'app.

    Stessa scelta di `voce_cloud`: la chiave **non** si salva dall'app, si mette
    prima di avviare. Su una macchina propria e' il modo comodo; nei sandbox, dove
    i file spariscono, si usa l'ambiente e i file non servono.
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
                nome, valore = letto
                if valore and not os.environ.get(nome):
                    os.environ[nome] = valore


def chiave() -> str:
    """La chiave del modello: l'ambiente per primo, poi il file."""
    _leggi_file()
    return _pulisci_chiave(os.environ.get("LLM_API_KEY", ""))


def modello() -> str:
    _leggi_file()
    return (os.environ.get("LLM_MODEL") or MODELLO_PREDEFINITO).strip()


def base_url() -> str:
    _leggi_file()
    return (os.environ.get("LLM_BASE_URL") or BASE_URL_PREDEFINITA).strip().rstrip("/")


def _e_locale() -> bool:
    """L'endpoint e' un modello in casa (Ollama)?

    Un modello in casa non chiede una chiave: pretendere `LLM_API_KEY` terrebbe
    spenta proprio la configurazione predefinita. Si riconosce dall'indirizzo,
    perche' non c'e' altro modo di saperlo."""
    return "127.0.0.1" in base_url() or "localhost" in base_url()


def configurato() -> bool:
    """C'e' una **configurazione** per capire i comandi col modello?

    Serve o una chiave (servizio in rete) oppure un endpoint locale (Ollama, che
    non ne usa). Senza ne' l'una ne' l'altro resta il parser a regole: l'app
    funziona lo stesso, non si rompe. E' la stessa logica di
    `voce_cloud.configurato()`.

    Dice che la configurazione **c'e'**, non che il modello risponda: un
    endpoint locale c'e' sempre (e' il predefinito), anche a Ollama spento. Per
    sapere se risponde davvero si usa `raggiungibile()`.
    """
    return bool(chiave()) or _e_locale()


# Il tetto della verifica di raggiungibilita', piu' corto di quello delle
# chiamate: qui non si aspetta una risposta, solo se la porta e' aperta. Ollama
# risponde in millisecondi; un secondo e' gia' tanto per un servizio locale.
TIMEOUT_VERIFICA = 1.5


def _endpoint_salute(base: str) -> str:
    """L'indirizzo da cui chiedere l'elenco dei modelli a un endpoint compatibile
    OpenAI.

    Ollama tiene l'elenco in `/api/tags`, non nella parte compatibile OpenAI
    (`/v1`): da `http://127.0.0.1:11434/v1` si risale a
    `http://127.0.0.1:11434/api/tags`. Un servizio in rete che espone `/v1` di
    solito risponde anche a `/models` con la stessa lista. Cosi' la verifica
    vale per entrambi, senza sapere in anticipo quale sia.
    """
    u = urlparse(base)
    if not u.scheme or not u.netloc:
        return ""
    radice = f"{u.scheme}://{u.netloc}"
    if u.port == 11434:
        return radice + "/api/tags"
    return radice + "/models"


def raggiungibile() -> bool:
    """Il modello risponde **adesso**?

    `configurato()` dice solo che c'e' una configurazione, e un endpoint locale
    c'e' sempre (il predefinito), anche a Ollama spento. Qui si guarda davvero:
    si chiede l'elenco dei modelli con un tetto breve. Serve all'app per non
    offrire l'interruttore — e non dire "disponibile" — quando ogni comando
    finirebbe in silenzio sulle regole.

    Un guasto di rete non e' un errore: vuol dire "non pronto". Non si solleva
    niente, perche' l'app funziona lo stesso col parser a regole.
    """
    if not configurato():
        return False
    indirizzo = _endpoint_salute(base_url())
    if not indirizzo:
        return False
    intestazioni = {"User-Agent": "IlMaggiordomo"}
    # La chiave non serve a Ollama, ma un servizio in rete la pretende: se c'e'
    # si manda, se no si prova lo stesso (Ollama risponde anche senza).
    if chiave():
        intestazioni["Authorization"] = f"Bearer {chiave()}"
    try:
        richiesta = urllib.request.Request(indirizzo, headers=intestazioni)
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT_VERIFICA):
            return True
    except (OSError, ValueError):
        return False


def messaggio_stato() -> str:
    """Cosa manca per capire i comandi col modello, se manca qualcosa.

    Vuoto quando e' pronto. Altrimenti dice la **causa** e cosa fare: il sintomo
    «il modello non capisce» ha tre cause — nessuna chiave, Ollama spento,
    modello non scaricato — che danno lo stesso effetto, e distinguerle e'
    l'unica cosa che serve per uscirne.
    """
    if chiave():
        return ""
    if not _e_locale():
        return ("Per capire i comandi con un modello serve una chiave: registrala "
                "come segreto LLM_API_KEY prima di avviare l'app, oppure avvia un "
                "modello in casa (Ollama).")
    if raggiungibile():
        return ""
    modello_atteso = modello()
    return (f"Ollama non risponde su {base_url()}. Aprilo (deve stare nella tray) "
            f"e assicurati che il modello «{modello_atteso}» sia scaricato "
            f"(ollama pull {modello_atteso}). Senza, l'app usa le regole.")


def _giorni_promemoria(valore) -> int:
    """Quanti giorni prima avvisare, entro i limiti. Zero e' il giorno stesso."""
    try:
        n = int(valore)
    except (TypeError, ValueError):
        return 0
    return max(0, min(365, n))


def _ripulisci(dati: dict) -> dict:
    """Tiene solo un comando che il parser saprebbe eseguire.

    Il modello puo' inventare un intento che non esiste, un'unita' che non
    conosciamo, o una quantita' che non e' un numero: ognuno di questi campi,
    se passasse, farebbe scrivere qualcosa di sbagliato nel database. Qui si
    scarta tutto quello che non e' previsto, e se resta poco il comando non
    parte. Meglio "non ho capito" di una voce sbagliata in dispensa."""
    if not isinstance(dati, dict):
        return {"intent": "unknown"}
    intento = str(dati.get("intent") or "").strip()
    if intento not in INTENTI:
        return {"intent": "unknown"}

    def testo(v):
        return str(v).strip() if isinstance(v, (str, int, float)) else ""

    def quantita(v):
        # l'unita' e' gia' validata altrove; qui solo il numero, che puo' essere
        # arrivato come stringa ("2") ed e' comunque un numero
        try:
            n = float(v)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    def unita(v):
        u = str(v or "").strip().lower()
        return u if u in UNITA else None

    comando = {"intent": intento}
    if intento in ("pantry_add", "pantry_remove", "pantry_consume",
                   "shopping_add", "storage_add"):
        nome = testo(dati.get("name"))
        if not nome:
            return {"intent": "unknown"}
        comando["name"] = nome
        comando["quantity"] = quantita(dati.get("quantity"))
        comando["unit"] = unita(dati.get("unit"))
        if intento == "storage_add":
            comando["place"] = testo(dati.get("place")) or None
            comando["category"] = testo(dati.get("category")) or None
    elif intento in ("shopping_remove", "shopping_check", "recipe_cooked"):
        nome = testo(dati.get("name"))
        if not nome:
            return {"intent": "unknown"}
        comando["name"] = nome
    elif intento == "term_add":
        grezzo = dati.get("terms")
        if isinstance(grezzo, str):
            grezzo = [grezzo]
        termini = [testo(t) for t in (grezzo or []) if testo(t)]
        if not termini:
            return {"intent": "unknown"}
        comando["terms"] = termini
    elif intento == "recipe_search":
        q = testo(dati.get("query") or dati.get("name"))
        if not q:
            return {"intent": "unknown"}
        comando["query"] = q
    elif intento == "recipe_add":
        comando["name"] = testo(dati.get("name"))
        items = []
        for it in (dati.get("items") or []):
            if not isinstance(it, dict):
                continue
            n = testo(it.get("name"))
            if not n:
                continue
            items.append({"name": n, "quantity": quantita(it.get("quantity")),
                          "unit": unita(it.get("unit"))})
        comando["items"] = items
        if not comando["name"] and not items:
            return {"intent": "unknown"}
    elif intento == "event_add":
        nome = testo(dati.get("name"))
        if not nome:
            return {"intent": "unknown"}
        comando["name"] = nome
        # la data dev'essere una data vera: una inventata farebbe un impegno nel
        # giorno sbagliato, che e' peggio di un impegno mancato. Il modello la
        # rende in ISO; se non ci riesce, si prova il parser a regole piu' sotto.
        quando = testo(dati.get("when_date"))[:10]
        try:
            date.fromisoformat(quando)
        except ValueError:
            return {"intent": "unknown"}
        comando["when_date"] = quando
        ora = testo(dati.get("time"))
        comando["time"] = ora[:5] if re.match(r"^\d{1,2}:\d{2}$", ora) else ""
        comando["category"] = testo(dati.get("category")) or None
        comando["reminder_days"] = _giorni_promemoria(dati.get("reminder_days"))
    elif intento == "domanda":
        area = testo(dati.get("area")).lower()
        if area not in AREE:
            return {"intent": "unknown"}
        comando["area"] = area
        comando["query"] = testo(dati.get("query"))
    return comando


def _estrai_json(testo: str) -> dict | None:
    """Trova l'oggetto JSON nella risposta, anche se attorno c'e' altro testo.

    Con `response_format` il modello restituisce JSON puro, ma non tutti i
    servizi compatibili lo rispettano: si prende il primo {...} e lo si interpreta.
    """
    testo = (testo or "").strip()
    if not testo:
        return None
    try:
        return json.loads(testo)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", testo, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def chiama(testo: str) -> dict | None:
    """Chiede al modello di interpretare la frase. `None` se non si puo'.

    `None` vuol dire "usa il parser a regole": non si distingue fra chiave
    assente, rete giu' e risposta storta, perche' in tutti e tre i casi la cosa
    giusta da fare e' la stessa e non serve dirlo a chi ha parlato.
    """
    if not configurato():
        return None
    frase = (testo or "").strip()
    if not frase:
        return None

    corpo = json.dumps({
        "model": modello(),
        "messages": [
            {"role": "system", "content": istruzioni()},
            {"role": "user", "content": frase},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    richiesta = urllib.request.Request(
        f"{base_url()}/chat/completions",
        data=corpo,
        headers={
            "Authorization": f"Bearer {chiave()}",
            "Content-Type": "application/json",
            "User-Agent": "IlMaggiordomo",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=timeout()) as risposta:
            dati = json.loads(risposta.read().decode("utf-8"))
    except (OSError, ValueError):
        # URLError, timeout, DNS, risposta illeggibile: sono tutti lo stesso caso
        # per chi ha parlato, e la cosa giusta e' la stessa — si ricade sul parser
        # senza dire niente. Il corpo di un eventuale HTTPError non si riporta:
        # puo' contenere dettagli della risorsa.
        return None

    try:
        contenuto = dati["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return _ripulisci(_estrai_json(contenuto) or {})