"""Helper, costanti e classi condivisi dai test.

Estratto da `test_cucina.py` quando era un file solo: i test sono spezzati
per modulo, ma gli helper e le costanti restano qui, in un posto solo.
Le fixture stanno in `conftest.py`, come vuole pytest. Ogni file di test fa
`from test_comuni import *`.
"""
import base64

import json

import os

import re

import sqlite3

import tempfile

import time

import urllib.parse

from contextlib import closing

from datetime import date, timedelta

import pytest

import app as app_module  # noqa: E402

import allergens  # noqa: E402

import calendario  # noqa: E402

import cassaforte  # noqa: E402

import cinema  # noqa: E402

import comprensione  # noqa: E402

import copie  # noqa: E402

import dispensa  # noqa: E402

import houses  # noqa: E402

import igiene  # noqa: E402

import units  # noqa: E402

import voice  # noqa: E402

import voce_cloud  # noqa: E402

import ricette_online  # noqa: E402

import tv  # noqa: E402


__all__ = [
    "BASE_APP",
    "CASA_TEST",
    "DB",
    "FEED_NOTIZIE",
    "FEED_PLAYLIST",
    "MET_OPERA",
    "PASSWORD_TEST",
    "PNG_1PX",
    "REGISTRO",
    "_Ascolto",
    "_ModelloFinto",
    "_RispostaLlm",
    "_apri_tmdb",
    "_apri_tmdb_a_pagine",
    "_ascolta_senza_campioni_js",
    "_cenno_js",
    "_con_chiave",
    "_con_segreto",
    "_con_segreto_llm",
    "_costanti_snake",
    "_decisione_js",
    "_deve_accendere_js",
    "_esegui_node",
    "_estrai_funzione_js",
    "_feed",
    "_film",
    "_fine_registrazione_js",
    "_finestra_js",
    "_finta_met",
    "_modo_parla_js",
    "_niente_rete",
    "_nomi_chiamati_senza_definizione",
    "_parlaCloud_e_misura",
    "_parla_e_misura",
    "_quiz_finto",
    "_quiz_in_cache",
    "_ricetta_con_ingredienti",
    "_snake_js",
    "_snake_puro",
    "_sorvegliante_js",
    "_spesa_su_giorni",
    "_stato_ascolto_js",
    "_suggerimento_finto",
    "_traduzione_che_rispetta_le_righe",
    "_url_playlist",
    "_verdetto_microfono_js",
    "_voce",
    "allergens",
    "app_module",
    "base64",
    "calendario",
    "cassaforte",
    "cinema",
    "closing",
    "comprensione",
    "copie",
    "crea_ricetta",
    "data_url",
    "date",
    "dispensa",
    "esiste_tabella",
    "finta_rete",
    "finta_tv",
    "houses",
    "igiene",
    "json",
    "nomi_ingredienti",
    "os",
    "pagina_ricetta",
    "pytest",
    "re",
    "registra_casa",
    "ricetta",
    "ricette_online",
    "righe_foto",
    "sqlite3",
    "tempfile",
    "time",
    "timedelta",
    "tv",
    "units",
    "urllib",
    "version_foto",
    "voce_cloud",
    "voce_con_foto",
    "voce_spesa",
    "voice",
]

BASE_APP = os.path.dirname(os.path.abspath(__file__))

DB = os.path.join(tempfile.mkdtemp(), "test.db")

os.environ["CUCINA_DB"] = DB

REGISTRO = os.path.join(os.path.dirname(DB), "test-houses.db")

houses.REGISTRY_PATH = REGISTRO

houses.CASE_DIR = os.path.join(os.path.dirname(DB), "test-case")

houses.DATA_DIR = os.path.dirname(DB)

CASA_TEST = "casa-test"

PASSWORD_TEST = "password-di-prova"

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

FEED_PLAYLIST = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns="http://www.w3.org/2005/Atom">
  <title>GIAGIA-Max</title>
  <entry>
    <yt:videoId>aaa111</yt:videoId>
    <title>Primo video</title>
    <author><name>Canale Uno</name></author>
    <published>2026-01-02T10:00:00+00:00</published>
  </entry>
  <entry>
    <yt:videoId>bbb222</yt:videoId>
    <title>Secondo video</title>
    <author><name>Canale Due</name></author>
    <published>2026-03-04T10:00:00+00:00</published>
  </entry>
