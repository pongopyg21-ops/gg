"""Comprensione dei comandi col modello (facoltativa).

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_comprensione_valida_solo_un_intento_che_esiste():
    """Un intento inventato dal modello non deve arrivare all'esecuzione."""
    assert comprensione._ripulisci({"intent": "spegni_la_luce"})["intent"] == "unknown"
    assert comprensione._ripulisci({"intent": "shopping_add", "name": "latte"})["intent"] == "shopping_add"
    # senza nome non c'e' niente da scrivere: meglio non capire che scrivere vuoto
    assert comprensione._ripulisci({"intent": "shopping_add"})["intent"] == "unknown"

def test_comprensione_scarta_unita_e_quantita_non_previste():
    """Un'unita' fuori elenco o una quantita' non numerica vanno scartate, non
    passate: e' la differenza fra "non ho capito" e una voce sbagliata in dispensa."""
    c = comprensione._ripulisci({"intent": "pantry_add", "name": "farina",
                                 "quantity": "due", "unit": "cucchiaiate"})
    assert c["name"] == "farina"
    assert c["quantity"] is None    # "due" non e' un numero: il client mettera' 1
    assert c["unit"] is None        # unita' sconosciuta: si usa pz
    c = comprensione._ripulisci({"intent": "pantry_add", "name": "farina",
                                 "quantity": 2, "unit": "kg"})
    assert c["quantity"] == 2.0 and c["unit"] == "kg"

def test_comprensione_legge_il_json_anche_con_testo_attorno():
    """Non tutti i servizi rispettano `response_format`: si prende il primo oggetto."""
    assert comprensione._estrai_json('{"intent": "unknown"}') == {"intent": "unknown"}
    assert comprensione._estrai_json('Ecco: {"intent": "unknown"} grazie') == {"intent": "unknown"}
    assert comprensione._estrai_json("nessun json qui") is None

def test_comprensione_senza_chiave_ne_modello_non_e_configurata(monkeypatch):
    """Senza chiave **e** con un endpoint in rete non c'e' un modello: la
    comprensione resta a regole. (Un endpoint locale, come Ollama, invece vale
    anche senza chiave: vedi il test qui sotto.)"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://esempio.invalid/v1")
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    assert not comprensione.configurato()
    assert comprensione.chiama("aggiungi il latte alla spesa") is None

def test_un_modello_in_casa_non_richiede_una_chiave(monkeypatch):
    """Ollama non usa chiavi: l'endpoint locale da solo basta. E' la
    configurazione predefinita, e senza questo resterebbe spenta."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    assert comprensione.configurato()

def test_la_disponibilita_non_basta_serve_che_il_modello_risponda(monkeypatch):
    """Il difetto che questo corregge: l'endpoint locale predefinito c'e' sempre,
    quindi `configurato()` era vero anche a Ollama spento. L'app diceva
    "disponibile" e l'interruttore si accendeva, ma ogni comando finiva in
    silenzio sulle regole. `raggiungibile()` guarda davvero se risponde."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    # configurazione presente, ma nessuno risponde
    monkeypatch.setattr(comprensione.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("connessione rifiutata")))
    assert comprensione.configurato() is True
    assert comprensione.raggiungibile() is False
    # e l'avviso dice la causa vera, non "manca la chiave"
    msg = comprensione.messaggio_stato()
    assert "Ollama non risponde" in msg and "ollama pull" in msg

def test_se_il_modello_risponde_la_verifica_passa(monkeypatch):
    """Con Ollama che risponde la verifica passa, e l'indirizzo interrogato e'
    quello giusto: l'elenco dei modelli sta in `/api/tags`, non in `/v1`."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    finto = _ModelloFinto()
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", finto)
    assert comprensione.raggiungibile() is True
    assert finto.url and finto.url[0].endswith("/api/tags")
    assert comprensione.messaggio_stato() == ""