</feed>"""

FEED_NOTIZIE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>RSS di Mondo  - ANSA.it</title>
  <item>
    <title>Notizia vecchia</title>
    <link>https://esempio.invalid/vecchia</link>
    <description>Sommario vecchio</description>
    <pubDate>Mon, 01 Jan 2026 08:00:00 +0100</pubDate>
  </item>
  <item>
    <title>Notizia nuova</title>
    <link>https://esempio.invalid/nuova</link>
    <description>Sommario nuovo</description>
    <pubDate>Thu, 02 Apr 2026 09:30:00 +0200</pubDate>
  </item>
</channel></rss>"""

MET_OPERA = {
    "objectID": 436535, "isPublicDomain": True,
    "title": "Wheat Field with Cypresses", "artistDisplayName": "Vincent van Gogh",
    "objectDate": "1889", "medium": "Oil on canvas", "department": "European Paintings",
    "primaryImageSmall": "https://images.metmuseum.org/esempio.jpg",
    "objectURL": "https://www.metmuseum.org/art/collection/search/436535",
}


class _Ascolto:
    """Risposta finta di Azure all'audio breve, per non toccare la rete."""

    def __init__(self, corpo: bytes):
        self._corpo = corpo

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

class _RispostaLlm:
    """Risposta finta di un servizio compatibile con OpenAI."""

    def __init__(self, contenuto: str):
        self._corpo = json.dumps(
            {"choices": [{"message": {"content": contenuto}}]}).encode()

    def read(self): return self._corpo
    def __enter__(self): return self
    def __exit__(self, *a): return False

class _ModelloFinto:
    """Un modello che **risponde**: sia alla verifica di raggiungibilita'
    (`/api/tags` o `/models`), sia alla chat (`/chat/completions`).

    Serve perche' le due cose ora sono distinte: la chiave dice che la
    configurazione c'e', ma l'interruttore si accende solo se il modello
    risponde. Questa classe finge entrambe, cosi' i test provano il percorso
    vero invece di dipendere dalla rete."""

    def __init__(self, contenuto: str = '{"intent": "unknown"}'):
        self.contenuto = contenuto
        self.url = []

    def __call__(self, richiesta, timeout=None):
        self.url.append(richiesta.full_url)
        if richiesta.full_url.endswith(("/api/tags", "/models")):
            return _RispostaLlm('{"models": []}')
        return _RispostaLlm(self.contenuto)


def registra_casa(nome="Casa Test", password=PASSWORD_TEST, db_path=None):
    """Registra la casa di prova e le prepara il database.

    I test delle funzioni (ricette, dispensa, spesa...) non riguardano le case:
    questa casa unica serve a farli girare come prima, quando il database era
    uno solo. I test della separazione fra case creano le proprie.
    """
    houses.init_registro()
    if not houses.esiste(CASA_TEST):
        houses.registra(CASA_TEST, nome, password, db_file="")
    percorso = db_path or houses.db_path(CASA_TEST)
    app_module.init_db(percorso)
    return CASA_TEST

def ricetta(client, name, servings, items):
    r = client.post("/api/recipes", json={"name": name, "servings": servings, "items": items})
    assert r.status_code == 201, r.data
    return r.get_json()["id"]

def nomi_ingredienti(client, q=""):
    return [i["name"] for i in client.get(f"/api/ingredients?q={q}").get_json()]

def voce_spesa(client, nome):
    """Voce della lista della spesa con il dato di dispensa allegato dall'API."""
    for i in client.get("/api/shopping").get_json():
        if i["name"] == nome:
            return i
    raise AssertionError(f"voce {nome!r} assente dalla lista")

def _spesa_su_giorni(client, *giorni):
    """Mette in piano un ingrediente diverso per giorno, poi rigenera la lista."""
    for i, g in enumerate(giorni):
        nome = f"Alimento{i}"
        rid = ricetta(client, nome, 2, [{"name": nome, "quantity": 100, "unit": "g"}])
        client.post("/api/plan", json={"date": g, "meal": "cena", "recipe_id": rid, "servings": 2})
    client.post("/api/shopping/generate",
                json={"start": min(giorni), "end": max(giorni)})

def crea_ricetta(client, **extra):
    body = {"name": "Piatto di prova", "servings": 2, "items": [
        {"name": "Pasta", "quantity": 180, "unit": "g", "category": "Pane e Cereali"}]}
    body.update(extra)
    return client.post("/api/recipes", json=body).get_json()

def _ricetta_con_ingredienti(client, nome, ingredienti):
    """Crea una ricetta passando dall'API, come farebbe il modulo."""
    r = client.post("/api/recipes", json={
        "name": nome,
        "items": [{"name": n, "quantity": q, "unit": u} for n, q, u in ingredienti],
    })
    assert r.status_code == 201
    return r.get_json()["id"]

def data_url(dati=PNG_1PX, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(dati).decode()

def voce_con_foto(client, nome="Sapone"):
    sid = client.post("/api/storage", json={"name": nome, "quantity": 1}).get_json()["id"]
    r = client.post(f"/api/storage/{sid}/photo", json={"image": data_url()})
    assert r.status_code == 200, r.data
    return sid

def version_foto(client, sid):
    """La versione (`?v=`) che il client userebbe per la foto di questa voce."""
    v = next(x for x in client.get("/api/storage").get_json() if x["id"] == sid)
    return v["photo_url"].partition("?v=")[2]

def righe_foto(sid):
    """Quante foto ha questa voce nel database della casa di prova."""
    with closing(sqlite3.connect(houses.db_path(CASA_TEST))) as con:
        return con.execute(
            "SELECT COUNT(*) FROM storage_photos WHERE storage_id = ?", (sid,)).fetchone()[0]

def esiste_tabella(percorso, nome):
    with closing(sqlite3.connect(percorso)) as con:
        return con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (nome,)).fetchone() is not None

def _con_segreto(tmp_path, monkeypatch, testo, nome_file="segreto.txt"):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)
    (tmp_path / nome_file).write_text(testo)

def _decisione_js(client, casi):
    """Esegue la decisione dell'ascolto continuo sul codice vero.

    `decisioneContinuo` e' pura apposta: si prova senza microfono, senza DOM e
    senza attese. E' la regola che decide se un comando parte, e va provata come
    si comporterebbe davvero.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("const VERBI_COMANDO")
    fine = js.index("\n}\n", js.index("function decisioneContinuo")) + 3
    blocco = js[inizio:fine]
    prova = blocco + "\nconsole.log(JSON.stringify(" + casi + "));"
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)

def _finestra_js(client, script):
    """Esegue le funzioni della finestra dopo "Sì." con un orologio finto.

    Il tempo e' l'unico modo di provare una regola a scadenza senza aspettare:
    `Date.now` si sostituisce con un valore che il test fa avanzare a mano."""
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("const ATTESA_COMANDO_MS")
    fine = js.index("\n}\n", js.index("function inAttesaComando")) + 3
    blocco = js[inizio:fine]
    prova = """
let adesso = 1000000;   // non zero: l'orologio vero non parte mai da zero, e
                        // `apertaIl` a zero sarebbe indistinguibile da "mai aperta"
const Date = { now: () => adesso };
let ascoltoContinuo = { inAttesa: 0, apertaIl: 0 };
function avanza(ms) { adesso += ms; }
""" + blocco + "\n" + script
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)

def _sorvegliante_js(client, casi):
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "cicloDaRiavviare")
    costanti = "const BATTITO_MASSIMO_MS = 25000;\n"
    return _esegui_node(costanti + blocco
                        + "\nconsole.log(JSON.stringify(" + casi + "));")

def _ascolta_senza_campioni_js(client):
    """Esegue il registratore vero con un microfono finto muto e misura se e
    quando arriva l'esito. Le costanti sono piccole per non far durare il test
    quanto una frase vera."""
    js = client.get("/static/app.js").get_data(as_text=True)
    pezzi = [_estrai_funzione_js(js, n) for n in ("ampiezza", "fineRegistrazione",
                                                  "ascoltaSulServer")]
    preludio = """