def test_con_una_chiave_ma_servizio_muto_l_avviso_nomina_la_chiave(monkeypatch):
    """Un servizio in rete con la chiave ma che non risponde: la causa non e'
    Ollama, quindi l'avviso non deve parlare di Ollama."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setenv("LLM_BASE_URL", "https://esempio.invalid/v1")
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    monkeypatch.setattr(comprensione.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("rete assente")))
    assert comprensione.raggiungibile() is False
    # con la chiave presente l'avviso e' vuoto: la configurazione e' completa,
    # e' solo il servizio a non rispondere. Non si accusa la chiave.
    assert comprensione.messaggio_stato() == ""

def test_la_chiave_del_modello_si_legge_da_segreto_txt(tmp_path, monkeypatch):
    """`chiave: valore` come per la voce: chi configura non deve sapere i nomi
    delle variabili. Il modello e l'indirizzo si leggono dallo stesso file."""
    _con_segreto_llm(tmp_path, monkeypatch,
                     "chiave: sk-llm-di-prova-123\n"
                     "modello: qwen2.5:7b-instruct\n"
                     "base_url: https://esempio.invalid/v1\n")
    assert comprensione.chiave() == "sk-llm-di-prova-123"
    assert comprensione.modello() == "qwen2.5:7b-instruct"
    assert comprensione.base_url() == "https://esempio.invalid/v1"
    assert comprensione.configurato()

def test_la_chiave_del_modello_nuda_si_riconosce(tmp_path, monkeypatch):
    """Il file piu' semplice: una riga e basta. Una parola che sembra una chiave
    (`sk-...`) e' la chiave; una parola minuscola corta non la ruba."""
    _con_segreto_llm(tmp_path, monkeypatch, "sk-llm-di-prova-123\n")
    assert comprensione.chiave() == "sk-llm-di-prova-123"

def test_una_spiegazione_nel_file_non_diventa_la_chiave_del_modello(tmp_path, monkeypatch):
    """Le righe con spazi sono testo libero: non devono finire nell'ambiente."""
    _con_segreto_llm(tmp_path, monkeypatch,
                     "Questa e' la chiave del modello, non copiarla in giro\n"
                     "chiave: sk-llm-di-prova-123\n")
    assert comprensione.chiave() == "sk-llm-di-prova-123"

def test_l_ambiente_vince_sul_file_per_la_chiave_del_modello(tmp_path, monkeypatch):
    """Chi esporta la chiave a mano comanda, come per `segreto.sh`."""
    _con_segreto_llm(tmp_path, monkeypatch, "chiave: DalFile\n")
    monkeypatch.setenv("LLM_API_KEY", "DallAmbiente")
    assert comprensione.chiave() == "DallAmbiente"

def test_il_modello_e_l_indirizzo_predefiniti_sono_quelli_di_casa(monkeypatch):
    """Senza nessuna scelta la configurazione e' Ollama in locale: nessuna
    chiave, nessun costo, niente che esce di casa."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    assert comprensione.modello() == "qwen2.5:7b-instruct"
    assert comprensione.base_url() == "http://127.0.0.1:11434/v1"

def test_ollama_si_riconosce_dall_indirizzo_locale(monkeypatch):
    """Un modello in casa non chiede una chiave: si riconosce dall'indirizzo,
    perche' non c'e' altro modo di saperlo. Un servizio in rete no."""
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    for locale in ("http://127.0.0.1:11434/v1", "http://localhost:11434/v1"):
        monkeypatch.setenv("LLM_BASE_URL", locale)
        assert comprensione._e_locale(), locale
    monkeypatch.setenv("LLM_BASE_URL", "https://api.esempio.invalid/v1")
    assert not comprensione._e_locale()

def test_l_elenco_dei_modelli_dipende_dalla_porta_di_ollama(monkeypatch):
    """Ollama tiene l'elenco in `/api/tags`, non nella parte compatibile OpenAI:
    da `.../v1` si risale a `/api/tags`. Un servizio in rete risponde a `/models`."""
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    assert comprensione._endpoint_salute("http://127.0.0.1:11434/v1").endswith("/api/tags")
    assert comprensione._endpoint_salute("http://127.0.0.1:8080/v1").endswith("/models")
    assert comprensione._endpoint_salute("non-un-indirizzo") == ""