const ASCOLTO_BLOCCO = 4096;
const ASCOLTO_CAMPIONI = 16000;
const ASCOLTO_FINE_MS = 1600;
const ASCOLTO_ATTESA_MS = 200;
const ASCOLTO_MAX_MS = 400;
const ASCOLTO_SILENZIO = 0.012;
let campioniChiamati = false;
let gestoreCampioni = null;
class AudioContextFinto {
  constructor() { this.state = 'running'; this.sampleRate = 16000; }
  createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
  createScriptProcessor() {
    return { connect() {}, disconnect() {},
             // il gestore viene **assegnato** dal codice vero, ma in questa
             // simulazione non viene mai invocato: e' il caso iPhone
             set onaudioprocess(f) { gestoreCampioni = f; } };
  }
  close() {}
  resume() { return Promise.resolve(); }
}
global.window = { AudioContext: AudioContextFinto };
// `navigator` in Node e' un oggetto nativo non assegnabile: va ridefinito
Object.defineProperty(globalThis, "navigator", {
  value: { mediaDevices: {
    getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }),
  } },
  configurable: true,
});
function ampiezza() { return 0; }
function inviaAscolto() { return Promise.resolve({ testo: '' }); }
function $() { return { classList: { add() {}, remove() {} }, focus() {} }; }
function voceStato() {}
function aggiornaParla() {}
function mostraLivello() {}
let voce = { registratore: null, attivo: false, pushAttivo: false, livello: null };
"""
    prova = (preludio + "\n".join(pezzi) + """
const t0 = Date.now();
ascoltaSulServer((d) => {
  console.log(JSON.stringify({ esitoRicevuto: true, gestoreAssegnato: !!gestoreCampioni,
                               campioniChiamati, muto: !!(d && d.muto),
                               ms: Date.now() - t0 }));
  process.exit(0);
});
setTimeout(() => {
  console.log(JSON.stringify({ esitoRicevuto: false, gestoreAssegnato: !!gestoreCampioni,
                               campioniChiamati, muto: null,
                               ms: Date.now() - t0 }));
  process.exit(0);
}, 3000);""")
    return _esegui_node(prova)

def _fine_registrazione_js(client, casi):
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "fineRegistrazione")
    costanti = ("const ASCOLTO_FINE_MS = 1600;\n"
                "const ASCOLTO_ATTESA_MS = 6000;\n"
                "const ASCOLTO_MAX_MS = 15000;\n")
    return _esegui_node(costanti + blocco
                        + "\nconsole.log(JSON.stringify(" + casi + "));")

def _stato_ascolto_js(client, casi):
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "statoAscoltoTesto")
    return _esegui_node(blocco + "\nconsole.log(JSON.stringify(" + casi + "));")

def _verdetto_microfono_js(client, casi):
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "verdettoMicrofono")
    return _esegui_node(blocco + "\nconsole.log(JSON.stringify(" + casi + "));")

def _modo_parla_js(client, casi):
    js = client.get("/static/app.js").get_data(as_text=True)
    blocchi = "\n".join(_estrai_funzione_js(js, n) for n in ("modoParla", "guardaSeRilascia"))
    return _esegui_node(blocchi + "\nconsole.log(JSON.stringify(" + casi + "));")

def _con_chiave(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorth")
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", True)

def pagina_ricetta(nome="Spaghetti alla Carbonara", porzioni="4",
                   ingredienti=("Spaghetti 320 g", "Guanciale 150 g", "Tuorli 6"),
                   passi=("Mettete l'acqua sul fuoco.", "Rosolate il guanciale.")):
    ld = {
        "@context": "https://schema.org", "@type": "Recipe", "name": nome,
        "recipeYield": porzioni, "totalTime": "PT25M",
        "recipeIngredient": list(ingredienti),
        "recipeInstructions": [{"@type": "HowToStep", "text": p} for p in passi],
        "author": {"@type": "Person", "name": "GialloZafferano"},
    }
    return ('<html><head><script type="application/ld+json">'
            + json.dumps(ld) + '</script></head><body>cucina</body></html>')

def finta_rete(monkeypatch, risposte, permesso=True):
    """Sostituisce la lettura di rete con pagine preparate.

    `risposte` e' un dizionario indirizzo -> contenuto. `_permesso` si forza a
    parte perche' il controllo del robots.txt e' una decisione a se': qui interessa
    la lettura della ricetta, e la politica dei permessi ha i suoi test.
    """
    def apri(url):
        if url not in risposte:
            raise ricette_online.NonDisponibile(f"indirizzo di prova non previsto: {url}")
        return risposte[url]
    monkeypatch.setattr(ricette_online, "_apri", apri)
    monkeypatch.setattr(ricette_online, "_permesso", lambda url: permesso)

def _deve_accendere_js(client, casi):
    """Esegue `deveAccendereDaSolo` sul codice vero.

    E' pura apposta: decide se il microfono si apre da solo, e una regola cosi'
    non va provata con permessi finti e un microfono vero attorno.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function deveAccendereDaSolo")
    fine = js.index("\n}\n", inizio) + 3
    blocco = js[inizio:fine]
    prova = blocco + "\nconsole.log(JSON.stringify(" + casi + "));"
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)

def _cenno_js(client, casi):
    """Esegue `cennoDiRicevuto` sul codice vero. Anche questa e' una regola pura:
    decide se l'assistente parla quando ha capito, e va provata come regola, non
    con un microfono e una voce attorno."""
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function cennoDiRicevuto")
    fine = js.index("\n}\n", inizio) + 3
    blocco = js[inizio:fine]
    prova = blocco + "\nconsole.log(JSON.stringify(" + casi + "));"
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)

def _estrai_funzione_js(js, nome):
    """Ritaglia una `function NOME(...) { ... }` con parentesi bilanciate.

    Serve a eseguire il codice vero con node invece di leggerne le stringhe: un
    test sulle stringhe non si accorge se la funzione fa la cosa sbagliata."""
    import re
    m = re.search(r'(?:async\s+)?function ' + nome + r'\s*\(', js)
    assert m, f"non trovo la funzione {nome}"
    inizio = m.start()
    i = js.index('(', m.start())
    par = 0
    while i < len(js):
        if js[i] == '(':
            par += 1
        elif js[i] == ')':
            par -= 1
            if par == 0:
                i += 1
                break
        i += 1
    brace = js.index('{', i)
    depth = 0
    j = brace
    while j < len(js):
        if js[j] == '{':
            depth += 1
        elif js[j] == '}':
            depth -= 1
            if depth == 0:
                j += 1
                break
        j += 1
    return js[inizio:j]

def _esegui_node(prova):
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)

def _parlaCloud_e_misura(client):
    """Esegue `parlaCloud` **vera** con un `Audio` finto ma fedele: `play()`
    risolve all'inizio, l'evento 'ended' arriva dopo. Restituisce l'ordine degli
    eventi, per vedere quando la promessa si chiude."""
    js = client.get("/static/app.js").get_data(as_text=True)
    # `parlaCloud` prende l'audio da `audioCloud` (separata per poter preparare le
    # frasi fisse in anticipo): si estraggono entrambe, cosi' il test esegue il
    # percorso vero e non uno stub che potrebbe divergere
    codice = (_estrai_funzione_js(js, "audioCloud")
              + _estrai_funzione_js(js, "parlaCloud"))
    preludio = """
const log = [];
const CLOUD_CACHE_MAX = 40;
function voceStato() {}
let voceCloud = { disponibile: true, maxCaratteri: 600,
                  sentite: new Map([['it-IT-IsabellaNeural|Ciao.', {}]]) };
function voceCloudScelta() { return 'it-IT-IsabellaNeural'; }
global.URL = { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} };
class Audio {
  play() { log.push('play'); return Promise.resolve(); }
  addEventListener(ev, fn) {
    if (ev === 'ended') setTimeout(() => { log.push('ended'); fn(); }, 40);
  }
}
"""
    prova = (preludio + codice
             + "\nparlaCloud('Ciao.').then(() => log.push('risolta'));"
             + "\nsetTimeout(() => console.log(JSON.stringify(log)), 300);")
    return _esegui_node(prova)

def _parla_e_misura(client, testo):
    """Esegue `parla` **vera** con una `parlaCloud` finta che suona una frase per
    volta, per verificare che le frasi vadano in fila e che il segnale di
    silenzio arrivi solo dopo l'ultima."""
    js = client.get("/static/app.js").get_data(as_text=True)
    pezzi = [_estrai_funzione_js(js, n)
             for n in ("spezzaInFrasi", "avvisaFineParlato", "parla")]
    preludio = """
const log = [];
function voceStato() {}
function $() { return { checked: true }; }
function cloudAttivo() { return true; }
function parlaTesto() {}
let voce = { aFineParlato: () => log.push('FINE-PARLATO') };
function parlaCloud(frase) {
  return new Promise((risolvi) => {
    log.push('suona:' + frase);
    setTimeout(() => { log.push('fine:suona:' + frase); risolvi(true); }, 40);
  });
}
"""
    prova = (preludio + "\n".join(pezzi)
             + "\nparla(" + json.dumps(testo) + ");"
             + "\nsetTimeout(() => console.log(JSON.stringify(log)), 800);")
    return _esegui_node(prova)