def test_la_chiave_del_modello_non_si_salva_dall_app(client):
    """Come per la voce: la chiave LLM entra solo dall'ambiente o dal file prima
    di avviare. L'app puo' nominarla in un avviso («registrala come segreto
    LLM_API_KEY»), ma non deve avere un campo che la scriva, ne' una rotta che la
    salvi: chi apre la pagina potrebbe cambiarla, e la chiave finirebbe in una
    richiesta HTTP."""
    html = client.get("/static/index.html").get_data(as_text=True)
    # nessun campo dove incollare la chiave del modello
    for campo in ('id="llm-chiave"', 'id="llm-chiave-salva"', 'id="voice-llm-chiave"'):
        assert campo not in html, campo
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "salvaChiaveLlm" not in js
    assert "/api/llm/configura" not in js
    # e la rotta non esiste: senza, la chiave non si potrebbe scrivere via HTTP
    percorsi = {r.rule for r in app_module.app.url_map.iter_rules()}
    assert not any("llm" in p.lower() and "configur" in p.lower() for p in percorsi)

def test_comprensione_chiama_il_modello_e_ne_interpreta_la_risposta(monkeypatch):
    """Si prova la richiesta vera, non solo l'interpretazione: la chiave va
    nell'intestazione e il modello richiesto e' quello configurato."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setenv("LLM_MODEL", "modello-di-prova")
    catturato = {}

    def finta(richiesta, timeout=None):
        catturato["url"] = richiesta.full_url
        catturato["aut"] = richiesta.headers.get("Authorization")
        catturato["corpo"] = json.loads(richiesta.data.decode())
        return _RispostaLlm('{"intent": "shopping_add", "name": "latte", "quantity": 1, "unit": "pz"}')

    monkeypatch.setattr(comprensione.urllib.request, "urlopen", finta)
    cmd = comprensione.chiama("dammi il latte")
    assert cmd["intent"] == "shopping_add" and cmd["name"] == "latte"
    assert catturato["aut"] == "Bearer chiave-llm-di-prova"
    assert catturato["corpo"]["model"] == "modello-di-prova"
    assert catturato["url"].endswith("/chat/completions")
    assert "latte" in catturato["corpo"]["messages"][-1]["content"]

def test_la_comprensione_lascia_budget_ai_modelli_di_ragionamento(monkeypatch):
    """Il tetto di token non deve strozzare i modelli che "pensano" prima di
    rispondere: il ragionamento spende lo stesso budget, e con un tetto stretto il
    JSON arriva troncato o vuoto. L'app ripiegherebbe in silenzio sulle regole e
    sembrerebbe che il modello non capisca. Un tetto largo non costa sugli altri
    modelli: si fermano da soli."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    catturato = {}

    def finta(richiesta, timeout=None):
        catturato["corpo"] = json.loads(richiesta.data.decode())
        return _RispostaLlm('{"intent": "unknown"}')

    monkeypatch.setattr(comprensione.urllib.request, "urlopen", finta)
    comprensione.chiama("dammi il latte")
    assert catturato["corpo"]["max_tokens"] >= 1024

def test_il_tempo_di_attesa_del_modello_si_puo_allungare(monkeypatch):
    """Un modello locale (Ollama su CPU) impiega diversi secondi a rispondere: il
    tetto del cloud lo farebbe scadere sempre, e si ricadrebbe in silenzio sulle
    regole. `LLM_TIMEOUT` lo allunga; senza la variabile resta il predefinito."""
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    assert comprensione.timeout() == comprensione.TIMEOUT
    monkeypatch.setenv("LLM_TIMEOUT", "30")
    assert comprensione.timeout() == 30.0
    monkeypatch.setenv("LLM_TIMEOUT", "non-un-numero")
    assert comprensione.timeout() == comprensione.TIMEOUT