def _con_segreto_llm(tmp_path, monkeypatch, testo, nome_file="segreto.txt"):
    """Prepara un `segreto.txt` con la chiave del modello, senza toccare quello vero."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("MAGGIORDOMO_DATA", str(tmp_path))
    monkeypatch.setattr(comprensione, "_letto", {"fatto": False})
    (tmp_path / nome_file).write_text(testo)

def _nomi_chiamati_senza_definizione(js):
    """Ritorna i nomi chiamati come `nome(...)` che non risultano definiti da
    nessuna parte nel file (function, const/let/var, class, parametro).

    E' una scansione testuale, non un vero parser: toglie i commenti, le
    stringhe e i template literal, poi cerca le chiamate. Serve a scoprire un
    riferimento a una funzione **inesistente**, che il browser solleva come
    ReferenceError solo quando quella riga viene raggiunta — quindi un errore
    che sfugge a ogni test che non esegue la pagina intera. E' il caso di
    `caricaVoci`: rimossa con la scheda Voce, ma ancora chiamata in `init()`,
    faceva fallire l'accesso e l'app restava sulla schermata di login."""
    import re

    def senza_commenti_stringhe(s):
        out = []
        i, n = 0, len(s)
        while i < n:
            if s[i:i + 2] == '//':
                j = s.find('\n', i)
                i = n if j < 0 else j
                continue
            if s[i:i + 2] == '/*':
                j = s.find('*/', i + 2)
                i = n if j < 0 else j + 2
                continue
            c = s[i]
            if c in '"\'':
                # stringa mono-riga: se non si chiude sulla stessa riga non e'
                # una stringa (es. apostrofo dentro un commento gia' tolto)
                j, chiusa = i + 1, False
                while j < n and s[j] != '\n':
                    if s[j] == '\\':
                        j += 2
                        continue
                    if s[j] == c:
                        chiusa = True
                        break
                    j += 1
                if chiusa:
                    i = j + 1
                    out.append(' ')
                    continue
                out.append(c)
                i += 1
                continue
            if c == '`':
                j = i + 1
                while j < n:
                    if s[j] == '\\':
                        j += 2
                        continue
                    if s[j] == '`':
                        break
                    j += 1
                i = n if j >= n else j + 1
                out.append(' ')
                continue
            out.append(c)
            i += 1
        return ''.join(out)

    code = senza_commenti_stringhe(js)
    defs = set(re.findall(r'function\s+([A-Za-z_$][\w$]*)', code))
    defs |= set(re.findall(r'(?:const|let|var)\s+([A-Za-z_$][\w$]*)', code))
    defs |= set(re.findall(r'class\s+([A-Za-z_$][\w$]*)', code))
    params = set()
    for m in re.finditer(r'\(([^()]*)\)\s*(?:=>|\{)', code):
        for p in m.group(1).split(','):
            p = p.strip().split('=')[0].strip()
            if re.fullmatch(r'[A-Za-z_$][\w$]*', p):
                params.add(p)
    for m in re.finditer(r'\{([^{}]*)\}\s*=\s*', code):
        for p in re.findall(r'[A-Za-z_$][\w$]*', m.group(1)):
            params.add(p)
    chiamate = re.findall(r'(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(', code)
    parole = {'if', 'for', 'while', 'switch', 'catch', 'return', 'function',
              'typeof', 'new', 'do', 'else', 'in', 'of', 'case', 'delete',
              'void', 'yield', 'await', 'super', 'this', 'async'}
    # nomi forniti dal browser, non definiti nel file
    browser = set("""Array ArrayBuffer Audio Blob Boolean DataView Date Error
File FileReader Float32Array Image JSON Map Math Number Object Promise RegExp Set
String Symbol SpeechSynthesisUtterance parseInt parseFloat isNaN Uint8Array
encodeURIComponent decodeURIComponent fetch setTimeout clearTimeout setInterval
clearInterval confirm alert console requestAnimationFrame cancelAnimationFrame
AudioContext webkitAudioContext MediaRecorder URL URLSearchParams FormData btoa
atob structuredClone queueMicrotask crypto getComputedStyle MutationObserver
Notification localStorage sessionStorage navigator document window""".split())
    return sorted(set(c for c in chiamate
                      if c not in parole and c not in defs
                      and c not in params and c not in browser))

def finta_tv(monkeypatch, risposte):
    """Sostituisce la lettura di rete di `tv` con risposte preparate.

    Le chiavi sono gli indirizzi; un indirizzo non previsto solleva
    `NonDisponibile`, cosi' un test che sbaglia indirizzo se ne accorge invece
    di scaricare davvero."""
    def apri(url):
        if url not in risposte:
            raise tv.NonDisponibile(f"indirizzo di prova non previsto: {url}")
        return risposte[url].encode("utf-8")
    monkeypatch.setattr(tv, "_apri", apri)

def _url_playlist():
    return f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.playlist_id()}"

def _quiz_finto(domanda="Qual e' il pianeta piu' grande?", giusta="Giove",
                sbagliate=("Marte", "Terra", "Venere"), categoria="Science: Astronomy"):
    return json.dumps({"response_code": 0, "results": [
        {"type": "multiple", "difficulty": "medium", "category": categoria,
         "question": domanda, "correct_answer": giusta,
         "incorrect_answers": list(sbagliate)}]})

def _traduzione_che_rispetta_le_righe(monkeypatch, prefisso="IT: "):
    """Un finto servizio di traduzione che antepone un prefisso a ogni riga.

    Qualunque sia l'ordine delle risposte (il server le mescola), il numero di
    righe resta quello: cosi' il test prova la logica di allineamento senza
    dipendere dall'ordine, che e' casuale.
    """
    def apri(url):
        if url == tv.QUIZ_URL:
            return _quiz_finto().encode("utf-8")
        if url.startswith(tv.TRADUZIONE_URL):
            testo = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
            tradotto = "\n".join(prefisso + r for r in testo.split("\n"))
            return json.dumps({"responseData": {"translatedText": tradotto}}).encode("utf-8")
        raise tv.NonDisponibile(f"indirizzo di prova non previsto: {url}")
    monkeypatch.setattr(tv, "_apri", apri)

def _quiz_in_cache(db, testi):
    """Riempie la copia del quiz con domande finte (una per testo)."""
    tv._scrivi(db, "quiz", [
        {"testo": t, "risposte": [{"testo": "A", "giusta": True},
                                  {"testo": "B", "giusta": False}],
         "categoria": "Test", "difficolta": "medio"}
        for t in testi])

def _suggerimento_finto(tipo="recreational", attivita="Impara a fare il pane"):
    return {"activity": attivita, "availability": 0.1, "type": tipo,
            "participants": 2, "price": 0.0,
            "accessibility": "Few to no challenges",
            "duration": "minutes", "kidFriendly": True,
            "link": "", "key": "12345"}

def _finta_met(monkeypatch, opere, ids=None):
    """Sostituisce la rete del Met: la ricerca e i dettagli delle opere date."""
    if ids is None:
        ids = [o["objectID"] for o in opere]
    per_id = {o["objectID"]: o for o in opere}

    def apri(url):
        if url.startswith(tv.MET_RICERCA):
            return json.dumps({"total": len(ids), "objectIDs": ids}).encode("utf-8")
        prefisso = tv.MET_BASE + "/objects/"
        if url.startswith(prefisso):
            oid = int(url[len(prefisso):])
            if oid not in per_id:
                raise tv.NonDisponibile("opera di prova non prevista")
            return json.dumps(per_id[oid]).encode("utf-8")
        raise tv.NonDisponibile(f"indirizzo di prova non previsto: {url}")
    monkeypatch.setattr(tv, "_apri", apri)

def _snake_js(client):
    return client.get("/static/snake.js").get_data(as_text=True)

def _costanti_snake(js):
    """Le misure del campo, lette dal file vero: un test con 15 scritto a mano
    non si accorgerebbe se il gioco cambiasse campo."""
    import re
    d = {}
    for nome in ("SNAKE_COLS", "SNAKE_ROWS"):
        m = re.search(r"const " + nome + r"\s*=\s*(\d+)", js)
        assert m, f"non trovo {nome} in snake.js"
        d[nome] = int(m.group(1))
    return d

def _snake_puro(client, coda):
    """Estrae le funzioni pure e le esegue con node, sulla coda data.

    `rand` finto e deterministico: `snakeNuovo` e `snakePasso` prendono un
    generatore, quindi il test decide dove finisce il cibo invece di sperare."""
    js = _snake_js(client)
    m = _costanti_snake(js)
    codice = "".join(_estrai_funzione_js(js, n)
                     for n in ("snakeNuovo", "snakeCellaLibera", "snakePasso",
                               "snakeDirezione"))
    preludio = (f"const SNAKE_COLS = {m['SNAKE_COLS']};\n"
                f"const SNAKE_ROWS = {m['SNAKE_ROWS']};\n") + codice
    return _esegui_node(preludio + coda)

def _apri_tmdb(principale=None, nicchia=None, scia=None, senza_it=(),
               piattaforme=None):
    """Un `_apri` finto che risponde come TMDB, su tutti i percorsi usati.

    Sono quattro risposte distinte: la scoperta principale, la nicchia (per
    tag), le raccomandazioni (la scia) e il **dettaglio** — che ora porta
    traduzioni e piattaforme insieme, in una chiamata sola. Il dettaglio e'
    quello che dice se un film ha una versione italiana: senza, `_dettagli`
    scarterebbe tutto. Gli id in `senza_it` rispondono senza traduzione `it`,
    cosi' si prova il filtro.
    """
    principale = principale if principale is not None else {"results": []}
    nicchia = nicchia if nicchia is not None else {"results": []}
    scia = scia if scia is not None else {"results": []}

    def apri(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "/recommendations" in url:
            return json.dumps(scia).encode()
        if "/discover/movie" in url:
            return json.dumps(nicchia if "with_keywords" in q else principale).encode()
        m = re.search(r"/movie/(\d+)(?:\?|$)", url)
        if m:
            trad = [] if int(m.group(1)) in senza_it else [{"iso_639_1": "it"}]
            return json.dumps({"translations": {"translations": trad},
                               "watch/providers": piattaforme or {}}).encode()
        return json.dumps({"results": []}).encode()

    return apri

def _apri_tmdb_a_pagine(per_pagina: dict):
    """Un `_apri` finto che distingue le pagine di `discover`.

    `per_pagina` mappa il numero di pagina all'elenco di film. Serve al
    rimpiazzo: pesca da una pagina diversa, e senza questo ogni pagina
    risponderebbe uguale e il rimpiazzo non troverebbe mai niente di nuovo.
    """
    def apri(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "/recommendations" in url:
            return json.dumps({"results": []}).encode()
        if "/discover/movie" in url:
            if "with_keywords" in q:
                return json.dumps({"results": []}).encode()
            pagina = int(q.get("page", ["1"])[0])
            return json.dumps({"results": per_pagina.get(pagina, [])}).encode()
        if re.search(r"/movie/\d+", url):
            return json.dumps({"translations": {"translations": [{"iso_639_1": "it"}]},
                               "watch/providers": {}}).encode()
        return json.dumps({"results": []}).encode()
    return apri

def _film(id_, titolo):
    return {"id": id_, "title": titolo, "release_date": "2026-01-01",
            "vote_average": 7.0, "poster_path": f"/{id_}.jpg", "overview": ""}

def _niente_rete(monkeypatch):
    """Nei test la rete non esiste e il sottofondo non deve partire.

    `/api/tv` riprova a scaricare **dopo** aver risposto, in un filo che apre una
    connessione sua. In un test quel filo sopravvive alla richiesta e, quando
    `monkeypatch` ha gia' rimesso a posto `_apri`, scarica davvero tenendo aperto
    il database di prova: la fixture lo cancella sotto e il test dopo fallisce
    con «disk I/O error». Si spengono entrambe le cose: il guasto di rete e il
    filo di sottofondo.
    """
    monkeypatch.setattr(tv, "_apri",
                        lambda url: (_ for _ in ()).throw(tv.NonDisponibile("test")))
    monkeypatch.setattr(app_module, "_aggiorna_tv_in_sottofondo", lambda db: None)
    monkeypatch.setattr(app_module, "_aggiorna_notizie_in_sottofondo", lambda db: None)
    # il Cinema vive nella sezione TV e ha lo stesso filo: si spegne anche lui,
    # altrimenti un test che apre la sezione lascia un filo che tocca il db di
    # prova mentre la fixture lo cancella
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)

def _feed(titolo, voci):
    return (f"<rss version='2.0'><channel><title>{titolo}</title>"
            + "".join(voci) + "</channel></rss>")

def _voce(n, data="Mon, 01 Jan 2026 08:00:00 +0100"):
    return (f"<item><title>{n}</title><link>https://esempio.invalid/{n}</link>"
            f"<description>S {n}</description><pubDate>{data}</pubDate></item>")