def test_comprensione_ripiega_in_silenzio_se_il_modello_non_risponde(monkeypatch):
    """Un errore di rete non deve diventare un errore per chi ha parlato: si
    restituisce `None`, e il chiamante usa il parser a regole."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")

    def esplode(*a, **k):
        raise OSError("rete assente")

    monkeypatch.setattr(comprensione.urllib.request, "urlopen", esplode)
    assert comprensione.chiama("aggiungi il latte alla spesa") is None

def test_senza_modello_l_interruttore_non_si_accende(client, monkeypatch):
    """Accendere una cosa che non c'e' confonderebbe: si risponde 400 dicendo
    quale variabile registrare."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://esempio.invalid/v1")
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    r = client.put("/api/voce/llm", json={"abilitato": True})
    assert r.status_code == 400
    assert "LLM_API_KEY" in r.get_json()["error"]

def test_interruttore_del_modello_si_salva_per_casa(client, monkeypatch):
    """La scelta e' dell'utente e resta; e la chiave non compare mai nella risposta.

    Il modello e' finto ma **risponde**: da quando l'interruttore si accende solo
    se risponde, una chiave da sola non basta piu'."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
    r = client.put("/api/voce/llm", json={"abilitato": True})
    assert r.status_code == 200 and r.get_json()["llm_abilitato"] is True
    cfg = client.get("/api/voce/config").get_json()
    assert cfg["llm_disponibile"] is True and cfg["llm_abilitato"] is True
    assert "chiave-llm-di-prova" not in json.dumps(cfg)
    # e si puo' spegnere
    assert client.put("/api/voce/llm", json={"abilitato": False}).get_json()["llm_abilitato"] is False

def test_con_l_interruttore_spento_la_comprensione_resta_a_regole(client, monkeypatch):
    """Con l'interruttore spento (o la chiave assente) non si chiama nessuno:
    la comprensione e' quella del parser, identica a prima."""
    def non_chiamare(*a, **k):
        raise AssertionError("il modello non deve essere chiamato")

    monkeypatch.setattr(comprensione, "chiama", non_chiamare)
    r = client.post("/api/voice", json={"text": "aggiungi il latte alla spesa"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "shopping_add"

def test_la_comprensione_col_modello_corregge_la_frase_che_il_parser_sbaglia(client, monkeypatch):
    """Il caso che ha motivato tutto: "metti via il vino in cantina" finiva in
    magazzino con l'articolo chiamato "via il vino". Col modello il nome e' "vino".

    Il modello e' finto: si prova l'**integrazione** — che la sua risposta vinca
    su quella del parser e finisca davvero nel database."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
    client.put("/api/voce/llm", json={"abilitato": True})
    monkeypatch.setattr(comprensione, "chiama", lambda t: {
        "intent": "storage_add", "name": "vino", "quantity": None, "unit": None,
        "place": "Cantina", "category": None})
    r = client.post("/api/voice", json={"text": "metti via il vino in cantina"})
    assert r.status_code == 200
    dati = r.get_json()
    assert dati["intent"] == "storage_add"
    assert dati["name"] == "vino"
    # e il nome sbagliato del parser non e' finito nel magazzino
    mag = client.get("/api/storage").get_json()
    nomi = [v["name"] for v in (mag.get("items", mag) if isinstance(mag, dict) else mag)]
    assert "vino" in nomi and "via il vino" not in nomi

def test_se_il_modello_non_capisce_si_usa_il_parser(client, monkeypatch):
    """`unknown` dal modello non cancella quello che il parser sapeva gia' fare."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
    client.put("/api/voce/llm", json={"abilitato": True})
    monkeypatch.setattr(comprensione, "chiama", lambda t: {"intent": "unknown"})
    r = client.post("/api/voice", json={"text": "aggiungi il latte alla spesa"})
    assert r.get_json()["intent"] == "shopping_add"

def test_la_comprensione_e_disattiva_di_partenza(client):
    """Nessuna chiamata a consumo senza che l'utente l'abbia accesa."""
    assert client.get("/api/voce/config").get_json()["llm_abilitato"] is False

def test_non_si_accende_l_interruttore_se_il_modello_non_risponde(client, monkeypatch):
    """L'endpoint locale predefinito c'e' sempre, anche a Ollama spento: senza
    questa guardia l'interruttore si accendeva e ogni comando finiva in silenzio
    sulle regole. Ora la rotta chiede che il modello **risponda**, e se no dice
    la causa (Ollama spento / modello non scaricato), non "manca la chiave"."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    monkeypatch.setattr(comprensione.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("connessione rifiutata")))
    r = client.put("/api/voce/llm", json={"abilitato": True})
    assert r.status_code == 400
    assert "Ollama non risponde" in r.get_json()["error"]
    cfg = client.get("/api/voce/config").get_json()
    assert cfg["llm_pronto"] is False and cfg["llm_abilitato"] is False

def test_lo_stato_distingue_configurato_da_raggiungibile(client, monkeypatch):
    """`/api/voce/config` espone le due cose separatamente: `disponibile` (c'e'
    la configurazione) e `pronto` (il modello risponde). E' la distinzione che
    mancava e che faceva mentire il pannello."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
    cfg = client.get("/api/voce/config").get_json()
    assert cfg["llm_disponibile"] is True and cfg["llm_pronto"] is True
    assert cfg["llm_manca"] == ""

def test_app_js_non_chiama_funzioni_che_non_esiste(client):
    """Un riferimento a una funzione rimossa non deve restare in `app.js`.

    Non e' un'ipotesi: e' successo con `caricaVoci`, tolta insieme alla scheda
    Voce ma lasciata in `init()`. `init()` solleva il ReferenceError **dopo** che
    il login e' riuscito, quindi l'errore finisce nel `catch` di `avviaApp` e
    l'utente, appena entra, resta sulla schermata di accesso con la casa non
    collegata a schermo: l'app "si blocca e si chiude". Nessun test lo vedeva,
    perche' nessuno eseguiva `init()` intera."""
    js = client.get("/static/app.js").get_data(as_text=True)
    orfane = _nomi_chiamati_senza_definizione(js)
    assert not orfane, (
        "app.js chiama funzioni che non esistono: " + ", ".join(orfane))

def test_gli_errori_non_gestiti_avvisano_e_finiscono_nel_registro(client):
    """Il gestore non ripara, ma **dice**: un errore non gestito produce un
    avviso breve a schermo e una riga nel registro, e una raffica non ripete
    l'avviso. E' la rete che mancava: senza, un errore a runtime spariva in
    silenzio e l'app sembrava bloccarsi."""
    js = client.get("/static/app.js").get_data(as_text=True)
    corpo = _estrai_funzione_js(js, "erroreNonGestito")
    prova = """
const log = [];
let erroreInCorso = false;
function registra(m, t) { log.push('registra:' + m + ':' + t); }
function toast(m) { log.push('toast:' + m); }
const timer = [];
function setTimeout(fn) { timer.push(fn); return timer.length; }
""" + corpo + """
erroreNonGestito(new Error('primo'));
erroreNonGestito(new Error('secondo'));   // raffica: un solo avviso
timer[0]();                                // passato il momento, si puo' riavvisare
erroreNonGestito(new Error('terzo'));
console.log(JSON.stringify(log));
"""
    log = _esegui_node(prova)
    avvisi = [v for v in log if v.startswith('toast:')]
    registri = [v for v in log if v.startswith('registra:')]
    assert len(avvisi) == 2, log           # primo e terzo, non il secondo
    assert len(registri) == 3, log         # nel registro ci vanno tutti
    # il testo a schermo non porta il nome dell'eccezione ne' la traccia
    assert all('Error' not in v and 'at ' not in v for v in registri), registri

def test_gli_errori_non_gestiti_sono_ascoltati(client):
    """La registrazione degli eventi e' il legame che rende utile il gestore:
    senza, `erroreNonGestito` non verrebbe mai chiamato."""
    import re
    js = client.get("/static/app.js").get_data(as_text=True)
    m = re.search(r"if \(typeof window[^\n]*\n(?:.*\n)*?\}", js)
    assert m, "non trovo la registrazione degli eventi d'errore"
    prova = """
const sentiti = [];
const window = { addEventListener: (t, f) => sentiti.push([t, f]) };
let chiamate = 0;
function erroreNonGestito() { chiamate++; }
""" + m.group(0) + """
for (const [tipo, f] of sentiti) {
  if (tipo === 'error') f({ error: new Error('x') });
  if (tipo === 'unhandledrejection') f({ reason: new Error('y') });
}
console.log(JSON.stringify({ tipi: sentiti.map((s) => s[0]), chiamate }));
"""
    d = _esegui_node(prova)
    assert d["tipi"] == ["error", "unhandledrejection"], d
    assert d["chiamate"] == 2, d

def test_un_avvio_fallito_non_riporta_all_accesso(client):
    """Se la sessione c'e' ma `init()` fallisce, l'utente resta **dentro** con
    un avviso e "Ricarica": rimandarlo all'accesso gli farebbe credere di aver
    sbagliato la password. Solo se la **sessione** non risponde si torna
    all'accesso. E' la differenza che rendeva il difetto di `caricaVoci`
    indistinguibile da un problema di credenziali."""
    js = client.get("/static/app.js").get_data(as_text=True)
    corpo = _estrai_funzione_js(js, "avviaApp")
    prova = """
const log = [];
let scenario = 'sessione-giu';
async function api() {
  if (scenario === 'sessione-giu') throw new Error('server giu');
  return { authenticated: scenario !== 'anonimo' };
}
async function init() {
  if (scenario === 'init-giu') throw new Error('guasto');
  log.push('init-ok');
}
function mostraAccesso() { log.push('mostraAccesso'); }
function mostraErrore() { log.push('mostraErrore'); }
function mostraErroreApp() { log.push('mostraErroreApp'); }
function registra() { log.push('registra'); }
async function avviaAccesso() { log.push('avviaAccesso'); }
""" + corpo + """
(async () => {
  const esiti = {};
  for (const s of ['sessione-giu', 'anonimo', 'init-giu', 'collegato']) {
    scenario = s; log.length = 0;
    await avviaApp();
    esiti[s] = log.slice();
  }
  console.log(JSON.stringify(esiti));
})();
"""
    e = _esegui_node(prova)
    assert e["sessione-giu"] == ["mostraAccesso", "mostraErrore"], e
    assert e["anonimo"] == ["avviaAccesso"], e
    assert e["init-giu"] == ["registra", "mostraErroreApp"], e
    assert e["collegato"] == ["init-ok"], e


# ---------------------------------------------------------------- impegni col modello

def test_il_modello_puo_programmare_un_impegno(client, monkeypatch):
    """Con l'interruttore acceso, un impegno detto a voce col modello viene creato."""
    domani = (date.today() + timedelta(days=1)).isoformat()
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
    client.put("/api/voce/llm", json={"abilitato": True})
    monkeypatch.setattr(comprensione, "chiama", lambda t: {
        "intent": "event_add", "name": "dentista", "when_date": domani,
        "time": "15:00", "category": "salute", "reminder_days": 1})
    r = client.post("/api/voice", json={"text": "ricordami il dentista domani alle 15"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "event_add"
    giorno = client.get(f"/api/appointments?giorno={domani}").get_json()
    voce = next(a for a in giorno["appointments"] if a["title"] == "dentista")
    assert voce["reminder_days"] == 1


def test_l_impegno_del_modello_con_data_inventata_non_parte(client, monkeypatch):
    """Una data storta dal modello non diventa un impegno nel giorno sbagliato:
    si scarta, e il parser a regole prova la sua."""
    cmd = comprensione._ripulisci({"intent": "event_add", "name": "dentista",
                                   "when_date": "non-una-data"})
    assert cmd["intent"] == "unknown"
