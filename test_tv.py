"""TV: video, notizie, quiz, arte e suggerimenti.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_il_riepilogo_non_cade_se_una_fonte_non_risponde(client):
    """Se il calendario non risponde, i pasti si mostrano lo stesso: un errore su
    una fonte non deve far sparire le altre."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeOggi")
    preludio = """
const stato = { html: '', nascosto: true };
function $(sel) {
  if (sel === '#home-oggi') return {
    set innerHTML(v) { stato.html = v; }, get innerHTML() { return stato.html; },
    classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } },
  };
  return { innerHTML: '', classList: { add() {}, remove() {} } };
}
function esc(s) { return String(s); }
function iso(d) { return '2026-10-02'; }
function statoScadenza() { return { testo: '—', classe: 'scad-niente' }; }
async function api(url) {
  if (url.startsWith('/api/plan')) return [{ recipe_name: 'Pasta', meal: 'cena' }];
  throw new Error('rete assente');
}
"""
    coda = "\nrenderHomeOggi().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is False
    assert "Pasta" in d["html"]

def test_le_notizie_in_home_stanno_sotto_il_calendario(client):
    """La home finisce con le notizie del giorno: prima le categorie, poi il
    riepilogo «Oggi», il calendario e infine le notizie, che sono da leggere.
    L'elenco completo resta nella sezione TV."""
    html = client.get("/").get_data(as_text=True)
    assert 'id="home-notizie"' in html
    assert html.index('id="home-cal"') < html.index('id="home-notizie"')
    # le notizie chiudono i riquadri: subito dopo c'e' l'intestazione della home
    sezione = html[html.index('id="home-notizie"'):html.index("home-hero-basso")]
    assert "home-notizie-apri" in sezione
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "$('#home-notizie-apri')" in js and "apriSezione('tv')" in js

def test_la_home_mostra_dieci_notizie_non_tutte(client):
    """In home le notizie sono al massimo dieci: e' un assaggio. La sezione TV
    resta con tutte quelle della cache (`MAX_NOTIZIE`, 20), quindi il taglio e'
    della home e non del feed. Si esegue `renderHomeNotizie` vera con node."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeNotizie")
    notizie = [{"titolo": f"Notizia {i}", "link": f"/n/{i}", "fonte": "ANSA"}
               for i in range(20)]
    preludio = """
const stato = { html: '', nascosto: true };
function $(sel) {
  if (sel === '#home-notizie') return { classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } } };
  if (sel === '#home-notizie-elenco') return { set innerHTML(v) { stato.html = v; } };
  return { innerHTML: '' };
}
function esc(s) { return String(s ?? ''); }
const NOTIZIE = %s;
async function api() { return { notizie: NOTIZIE }; }
""" % json.dumps(notizie)
    coda = "\nrenderHomeNotizie().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is False
    assert "Notizia 9" in d["html"]
    assert "Notizia 10" not in d["html"], "in home non si mostrano tutte e venti"
    assert "Notizia 19" not in d["html"]

def test_l_endpoint_notizie_serve_solo_le_notizie_dalla_cache(client, monkeypatch):
    """`/api/notizie` alimenta il riquadro in home: deve portare le notizie e
    quando sono state prese, senza tirare dietro i video della TV (in home non
    si mostrano, e i loro embed sono peso inutile)."""
    finta_tv(monkeypatch, {tv.feed_urls()[0]: FEED_NOTIZIE})
    db = app_module.get_db()
    tv.aggiorna_notizie(db, forse=False)

    r = client.get("/api/notizie")
    assert r.status_code == 200
    d = r.get_json()
    assert len(d["notizie"]) == 2
    assert d["aggiornato"]
    assert "video" not in d

def test_l_endpoint_notizie_non_cade_se_non_c_e_niente(client, monkeypatch):
    """Cache vuota e rete assente: 200 con un elenco vuoto. E' un riquadro da
    riempire, non un guasto da mostrare in home."""
    monkeypatch.setattr(tv, "_apri",
                        lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    monkeypatch.setattr(app_module, "_aggiorna_notizie_in_sottofondo", lambda db: None)
    r = client.get("/api/notizie")
    assert r.status_code == 200
    assert r.get_json()["notizie"] == []

def test_il_riquadro_notizie_in_home_tace_se_non_ce_ne_sono(client):
    """Senza notizie il riquadro resta nascosto, come il riepilogo «Oggi»: una
    home con un riquadro vuoto e' peggio di una home senza riquadro."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeNotizie")
    preludio = """
const stato = { nascosto: false };
function $(sel) {
  if (sel === '#home-notizie') return { classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } } };
  return { innerHTML: '' };
}
function esc(s) { return String(s); }
async function api() { return { notizie: [] }; }
"""
    coda = "\nrenderHomeNotizie().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is True

def test_il_comando_parte_subito_senza_aspettare_la_voce(client):
    """La latenza riferita: il comando partiva solo **dopo** la fine di
    "Comandi.", quindi l'esecuzione restava ferma per tutta la voce — e col
    telefono (trascrizione + voce neurale) sembrava che non eseguisse affatto.

    Si esegue `eseguiComandoContinuo` **vera** con node: il comando dev'essere
    invocato **subito**, prima che la voce finisca, e le due frasi (cenno, esito)
    devono restare in fila, senza sovrapporsi."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = (_estrai_funzione_js(js, "confermaVoce")
              + _estrai_funzione_js(js, "tettoVoceMs")
              + _estrai_funzione_js(js, "eseguiComandoContinuo"))
    preludio = """
const ordine = [];
let risolviCenno, risolviEsito, risolviCmd;
function parlaEAttendi(f) {
  ordine.push('parla:' + f);
  return new Promise((r) => { if (f === 'Comandi.') risolviCenno = r; else risolviEsito = r; });
}
function riprendiDopoLaVoce() { return () => ordine.push('ripartito'); }
function eseguiComando(c, o) {
  ordine.push('esegui:' + c + ':parla=' + (o && o.parla));
  return new Promise((r) => { risolviCmd = r; });
}
function cennoDiRicevuto() { return 'Comandi.'; }
// piccolo apposta: il tetto vero segue la frase, e nel banco non serve — anzi,
// con quello vero il processo node resterebbe vivo a ogni esecuzione dei test
const TETTO_VOCE_MS = 30;
let voce = {};
function $() { return { checked: true }; }
"""
    prova = preludio + blocco + """
(async () => {
  const attendi = () => new Promise((r) => setTimeout(r, 0));
  const p = eseguiComandoContinuo('metti il latte', () => {});
  const subito = ordine.slice();   // prima che qualunque voce sia finita
  risolviCenno && risolviCenno(); await attendi();
  risolviCmd({ message: 'Fatto.' }); await attendi();
  risolviEsito && risolviEsito(); await p;
  console.log(JSON.stringify({ subito, dopo: ordine }));
})();
"""
    d = _esegui_node(prova)
    # il comando e' la **prima** cosa che succede: non aspetta la voce
    assert d["subito"][0] == "esegui:metti il latte:parla=false", d["subito"]
    # l'esecuzione non parla da sola (l'esito lo dice `eseguiComandoContinuo`)
    assert "esegui:metti il latte:parla=false" in d["subito"]
    # e le due frasi si dicono in fila: prima il cenno, poi l'esito
    parlate = [v for v in d["dopo"] if v.startswith("parla:")]
    assert parlate == ["parla:Comandi.", "parla:Fatto."], parlate

def test_i_video_della_playlist_si_leggono_con_i_loro_campi(client, monkeypatch):
    """Il feed Atom della playlist: id, titolo, autore e data.

    La trappola e' il namespace `yt:`: senza passare la mappa dei namespace a
    `find`, ogni campo torna vuoto e la playlist sembra senza video — e' il
    difetto che c'e' stato davvero, e non si vede leggendo il codice."""
    finta_tv(monkeypatch, {_url_playlist(): FEED_PLAYLIST})
    video = tv.video_playlist()
    assert [v["id"] for v in video] == ["aaa111", "bbb222"]
    assert video[0]["titolo"] == "Primo video"
    assert video[0]["autore"] == "Canale Uno"
    assert video[0]["data"] == "2026-01-02"

def test_una_playlist_senza_video_e_un_guasto_non_una_sezione_vuota(client, monkeypatch):
    """Una playlist privata o cancellata risponde senza voci: e' `NonDisponibile`,
    non una lista vuota, cosi' chi chiama tiene la copia vecchia invece di
    sovrascriverla con il vuoto."""
    finta_tv(monkeypatch, {_url_playlist(): "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"})
    with pytest.raises(tv.NonDisponibile):
        tv.video_playlist()

def test_il_gym_legge_la_sua_playlist_non_quella_della_tv(client, monkeypatch):
    """La sezione GYM ha la sua playlist, separata da quella della TV: si guarda
    per fare, non per passare il tempo, e cambiare i video di casa non deve
    toccare l'allenamento. Le due letture sono la stessa funzione (`_video_di`),
    cambia solo l'id: qui si verifica che sia davvero quello giusto."""
    urls = {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}":
            FEED_PLAYLIST,
        _url_playlist(): "<feed xmlns='http://www.w3.org/2005/Atom'></feed>",
    }
    finta_tv(monkeypatch, urls)
    video = tv.video_gym()
    assert [v["id"] for v in video] == ["aaa111", "bbb222"]
    assert tv.gym_playlist_id() == tv.PLAYLIST_GYM_PREDEFINITA

def test_gym_e_tv_si_aggiornano_e_si_leggono_separatamente(client, monkeypatch):
    """I due elenchi vivono in cache separate (`gym` e `video`): aggiornare il
    GYM non deve toccare la TV, ne' viceversa. Se condividessero la chiave, un
    giro del GYM sovrascriverebbe i video della TV."""
    gym_feed = FEED_PLAYLIST.replace("aaa111", "gym111").replace("bbb222", "gym222")
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": gym_feed,
        _url_playlist(): FEED_PLAYLIST,
    })
    db = app_module.get_db()
    assert tv.aggiorna_gym(db, forse=False) is True
    assert tv.aggiorna_video(db, forse=False) is True
    assert [v["id"] for v in tv.gym(db)] == ["gym111", "gym222"]
    assert [v["id"] for v in tv.video(db)] == ["aaa111", "bbb222"]

def test_l_endpoint_gym_serve_la_cache_e_gli_incorpora(client, monkeypatch):
    """L'endpoint GYM serve la copia in cache senza aspettare la rete, e ogni
    video porta l'indirizzo del player (`youtube-nocookie`)."""
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": FEED_PLAYLIST,
    })
    tv.aggiorna_gym(app_module.get_db(), forse=False)
    _niente_rete(monkeypatch)  # il sottofondo non deve partire: la copia e' fresca
    d = client.get("/api/gym").get_json()
    assert len(d["video"]) == 2
    assert d["video"][0]["embed"] == "https://www.youtube-nocookie.com/embed/aaa111"
    assert d["playlist"] == tv.PLAYLIST_GYM_PREDEFINITA
    assert d["aggiornato"]

def test_l_endpoint_gym_non_cade_se_non_c_e_niente(client, monkeypatch):
    """Cache vuota e rete assente: 200 con un elenco vuoto. E' una sezione da
    riempire, non un guasto da mostrare."""
    monkeypatch.setattr(tv, "_apri", lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    r = client.get("/api/gym")
    assert r.status_code == 200
    assert r.get_json()["video"] == []

def test_il_pulsante_gym_riscarica_solo_il_gym(client, monkeypatch):
    """`/api/gym/aggiorna` aspetta la rete (e' l'utente a chiederlo) e riscarica
    **solo** il GYM: le notizie non c'entrano con gli esercizi."""
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": FEED_PLAYLIST,
    })
    r = client.post("/api/gym/aggiorna")
    assert r.status_code == 200
    d = r.get_json()
    assert d["aggiornati"]["gym"] is True
    assert len(d["video"]) == 2
    # la TV non c'entra: il suo elenco resta quello di prima (vuoto), e le
    # notizie non vengono toccate da un aggiornamento del GYM
    _niente_rete(monkeypatch)  # il sottofondo di /api/tv non deve partire
    assert client.get("/api/tv").get_json()["video"] == []

def test_il_gym_non_cambia_col_cambio_playlist_della_tv(client, monkeypatch):
    """Cambiare la playlist della TV azzera i video della TV, non quelli del GYM:
    la scelta della TV non deve toccare l'allenamento."""
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": FEED_PLAYLIST,
    })
    db = app_module.get_db()
    tv.aggiorna_gym(db, forse=False)
    # la TV cambia playlist: `imposta_playlist` azzera solo la cache 'video'
    nuovo = "PLnuovatv9876543210zyxwv"
    tv.imposta_playlist(db, nuovo)
    assert [v["id"] for v in tv.gym(db)] == ["aaa111", "bbb222"], "il GYM resta"
    assert tv.video(db) == [], "la TV si azzera"

def test_la_sezione_gym_e_in_home_e_ha_il_suo_tab(client):
    """Il GYM e' una sezione a se': scheda in home, scheda nella barra, e il
    contenitore dei video. La scheda in home e' cio' che la rende raggiungibile."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'data-section="gym"' in html
    assert 'id="tab-gym"' in html
    assert 'id="gym-video"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function renderGym" in js
    assert "/api/gym" in js
    assert "gym:      { titolo:" in js or "gym: { titolo:" in js

def test_la_sezione_gym_ha_il_campo_playlist(client):
    """La playlist del GYM si cambia dalla sezione: campo, pulsante e gestore
    presenti, come in TV."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="gym-playlist"' in html
    assert 'id="gym-playlist-salva"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/gym/playlist" in js
    assert "gym-playlist-salva" in js

def test_la_playlist_del_gym_e_della_casa(client, monkeypatch):
    """La playlist del GYM si salva nella casa, come quella della TV: e' una
    preferenza dell'utente, e due case sullo stesso server non devono vedersi i
    video l'una dell'altra."""
    _niente_rete(monkeypatch)
    scelta = "PLgymcasa1234567890abc"
    r = client.put("/api/gym/playlist", json={"playlist": scelta})
    assert r.status_code == 200
    assert r.get_json()["playlist"] == scelta
    assert tv.gym_playlist_id(app_module.get_db()) == scelta
    assert client.get("/api/gym").get_json()["playlist"] == scelta

def test_la_playlist_del_gym_non_tocca_quella_della_tv(client, monkeypatch):
    """Le due scelte vivono su colonne diverse: cambiare l'allenamento non deve
    cambiare i video di casa, ne' viceversa."""
    _niente_rete(monkeypatch)
    db = app_module.get_db()
    tv.imposta_playlist(db, "PLtv1234567890abcdef")
    tv.imposta_playlist_gym(db, "PLgym1234567890abcdef")
    assert tv.playlist_id(db) == "PLtv1234567890abcdef"
    assert tv.gym_playlist_id(db) == "PLgym1234567890abcdef"
    # cambiare solo la TV non tocca il GYM
    tv.imposta_playlist(db, "PLtvnuova9876543210zyx")
    assert tv.gym_playlist_id(db) == "PLgym1234567890abcdef", "il GYM resta"
    # cambiare solo il GYM non tocca la TV
    tv.imposta_playlist_gym(db, "PLgymnuova9876543210zyx")
    assert tv.playlist_id(db) == "PLtvnuova9876543210zyx", "la TV resta"

def test_una_playlist_gym_non_valida_non_si_salva(client, monkeypatch):
    """L'id si valida **prima** di salvarlo: una playlist storta sarebbe una
    sezione vuota che non si capisce da dove venga."""
    _niente_rete(monkeypatch)
    prima = client.get("/api/gym").get_json()["playlist"]
    r = client.put("/api/gym/playlist",
                   json={"playlist": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 400
    assert client.get("/api/gym").get_json()["playlist"] == prima, "la scelta buona resta"

def test_cambiare_playlist_gym_azzera_solo_i_suoi_video(client, monkeypatch):
    """I video del GYM di prima sono di un'altra playlist: si azzerano solo i
    suoi, e quelli della TV restano."""
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": FEED_PLAYLIST,
        _url_playlist(): FEED_PLAYLIST,
    })
    db = app_module.get_db()
    tv.aggiorna_gym(db, forse=False)
    tv.aggiorna_video(db, forse=False)

    # la nuova playlist del GYM risponde con un feed diverso: si deve vedere quello
    nuovo = "PLgymnuova9876543210zyxw"
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={nuovo}":
            FEED_PLAYLIST.replace("aaa111", "ggg777").replace("bbb222", "hhh888"),
    })
    r = client.put("/api/gym/playlist", json={"playlist": nuovo})
    assert r.status_code == 200
    assert [v["id"] for v in r.get_json()["video"]] == ["ggg777", "hhh888"]
    # la TV non c'entra: i suoi video restano quelli di prima
    _niente_rete(monkeypatch)  # il sottofondo non deve scaricare: la copia e' appena scritta
    assert [v["id"] for v in client.get("/api/tv").get_json()["video"]] == ["aaa111", "bbb222"]

def test_il_quiz_legge_le_domande_e_mescola_le_risposte(monkeypatch):
    """Open Trivia DB manda la risposta giusta in un campo a parte: senza
    mescolare sarebbe sempre la prima e il quiz si indovinerebbe senza sapere.
    La risposta giusta resta segnata con `giusta`."""
    finta_tv(monkeypatch, {tv.QUIZ_URL: json.dumps({
        "response_code": 0, "results": [
            {"type": "multiple", "difficulty": "medium", "category": "Science",
             "question": "Quanti sono i pianeti?",
             "correct_answer": "Otto",
             "incorrect_answers": ["Nove", "Sette", "Dieci"]},
        ]})})
    domande = tv.quiz_dal_servizio()
    assert len(domande) == 1
    d = domande[0]
    assert d["testo"] == "Quanti sono i pianeti?"
    assert len(d["risposte"]) == 4
    # esattamente una risposta e' quella giusta, e c'e' sempre
    giuste = [r for r in d["risposte"] if r["giusta"]]
    assert len(giuste) == 1 and giuste[0]["testo"] == "Otto"

def test_il_quiz_senza_domande_e_un_guasto(monkeypatch):
    """`response_code` diverso da zero vuol dire "nessuna domanda" (il servizio
    usa 5 per il vuoto): la copia vecchia resta, non si sovrascrive con il vuoto."""
    finta_tv(monkeypatch, {tv.QUIZ_URL: json.dumps({"response_code": 5, "results": []})})
    with pytest.raises(tv.NonDisponibile):
        tv.quiz_dal_servizio()

def test_le_entita_html_delle_domande_si_leggono(monkeypatch):
    """Open Trivia DB manda `&quot;` e `&#039;`: senza `unescape` la domanda si
    legge con i codici in mezzo."""
    finta_tv(monkeypatch, {tv.QUIZ_URL: json.dumps({
        "response_code": 0, "results": [
            {"question": "Chi ha detto &quot;andiamo&#039;?&quot;",
             "correct_answer": "Lui", "incorrect_answers": ["Lei", "Noi"]},
        ]})})
    domande = tv.quiz_dal_servizio()
    assert domande[0]["testo"] == 'Chi ha detto "andiamo\'?"'

def test_il_quiz_traduce_le_domande_in_italiano(monkeypatch):
    """Open Trivia DB non ha contenuti in italiano: le domande si traducono sul
    server. La traduzione **non rimescola le risposte** — la posizione di quella
    giusta resta dov'e' — e la categoria si traduce insieme alla domanda."""
    _traduzione_che_rispetta_le_righe(monkeypatch)
    d = tv.quiz_dal_servizio()[0]
    assert d["testo"].startswith("IT: ")
    assert d["categoria"].startswith("IT: ")
    assert all(r["testo"].startswith("IT: ") for r in d["risposte"])
    giuste = [r for r in d["risposte"] if r["giusta"]]
    assert len(giuste) == 1 and giuste[0]["testo"] == "IT: Giove"

def test_la_traduzione_che_non_riesce_lascia_l_inglese(monkeypatch):
    """Il servizio di traduzione giu' non e' un guasto della sezione: le domande
    restano in inglese e il quiz funziona lo stesso. La traduzione e' un di piu'."""
    # `finta_tv` non prevede l'indirizzo di traduzione: solleva `NonDisponibile`
    finta_tv(monkeypatch, {tv.QUIZ_URL: _quiz_finto()})
    d = tv.quiz_dal_servizio()[0]
    assert d["testo"] == "Qual e' il pianeta piu' grande?"
    assert [r["testo"] for r in d["risposte"] if r["giusta"]] == ["Giove"]

def test_la_traduzione_non_rimescola_le_risposte_se_le_righe_non_tornano(monkeypatch):
    """Se il servizio accorpa le righe, allineare per posizione rimescolerebbe le
    risposte e la «giusta» finirebbe sulla risposta sbagliata. In quel caso si
    tiene l'inglese: meglio una domanda in inglese che una risposta falsa."""
    def apri(url):
        if url == tv.QUIZ_URL:
            return _quiz_finto().encode("utf-8")
        # una sola riga invece di cinque: la traduzione e' inaffidabile
        return json.dumps({"responseData": {"translatedText": "una riga sola"}}).encode("utf-8")
    monkeypatch.setattr(tv, "_apri", apri)
    d = tv.quiz_dal_servizio()[0]
    assert d["testo"] == "Qual e' il pianeta piu' grande?"
    giuste = [r for r in d["risposte"] if r["giusta"]]
    assert len(giuste) == 1 and giuste[0]["testo"] == "Giove"

def test_la_difficolta_e_in_italiano(monkeypatch):
    """La difficolta' e' una parola sola: si mappa invece di tradurla, cosi' non
    costa una richiesta e non dipende dal servizio."""
    finta_tv(monkeypatch, {tv.QUIZ_URL: json.dumps({"response_code": 0, "results": [
        {"question": "Q?", "correct_answer": "A",
         "incorrect_answers": ["B", "C"], "difficulty": "medium"},
        {"question": "Q2?", "correct_answer": "A",
         "incorrect_answers": ["B", "C"], "difficulty": "hard"},
    ]})})
    domande = tv.quiz_dal_servizio()
    assert domande[0]["difficolta"] == "medio"
    assert domande[1]["difficolta"] == "difficile"

def test_l_endpoint_tv_porta_il_quiz(client, monkeypatch):
    """`/api/tv` serve il quiz dalla cache, come video e notizie. Le barzellette
    sono state tolte: la sezione non le porta piu'."""
    finta_tv(monkeypatch, {
        _url_playlist(): FEED_PLAYLIST,
        tv.FEED_PREDEFINITI[0]: FEED_NOTIZIE,
        tv.QUIZ_URL: json.dumps({
            "response_code": 0, "results": [
                {"question": "Due più due?", "correct_answer": "Quattro",
                 "incorrect_answers": ["Cinque", "Sei", "Tre"], "category": "Math"}]}),
    })
    tv.aggiorna(app_module.get_db(), forse=False)
    _niente_rete(monkeypatch)  # la copia e' fresca: il sottofondo non deve partire
    d = client.get("/api/tv").get_json()
    assert len(d["quiz"]) == 1
    assert d["quiz"][0]["testo"] == "Due più due?"
    assert d["aggiornato"]["quiz"]
    assert "barzellette" not in d

def test_la_cache_del_quiz_non_si_svuota_col_guasto(client, monkeypatch):
    """La rete cade dopo che la copia c'era gia': il quiz resta. E' la regola di
    tutta la sezione: quello che si e' scaricato non si perde."""
    finta_tv(monkeypatch, {tv.QUIZ_URL: json.dumps({"response_code": 0, "results": [
        {"question": "Resta?", "correct_answer": "Si",
         "incorrect_answers": ["No"], "category": "Math"}]})})
    db = app_module.get_db()
    tv.aggiorna_quiz(db, forse=False)
    # ora la rete cade: la copia resta
    _niente_rete(monkeypatch)
    tv.aggiorna_quiz(db, forse=False)
    assert len(tv.quiz(db)) == 1

def test_indovinare_toglie_la_domanda_e_ne_mette_una_nuova(client, monkeypatch):
    """`rispondi` e' quello che fa cambiare domanda a ogni risposta esatta: la
    domanda indovinata esce (non si rivede) e al suo posto ne arriva una nuova,
    cosi' il quiz resta lungo uguale. Si esegue la funzione vera, non si legge
    il codice."""
    db = app_module.get_db()
    _quiz_in_cache(db, ["Prima?", "Seconda?"])
    finta_tv(monkeypatch, {tv._url_quiz(1): _quiz_finto(domanda="Nuova?")})
    esito = tv.rispondi(db, 0)
    assert esito is not None
    testi = [d["testo"] for d in tv.quiz(db)]
    assert "Prima?" not in testi, "la domanda indovinata deve uscire"
    assert "Seconda?" in testi, "le altre restano"
    assert len(testi) == 2, "una esce, una entra: la lunghezza non cambia"
    assert esito["risposta"]["testo"] == "Prima?"

def test_se_la_rete_non_risponde_la_domanda_indovinata_esce_lo_stesso(client, monkeypatch):
    """La domanda nuova e' un di piu': senza rete si toglie quella indovinata e
    basta. Ripetere una domanda a cui si e' appena risposto e' peggio di averne
    una in meno."""
    db = app_module.get_db()
    _quiz_in_cache(db, ["Prima?", "Seconda?"])
    _niente_rete(monkeypatch)
    esito = tv.rispondi(db, 0)
    assert esito is not None
    assert [d["testo"] for d in tv.quiz(db)] == ["Seconda?"]

def test_rispondi_a_un_indice_inesistente_e_un_errore(client):
    """Un indice fuori elenco non deve toccare la copia: e' la difesa contro un
    client che manda la domanda sbagliata."""
    db = app_module.get_db()
    _quiz_in_cache(db, ["Prima?"])
    assert tv.rispondi(db, 5) is None
    assert tv.rispondi(db, "x") is None
    assert len(tv.quiz(db)) == 1

def test_l_endpoint_del_quiz_cambia_domanda_a_ogni_risposta_esatta(client, monkeypatch):
    """`POST /api/quiz/rispondi` e' quello che il client chiama quando si
    indovina: risponde col quiz aggiornato e la domanda indovinata, e richiede
    l'accesso come tutte le altre rotte."""
    db = app_module.get_db()
    _quiz_in_cache(db, ["Prima?", "Seconda?"])
    finta_tv(monkeypatch, {tv._url_quiz(1): _quiz_finto(domanda="Nuova?")})
    r = client.post("/api/quiz/rispondi", json={"indice": 0})
    assert r.status_code == 200
    d = r.get_json()
    assert d["risposta"]["testo"] == "Prima?"
    assert "Prima?" not in [q["testo"] for q in d["quiz"]]
    assert r.get_json()["aggiornato"]["quiz"]
    # indice storto: 400, non un guasto
    assert client.post("/api/quiz/rispondi", json={"indice": 99}).status_code == 400

def test_l_endpoint_del_quiz_richiede_l_accesso(anon):
    assert anon.post("/api/quiz/rispondi", json={"indice": 0}).status_code == 401

def test_il_client_chiama_il_quiz_solo_quando_si_indovina(client):
    """La domanda deve cambiare **solo** indovinando: rispondendo male il quiz
    resta, altrimenti non si capirebbe mai la risposta giusta. Si guarda che il
    client chiami la rotta solo nel ramo `giusta`."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/quiz/rispondi" in js
    assert "disegnaQuiz" in js
    # il ritorno anticipato sul ramo sbagliato e' prima della chiamata
    i_sbagliata = js.index("if (!giusta) return;")
    i_chiamata = js.index("/api/quiz/rispondi")
    assert i_sbagliata < i_chiamata, "rispondendo male non si cambia domanda"

def test_la_sezione_tv_mostra_il_quiz(client):
    """Il riquadro del quiz ha il suo contenitore nella sezione TV, e il client
    lo riempie e risponde al tocco. Le barzellette sono state tolte: i loro nodi
    non devono restare, altrimenti il client scriverebbe su un nodo che non
    esiste (o su uno che non c'e' piu')."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="tv-quiz"' in html
    assert "tv-barzellette" not in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "tv-quiz" in js
    assert "tv-risposta" in js, "il quiz si risponde al tocco"
    assert "tv-barzellette" not in js

def test_il_suggerimento_legge_i_campi_e_traduce_l_attivita(monkeypatch):
    """La Bored API da' l'attivita' in inglese: si traduce (come le domande), e
    i campi strutturati si mostrano. `/filter` risponde con un elenco."""
    def apri(url):
        if url.startswith(tv.BORED_BASE):
            return json.dumps([_suggerimento_finto()]).encode("utf-8")
        if url.startswith(tv.TRADUZIONE_URL):
            testo = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
            return json.dumps({"responseData": {"translatedText": "IT: " + testo}}).encode("utf-8")
        raise tv.NonDisponibile(f"indirizzo di prova non previsto: {url}")
    monkeypatch.setattr(tv, "_apri", apri)
    s = tv.suggerimento_dal_servizio()
    assert s["attivita"] == "IT: Impara a fare il pane"
    assert s["tipo"] == "svago"
    assert s["partecipanti"] == 2
    assert s["bambini"] is True
    assert s["chiave"] == "12345"

def test_la_bored_si_chiede_col_filtro_per_tipo(monkeypatch):
    """Si usa `/filter?type=`, non `/random`: senza il filtro la meta' delle
    risposte sarebbe di un tipo scartato e il riquadro resterebbe vuoto."""
    visti = []

    def apri(url):
        visti.append(url)
        return json.dumps([_suggerimento_finto(tipo="recreational")]).encode("utf-8")
    monkeypatch.setattr(tv, "_apri", apri)
    tv.suggerimento_dal_servizio()
    bored = [u for u in visti if u.startswith(tv.BORED_BASE)]
    assert bored, "la Bored API deve essere chiamata"
    assert all("/filter?type=" in u for u in bored)

def test_un_tipo_non_gradito_non_e_un_suggerimento(monkeypatch):
    """`busywork`/`education` non sono un passatempo da mostrare: si scartano.
    Solo i tipi tenuti diventano un suggerimento."""
    assert tv._suggerimento(_suggerimento_finto(tipo="busywork")) is None
    assert tv._suggerimento(_suggerimento_finto(tipo="education")) is None
    assert tv._suggerimento(_suggerimento_finto(tipo="recreational")) is not None

def test_un_campo_numerico_storto_non_fa_cadere_il_suggerimento():
    """Un campo non numerico non deve sollevare: l'aggiornamento gira anche in
    un filo di sottofondo, dove un'eccezione non la vedrebbe nessuno. Si prende
    il valore di riserva invece di perdere l'attivita'."""
    s = tv._suggerimento({**_suggerimento_finto(), "participants": "due", "price": "gratis"})
    assert s is not None
    assert s["partecipanti"] == 1
    assert s["prezzo"] == 0.0

def test_se_un_tipo_non_risponde_si_passa_al_successivo(monkeypatch):
    """Un tipo che non risponde non deve svuotare il riquadro: si prova il
    successivo, e il primo buono si tiene."""
    def apri(url):
        if "type=music" in url:
            return json.dumps([_suggerimento_finto(tipo="music", attivita="Suona la chitarra")]).encode("utf-8")
        raise tv.NonDisponibile("tipo giu")
    monkeypatch.setattr(tv, "_apri", apri)
    s = tv.suggerimento_dal_servizio()
    assert s["attivita"] == "Suona la chitarra"
    assert s["tipo"] == "musica"

def test_il_suggerimento_senza_rete_non_svuota_la_copia(client, monkeypatch):
    """La rete cade dopo che la copia c'era gia': il suggerimento resta. E' la
    regola di tutta la sezione."""
    db = app_module.get_db()
    monkeypatch.setattr(
        tv, "_apri",
        lambda url: json.dumps([_suggerimento_finto()]).encode("utf-8"))
    tv.aggiorna_suggerimento(db, forse=False)
    _niente_rete(monkeypatch)
    tv.aggiorna_suggerimento(db, forse=False)
    assert tv.suggerimento(db)["attivita"] == "Impara a fare il pane"

def test_l_endpoint_tv_porta_il_suggerimento(client, monkeypatch):
    """`/api/tv` serve il suggerimento dalla cache, come il quiz. E la risposta
    esatta del quiz ne porta uno nuovo, cosi' si rinnova giocando."""
    db = app_module.get_db()
    monkeypatch.setattr(
        tv, "_apri",
        lambda url: json.dumps([_suggerimento_finto()]).encode("utf-8"))
    tv.aggiorna_suggerimento(db, forse=False)
    _niente_rete(monkeypatch)
    d = client.get("/api/tv").get_json()
    assert d["suggerimento"]["attivita"] == "Impara a fare il pane"

def test_la_sezione_tv_mostra_il_suggerimento(client):
    """Il riquadro del suggerimento ha il suo contenitore nel Quiz, e il client
    lo riempie. Sta **sotto** le domande: si legge dopo aver risposto."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="tv-suggerimento"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "disegnaSuggerimento" in js
    assert "tv-suggerimento" in js

def test_le_opere_del_met_si_leggono_con_i_loro_campi(monkeypatch):
    """Titolo, autore, data e foto. La foto arriva dal sito del museo: senza, in
    una striscia di immagini l'opera non si puo' mostrare."""
    _finta_met(monkeypatch, [MET_OPERA])
    arte = tv.arte_dal_servizio()
    assert len(arte) == 1
    o = arte[0]
    assert o["titolo"] == "Wheat Field with Cypresses"
    assert o["autore"] == "Vincent van Gogh"
    assert o["data"] == "1889"
    assert o["foto"] == "https://images.metmuseum.org/esempio.jpg"

def test_un_opera_senza_foto_o_non_pubblica_non_si_mostra(monkeypatch):
    """Si tengono solo le opere di **pubblico dominio** con una foto: un'opera
    ancora coperta da diritto d'autore non si ridistribuisce, e una senza foto
    non si vede. Si scartano in silenzio, non e' un guasto."""
    senza_foto = {**MET_OPERA, "objectID": 1, "primaryImageSmall": ""}
    coperta = {**MET_OPERA, "objectID": 2, "isPublicDomain": False}
    buona = {**MET_OPERA, "objectID": 3, "title": "Quadro buono"}
    _finta_met(monkeypatch, [senza_foto, coperta, buona])
    arte = tv.arte_dal_servizio()
    assert [o["titolo"] for o in arte] == ["Quadro buono"]

def test_se_nessuna_opera_e_mostrabile_e_un_guasto(monkeypatch):
    """Se il museo risponde ma nessuna opera e' mostrabile, la copia vecchia
    deve restare: sollevare `NonDisponibile` e' quello che lo permette."""
    coperta = {**MET_OPERA, "isPublicDomain": False}
    _finta_met(monkeypatch, [coperta])
    with pytest.raises(tv.NonDisponibile):
        tv.arte_dal_servizio()

def test_la_ricerca_del_met_usa_v1_1_e_il_dipartimento(monkeypatch):
    """La ricerca e' passata a **v1.1** (la v1 risponde 410): l'indirizzo vero
    deve usare la versione nuova e il dipartimento dei quadri, altrimenti
    arrivano pitture murali e un manuale a stampa al posto dei dipinti."""
    visti = []

    def apri(url):
        visti.append(url)
        if url.startswith(tv.MET_RICERCA):
            return json.dumps({"objectIDs": [MET_OPERA["objectID"]]}).encode("utf-8")
        return json.dumps(MET_OPERA).encode("utf-8")
    monkeypatch.setattr(tv, "_apri", apri)
    tv.arte_dal_servizio()
    assert visti[0].startswith(tv.MET_RICERCA)
    assert "v1.1/search" in visti[0]
    assert "departmentId=11" in visti[0]
    # il dettaglio resta su v1
    assert "/v1/objects/" in visti[1]

def test_la_copia_delle_opere_non_si_svuota_col_guasto(client, monkeypatch):
    """La rete cade dopo che la copia c'era gia': le opere restano."""
    db = app_module.get_db()
    _finta_met(monkeypatch, [MET_OPERA])
    tv.aggiorna_arte(db, forse=False)
    _niente_rete(monkeypatch)
    tv.aggiorna_arte(db, forse=False)
    assert len(tv.arte(db)) == 1

def test_l_endpoint_tv_porta_le_opere(client, monkeypatch):
    """`/api/tv` serve le opere dalla cache, come video e notizie."""
    db = app_module.get_db()
    _finta_met(monkeypatch, [MET_OPERA])
    tv.aggiorna_arte(db, forse=False)
    _niente_rete(monkeypatch)
    d = client.get("/api/tv").get_json()
    assert len(d["arte"]) == 1
    assert d["arte"][0]["titolo"] == "Wheat Field with Cypresses"
    assert d["aggiornato"]["arte"]

def test_la_sezione_tv_mostra_le_opere(client):
    """Il riquadro delle opere ha il suo contenitore in Intrattenimento, e il
    client lo riempie. Resta nascosto se non c'e' niente, come i riquadri della
    home: un riquadro vuoto e' peggio di un riquadro in meno."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="tv-arte"' in html
    assert 'id="tv-arte-box"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "disegnaArte" in js
    assert "tv-arte" in js

def test_ogni_opera_porta_anche_la_foto_grande(monkeypatch):
    """Per l'ingrandimento serve la foto **originale** (`primaryImage`, qualche
    migliaio di pixel): la misura `web-large` (~600 px) non basta a schermo
    intero. La piccola resta per la striscia, la grande si carica solo al clic."""
    grande = {**MET_OPERA, "primaryImage": "https://images.metmuseum.org/grande.jpg"}
    _finta_met(monkeypatch, [grande])
    o = tv.arte_dal_servizio()[0]
    assert o["foto"] == "https://images.metmuseum.org/esempio.jpg"
    assert o["foto_grande"] == "https://images.metmuseum.org/grande.jpg"

def test_senza_foto_grande_si_usa_quella_piccola(monkeypatch):
    """Se il museo non da' l'originale, l'ingrandimento ripiega sulla piccola:
    meglio un'immagine piu' morbida che una finestra vuota."""
    _finta_met(monkeypatch, [MET_OPERA])
    assert tv.arte_dal_servizio()[0]["foto_grande"] == MET_OPERA["primaryImageSmall"]

def test_altre_opere_saltano_quelle_gia_mostrate(monkeypatch):
    """Il pulsante «Altre opere» deve portare roba **nuova**: si escludono gli id
    gia' mostrati, altrimenti il pulsante ripescherebbe le stesse."""
    tutte = [{**MET_OPERA, "objectID": n, "title": f"Quadro {n}"} for n in range(1, 6)]
    _finta_met(monkeypatch, tutte)
    scelte = tv.arte_dal_servizio(escludi={1, 2})
    assert {o["id"] for o in scelte}.isdisjoint({1, 2})
    assert len(scelte) == 3

def test_se_escludere_svuota_si_ripiega_su_tutte(monkeypatch):
    """Se si sono gia' mostrate tutte le opere, escluderle lascerebbe il vuoto:
    meglio ripetere un'opera che non darne nessuna."""
    _finta_met(monkeypatch, [MET_OPERA])
    scelte = tv.arte_dal_servizio(escludi={MET_OPERA["objectID"]})
    assert len(scelte) == 1

def test_altre_arte_salva_il_gruppo_nuovo_in_copia(client, monkeypatch):
    """Il gruppo nuovo **sostituisce** la copia: ricaricando la pagina si
    rivedono le stesse opere, non quelle di prima."""
    db = app_module.get_db()
    prime = [{**MET_OPERA, "objectID": 1, "title": "Prima"}]
    _finta_met(monkeypatch, prime)
    tv.aggiorna_arte(db, forse=False)
    seconde = [{**MET_OPERA, "objectID": 2, "title": "Seconda"}]
    _finta_met(monkeypatch, seconde)
    tv.altre_arte(db)
    assert [o["titolo"] for o in tv.arte(db)] == ["Seconda"]

def test_l_endpoint_altre_opere_porta_un_gruppo_nuovo(client, monkeypatch):
    """La rotta del pulsante aspetta la rete e risponde con le opere nuove."""
    db = app_module.get_db()
    _finta_met(monkeypatch, [{**MET_OPERA, "objectID": 1, "title": "Prima"}])
    tv.aggiorna_arte(db, forse=False)
    _finta_met(monkeypatch, [{**MET_OPERA, "objectID": 2, "title": "Seconda"}])
    d = client.post("/api/tv/arte/altre").get_json()
    assert d["nuove"] is True
    assert [o["titolo"] for o in d["arte"]] == ["Seconda"]
    assert d["aggiornato"]

def test_se_il_met_non_risponde_l_endpoint_tiene_le_opere(client, monkeypatch):
    """Un giro a vuoto non deve svuotare il riquadro ne' sembrare riuscito:
    resta la copia di prima e lo si dice (`nuove: false`)."""
    db = app_module.get_db()
    _finta_met(monkeypatch, [MET_OPERA])
    tv.aggiorna_arte(db, forse=False)
    _niente_rete(monkeypatch)
    d = client.post("/api/tv/arte/altre").get_json()
    assert d["nuove"] is False
    assert len(d["arte"]) == 1
    assert d["arte"][0]["titolo"] == "Wheat Field with Cypresses"

def test_la_sezione_ha_il_pulsante_e_l_ingrandimento(client):
    """Il pulsante «Altre opere» e la finestra d'ingrandimento stanno nella
    pagina, e il client li collega. L'ingrandimento e' **dentro** l'app: non
    manda l'utente su una scheda nuova, altrimenti perderebbe il posto."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="tv-arte-altre"' in html
    assert 'id="tv-arte-grande"' in html
    assert 'id="tv-arte-img"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "apriOpera" in js
    assert "chiudiOpera" in js
    assert "/api/tv/arte/altre" in js
    # l'immagine della striscia e' cliccabile: senza, non si aprirebbe niente
    assert "data-opera" in js
    assert "cursor: zoom-in" in client.get("/static/style.css").get_data(as_text=True)

def test_migrazione_aggiunge_gym_playlist_a_un_db_esistente():
    """`tv_prefs` esisteva gia' prima del GYM: la colonna `gym_playlist` va
    aggiunta a mano alle case che l'hanno creata senza, altrimenti cambiare la
    playlist del GYM fallirebbe solo li'."""
    path = os.path.join(tempfile.mkdtemp(), "vecchio-tv.db")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
            CREATE TABLE tv_prefs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                playlist TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO tv_prefs (id, playlist) VALUES (1, 'PLsceltavecchia12345ab');
        """)
        app_module.migrate(db)
        cols = {r[1] for r in db.execute("PRAGMA table_info(tv_prefs)")}
        assert "gym_playlist" in cols
        row = db.execute("SELECT playlist, gym_playlist FROM tv_prefs").fetchone()
        # la scelta della TV resta, quella del GYM parte vuota
        assert tuple(row) == ("PLsceltavecchia12345ab", "")
        app_module.migrate(db)  # rieseguire non deve fallire

def test_il_profilo_ha_bucati_e_argomenti_delle_notizie(client):
    """Le due scelte nuove si governano dal Profilo: quanti bucati al giorno e
    quali argomenti delle notizie. I campi esistono, e i gestori li salvano."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="pf-bucati"' in html
    assert 'id="pf-news-topics"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "meta.bucati_opzioni" in js
    assert "meta.news_topics" in js
    assert "$('#pf-bucati').addEventListener" in js
    assert "$('#pf-news-topics').addEventListener" in js

def test_le_notizie_sono_al_massimo_venti_e_mescolate_fra_le_testate(client, monkeypatch):
    """Il tetto e' venti e le fonti si **alternano**, non si ordinano solo per
    data: un elenco per sola data puo' diventare una testata sola, quando una
    pubblica molto piu' spesso delle altre.

    Servono piu' feed: un singolo feed e' limitato a `MAX_PER_FEED` (vedi
    `test_un_feed_generalista_non_occupa_tutto_l_elenco`)."""
    urls = [f"https://esempio.invalid/f{i}" for i in range(3)]
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: urls)
    risposte = {}
    for f, u in enumerate(urls):
        voci = "".join(
            f"<item><title>N{f}-{i}</title><link>https://esempio.invalid/{f}/{i}</link>"
            f"<description>S</description>"
            f"<pubDate>Mon, {i:02d} Jan 2026 08:00:00 +0100</pubDate></item>"
            for i in range(1, 16))
        risposte[u] = f"<rss version='2.0'><channel><title>Prova{f}</title>{voci}</channel></rss>"
    finta_tv(monkeypatch, risposte)
    notizie = tv.notizie_dal_feed()
    assert len(notizie) <= tv.MAX_NOTIZIE
    # le fonti si alternano: due notizie di fila non vengono dalla stessa testata
    fonti = [n["fonte"] for n in notizie]
    assert all(a != b for a, b in zip(fonti, fonti[1:]))
    # e dentro ogni testata l'ordine resta per data
    for fonte in set(fonti):
        date = [n["data"] for n in notizie if n["fonte"] == fonte]
        assert date == sorted(date, reverse=True)

def test_due_testate_si_alternano_e_riempiono_le_venti(client, monkeypatch):
    """Due testate si alternano e riempiono l'elenco: la fetta per testata tiene
    la promessa, dieci e dieci, anche quando una pubblica piu' spesso."""
    u1, u2 = "https://esempio.invalid/ansa", "https://esempio.invalid/rai"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    ansa = [_voce(f"ansa-{i}", f"Thu, 02 Apr 2026 09:{i:02d}:00 +0200") for i in range(15)]
    rai = [_voce(f"rai-{i}", f"Wed, 01 Apr 2026 08:{i:02d}:00 +0200") for i in range(15)]
    finta_tv(monkeypatch, {
        u1: _feed("RSS di Mondo  - ANSA.it", ansa),
        u2: _feed("RaiNews", rai),
    })
    notizie = tv.notizie_dal_feed()
    fonti = [n["fonte"] for n in notizie]
    assert len(notizie) == tv.MAX_NOTIZIE
    assert fonti.count("ANSA.it") == fonti.count("RaiNews") == tv.MAX_NOTIZIE // 2
    assert all(a != b for a, b in zip(fonti, fonti[1:]))

def test_un_feed_generalista_non_occupa_tutto_l_elenco(client, monkeypatch):
    """Un feed generalista senza tetto riempirebbe da solo le dieci notizie,
    facendo sparire le sezioni: ogni feed contribuisce al massimo
    `MAX_PER_FEED`."""
    urls = [f"https://esempio.invalid/f{i}" for i in range(4)]
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: urls)
    risposte = {}
    for f, u in enumerate(urls):
        voci = "".join(
            f"<item><title>N{f}-{i}</title><link>https://esempio.invalid/{f}/{i}</link>"
            f"<description>S</description>"
            f"<pubDate>Mon, {i:02d} Jan 2026 08:00:00 +0100</pubDate></item>"
            for i in range(1, 16))
        risposte[u] = f"<rss version='2.0'><channel><title>Prova{f}</title>{voci}</channel></rss>"
    finta_tv(monkeypatch, risposte)
    notizie = tv.notizie_dal_feed()
    per_fonte = {}
    for n in notizie:
        per_fonte[n["fonte"]] = per_fonte.get(n["fonte"], 0) + 1
    assert all(q <= tv.MAX_PER_FEED for q in per_fonte.values())
    # con quattro fonti e il tetto a quattro, l'elenco e' pieno e misto
    assert len(notizie) == tv.MAX_NOTIZIE
    assert len(per_fonte) == 4

def test_il_nome_della_fonte_e_quello_che_si_mostra_non_il_titolo_del_feed(client, monkeypatch):
    """Il titolo di un feed e' per un lettore di feed: "RSS di Mondo  - ANSA.it".
    Accanto a una notizia ci vuole "ANSA.it"."""
    finta_tv(monkeypatch, {tv.feed_urls()[0]: FEED_NOTIZIE})
    notizie = tv.notizie_dal_feed()
    assert notizie[0]["fonte"] == "ANSA.it"
    assert notizie[0]["titolo"] == "Notizia nuova"

def test_il_sommario_lungo_si_taglia_sulla_parola(client, monkeypatch):
    """Un sommario tagliato a meta' parola si nota subito: si taglia sul confine."""
    lungo = "parola " * 60
    feed = (f"<rss version='2.0'><channel><title>Prova</title><item>"
            f"<title>T</title><link>https://esempio.invalid/a</link>"
            f"<description>{lungo}</description>"
            f"<pubDate>Thu, 02 Apr 2026 09:30:00 +0200</pubDate></item>"
            f"</channel></rss>")
    finta_tv(monkeypatch, {tv.feed_urls()[0]: feed})
    sommario = tv.notizie_dal_feed()[0]["sommario"]
    assert sommario.endswith("…")
    assert len(sommario) <= tv.MAX_SOMMARIO + 1
    assert not sommario[:-1].endswith(" ")

def test_la_cache_tiene_la_copia_vecchia_se_la_rete_non_risponde(client, monkeypatch):
    """E' la proprieta' che tiene in piedi la sezione: se la rete manca, quello
    che si era scaricato **resta**. Svuotarlo sarebbe il danno peggiore, perche'
    e' proprio la copia che serve quando non c'e' connessione."""
    db = app_module.get_db()
    finta_tv(monkeypatch, {tv.feed_urls()[0]: FEED_NOTIZIE})
    assert tv.aggiorna_notizie(db, forse=False) is True
    quante = len(tv.notizie(db))
    assert quante == 2

    # ora la rete non risponde piu': la copia deve restare
    monkeypatch.setattr(tv, "_apri", lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    assert tv.aggiorna_notizie(db, forse=False) is False
    assert len(tv.notizie(db)) == quante

def test_non_si_riscarica_se_la_copia_e_fresca(client, monkeypatch):
    """Una volta al giorno, non a ogni apertura: senza questo, ogni volta che si
    apre la sezione si chiamerebbe un sito altrui."""
    db = app_module.get_db()
    chiamate = {"n": 0}

    def apri(url):
        chiamate["n"] += 1
        return FEED_NOTIZIE.encode("utf-8")
    monkeypatch.setattr(tv, "_apri", apri)

    quanti_feed = len(tv.feed_urls())
    assert tv.aggiorna_notizie(db, forse=True) is True
    assert chiamate["n"] == quanti_feed
    assert tv.aggiorna_notizie(db, forse=True) is False
    assert chiamate["n"] == quanti_feed, "una copia fresca non si riscarica"

def test_l_endpoint_tv_richiede_l_accesso(anon):
    """La sezione TV sta dietro l'accesso come tutto il resto: non e' un dato
    della casa, ma nemmeno una pagina pubblica da lasciare aperta."""
    assert anon.get("/api/tv").status_code == 401
    assert anon.post("/api/tv/aggiorna").status_code == 401
    assert anon.put("/api/tv/playlist", json={"playlist": "x" * 20}).status_code == 401

def test_l_indirizzo_della_playlist_diventa_il_suo_id():
    """Nessuno incolla `PLQKkPe...`: si incolla l'indirizzo della barra del
    browser. Il feed Atom vuole il solo id, quindi va estratto — altrimenti la
    sezione resta vuota senza che si capisca perche'."""
    atteso = "PLQKkPe_OTLJygIqIViE5cqnWjxM1Cou0R"
    assert tv.normalizza_playlist(
        f"https://www.youtube.com/playlist?list={atteso}") == atteso
    # altri parametri nell'indirizzo non devono confondere
    assert tv.normalizza_playlist(
        f"https://www.youtube.com/watch?v=abc&list={atteso}&index=2") == atteso
    # un id gia' nudo si accetta com'e'
    assert tv.normalizza_playlist(atteso) == atteso

def test_un_indirizzo_senza_playlist_non_si_accetta():
    """Un video o un canale non sono una playlist: dirlo subito e' meglio che
    salvare un id sbagliato e mostrare una sezione vuota."""
    for storto in ("https://www.youtube.com/watch?v=abc123",
                   "https://www.youtube.com/@un-canale",
                   "non un id!!"):
        with pytest.raises(ValueError):
            tv.normalizza_playlist(storto)

def test_la_playlist_e_della_casa_non_del_modulo(client, monkeypatch):
    """La playlist scelta si salva nella casa: e' una preferenza dell'utente, e
    due case sullo stesso server non devono vedersi i video l'una dell'altra."""
    _niente_rete(monkeypatch)
    scelta = "PLcasa1234567890abcdef"
    r = client.put("/api/tv/playlist", json={"playlist": scelta})
    assert r.status_code == 200
    assert r.get_json()["playlist"] == scelta
    # il modulo continua a leggere la scelta della casa, non una costante
    assert tv.playlist_id(app_module.get_db()) == scelta
    assert client.get("/api/tv").get_json()["playlist"] == scelta

def test_una_playlist_non_valida_non_si_salva(client, monkeypatch):
    """L'id si valida **prima** di salvarlo: una playlist storta salvata sarebbe
    una sezione vuota che non si capisce da dove venga."""
    _niente_rete(monkeypatch)
    prima = client.get("/api/tv").get_json()["playlist"]
    r = client.put("/api/tv/playlist", json={"playlist": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 400
    assert client.get("/api/tv").get_json()["playlist"] == prima, "la scelta buona resta"

def test_cambiare_playlist_azzera_i_video_vecchi(client, monkeypatch):
    """I video di prima sono di un'altra playlist: tenerli mostrerebbe la scelta
    vecchia fino al prossimo giro, perche' `aggiorna` salta la copia fresca."""
    finta_tv(monkeypatch, {_url_playlist(): FEED_PLAYLIST})
    db = app_module.get_db()
    tv.aggiorna_video(db, forse=False)
    # il sottofondo di `/api/tv` non deve scaricare: la copia e' appena scritta
    _niente_rete(monkeypatch)
    assert len(client.get("/api/tv").get_json()["video"]) == 2

    # la nuova playlist risponde con un feed diverso: si deve vedere quello
    nuovo = "PLnuova9876543210zyxwvu"
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={nuovo}": FEED_PLAYLIST.replace(
            "aaa111", "ccc333").replace("bbb222", "ddd444"),
    })
    r = client.put("/api/tv/playlist", json={"playlist": nuovo})
    assert r.status_code == 200
    assert [v["id"] for v in r.get_json()["video"]] == ["ccc333", "ddd444"]

def test_la_casa_nuova_puo_nascere_con_una_playlist(anon, monkeypatch):
    """La richiesta nasce qui: alla creazione si chiede quale playlist si
    gradisce, cosi' la TV e' giusta fin dal primo avvio."""
    _niente_rete(monkeypatch)
    scelta = "PLscelta1234567890abcde"
    r = anon.post("/api/houses", json={
        "nome": "Casa Playlist", "password": "aaaa", "playlist": scelta})
    assert r.status_code == 201
    assert r.get_json()["playlist"] == scelta
    assert anon.get("/api/tv").get_json()["playlist"] == scelta

def test_una_playlist_non_valida_non_crea_la_casa(anon):
    """Si valida **prima** di registrare la casa: crearla e poi scoprire che la
    playlist non va bene la lascerebbe a meta'."""
    r = anon.post("/api/houses", json={
        "nome": "Casa Storta", "password": "aaaa",
        "playlist": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 400
    assert "Casa Storta" not in [c["nome"] for c in anon.get("/api/houses").get_json()]

def test_senza_playlist_la_casa_usa_la_predefinita(anon, monkeypatch):
    """Chi non sceglie non resta senza TV: la playlist predefinita vale per lui."""
    _niente_rete(monkeypatch)
    anon.post("/api/houses", json={"nome": "Casa Senza Scelta", "password": "aaaa"})
    assert anon.get("/api/tv").get_json()["playlist"] == tv.playlist_id()

def test_la_playlist_si_scegle_alla_creazione_e_si_cambia_dalla_tv(client):
    """La playlist si chiede creando la casa (la richiesta nasce li'), ma si deve
    anche poter cambiare dopo senza rifare la casa: un canale preferito cambia."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="new-playlist"' in html
    assert 'id="tv-playlist"' in html and 'id="tv-playlist-salva"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/tv/playlist" in js
    assert "$('#new-playlist').value" in js

def test_l_endpoint_tv_serve_la_cache_e_gli_incorpora(client, monkeypatch):
    """L'endpoint non aspetta la rete: serve quello che c'e' e basta. Ogni video
    porta anche l'indirizzo del player, e il player e' `youtube-nocookie`, cosi'
    la pagina della casa non consegna i cookie a YouTube per il solo fatto di
    mostrare un video."""
    finta_tv(monkeypatch, {_url_playlist(): FEED_PLAYLIST, tv.feed_urls()[0]: FEED_NOTIZIE})
    db = app_module.get_db()
    tv.aggiorna(db, forse=False)
    # il quiz non e' in cache: senza spegnere il filo di sottofondo questo test
    # lo lascerebbe partire, e sopravvivendo alla richiesta toccherebbe il
    # database di prova mentre la fixture lo cancella
    _niente_rete(monkeypatch)

    d = client.get("/api/tv").get_json()
    assert len(d["video"]) == 2
    assert d["video"][0]["embed"] == "https://www.youtube-nocookie.com/embed/aaa111"
    assert len(d["notizie"]) == 2
    assert d["aggiornato"]["notizie"]

def test_l_endpoint_tv_non_cade_se_non_c_e_niente(client, monkeypatch):
    """Cache vuota e rete assente: 200 con due elenchi vuoti. E' una sezione da
    riempire, non un guasto da mostrare a chi apre l'app."""
    # `_niente_rete` spegne anche il filo di sottofondo: senza, sopravvive al
    # test e tiene aperto il database di prova, che la fixture cancella sotto
    # il test successivo («disk I/O error» a intermittenza).
    _niente_rete(monkeypatch)
    r = client.get("/api/tv")
    assert r.status_code == 200
    d = r.get_json()
    assert d["video"] == [] and d["notizie"] == []

def test_le_notizie_vengono_da_piu_sezioni_e_si_unisono(client, monkeypatch):
    """Le notizie arrivano da piu' sezioni ANSA (mondo, cronaca, politica,
    economia): con una sola il mondo lascia fuori quello che succede in Italia.
    L'elenco unico si riordina per data, non per sezione."""
    u1, u2 = "https://esempio.invalid/mondo", "https://esempio.invalid/cronaca"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    finta_tv(monkeypatch, {
        u1: _feed("RSS di Mondo  - ANSA.it",
                  [_voce("mondo-vecchia", "Mon, 01 Jan 2026 08:00:00 +0100")]),
        u2: _feed("RSS di Cronaca  - ANSA.it",
                  [_voce("italia-nuova", "Thu, 02 Apr 2026 09:00:00 +0200")]),
    })
    notizie = tv.notizie_dal_feed()
    assert [n["titolo"] for n in notizie] == ["italia-nuova", "mondo-vecchia"]
    # la fonte resta quella della sezione di provenienza
    assert notizie[0]["fonte"] == "ANSA.it"

def test_se_nessun_feed_risponde_e_un_guasto(client, monkeypatch):
    """Nessuna sezione risponde: e' `NonDisponibile`, non una lista vuota, cosi'
    la cache buona di ieri non viene sovrascritta con il vuoto."""
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: ["https://esempio.invalid/a",
                                                  "https://esempio.invalid/b"])
    finta_tv(monkeypatch, {})
    with pytest.raises(tv.NonDisponibile):
        tv.notizie_dal_feed()

def test_la_stessa_notizia_non_compare_due_volte(client, monkeypatch):
    """Lo stesso fatto compare in piu' sezioni con titoli diversi: il link e' la
    chiave stabile, e il doppione occuperebbe il posto di un'altra notizia."""
    u1, u2 = "https://esempio.invalid/a", "https://esempio.invalid/b"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    voce = ("<item><title>Stesso fatto</title>"
            "<link>https://esempio.invalid/uguale</link>"
            "<description>S</description>"
            "<pubDate>Thu, 02 Apr 2026 09:00:00 +0200</pubDate></item>")
    finta_tv(monkeypatch, {
        u1: _feed("RSS di Mondo  - ANSA.it", [voce]),
        u2: _feed("RSS di Cronaca  - ANSA.it", [voce]),
    })
    notizie = tv.notizie_dal_feed()
    assert len(notizie) == 1

def test_i_feed_predefiniti_includono_l_italia(client):
    """Le sezioni predefinite non sono il solo «mondo»: dentro c'e' quello che
    succede in Italia, che e' la prima cosa che si guarda."""
    urls = tv.feed_urls()
    assert len(urls) >= 2
    assert any("mondo" in u for u in urls)
    assert any("cronaca" in u or "politica" in u for u in urls)
    # niente doppioni e tutti feed veri
    assert len(urls) == len(set(urls))
    assert all(u.startswith("https://") for u in urls)

def test_i_feed_predefiniti_non_includono_rainews(client):
    """RaiNews e' stato tolto dalle testate: le notizie sono solo ANSA.

    La scelta e' deliberata: il feed generalista di RaiNews pubblicava decine di
    voci e non si voleva piu' in elenco."""
    urls = tv.feed_urls()
    assert all("rainews" not in u.lower() for u in urls)
    assert all("ansa.it" in u for u in urls)

def test_gli_argomenti_scelti_riducono_i_feed(client):
    """Gli argomenti del profilo restringono i feed: chi legge solo economia non
    deve vedersi le notizie di mondo in elenco."""
    # nessuna scelta: tutti i feed predefiniti (nessun database = nessun profilo)
    assert tv.feed_urls() == list(tv.FEED_PREDEFINITI)
    client.put("/api/profile", json={"news_topics": ["economia", "politica"]})
    with closing(sqlite3.connect(houses.db_path(CASA_TEST))) as db:
        db.row_factory = sqlite3.Row
        urls = tv.feed_urls(db)
    assert urls == [tv.FEED_PER_TEMA["economia"], tv.FEED_PER_TEMA["politica"]]
    # e l'ordine e' quello dichiarato, non quello dei predefiniti
    assert urls[0].endswith("economia_rss.xml")

def test_argomenti_sconosciuti_non_svuotano_le_notizie():
    """Un refuso non deve lasciare la sezione senza notizie: si tengono solo le
    chiavi note, e se non ne resta nessuna valida si torna a "tutti"."""
    assert tv.argomenti_scelti("economia, sport, calcio") == ["economia"]
    assert tv.argomenti_scelti("") == []
    assert tv.argomenti_scelti(["mondo", "mondo", "cronaca"]) == ["mondo", "cronaca"]
    assert tv.argomenti_scelti("sport, meteo") == []

def test_cambiare_argomenti_azzera_la_copia_vecchia(client):
    """La copia delle notizie e' di altri argomenti: tenerla mostrerebbe la
    scelta precedente fino al giro dopo."""
    percorso = houses.db_path(CASA_TEST)
    with closing(sqlite3.connect(percorso)) as db:
        db.execute("INSERT INTO tv_cache (chiave, dati, aggiornato) "
                   "VALUES ('notizie', '[]', datetime('now'))")
        db.commit()
    client.put("/api/profile", json={"news_topics": ["economia"]})
    with closing(sqlite3.connect(percorso)) as db:
        righe = db.execute("SELECT chiave FROM tv_cache WHERE chiave = 'notizie'").fetchall()
    assert not righe, "la copia delle notizie va azzerata"

def test_la_meta_porta_gli_argomenti_delle_notizie(client):
    """Onboarding e Profilo costruiscono le scelte dalla meta, non a mano."""
    meta = client.get("/api/meta").get_json()
    chiavi = {a["key"] for a in meta["news_topics"]}
    assert chiavi == set(tv.FEED_PER_TEMA)
    assert all("label" in a for a in meta["news_topics"])

def test_gli_argomenti_si_salvano_come_testo_o_lista(client):
    """L'API accetta entrambe le forme, e normalizza in testo separato da virgole:
    e' la forma che `tv.argomenti_scelti` legge."""
    p = client.put("/api/profile", json={"news_topics": ["economia", "politica"]}).get_json()
    assert p["news_topics"] == "economia, politica"
    p = client.put("/api/profile", json={"news_topics": "economia; politica"}).get_json()
    assert p["news_topics"] == "economia, politica"
    p = client.put("/api/profile", json={"news_topics": []}).get_json()
    assert p["news_topics"] == ""

def test_tv_feed_dall_ambiente_ne_accetta_piu_d_uno(client, monkeypatch):
    """`TV_FEED` puo' indicare piu' indirizzi, separati da virgola o a capo:
    cosi' una casa puo' scegliere le proprie sezioni senza toccare il modulo."""
    monkeypatch.setenv("TV_FEED", "https://a.invalid/rss, https://b.invalid/rss\n"
                                  "https://c.invalid/rss")
    assert tv.feed_urls() == ["https://a.invalid/rss", "https://b.invalid/rss",
                              "https://c.invalid/rss"]
    # e il tetto vale anche qui: non si moltiplicano le richieste a un sito altrui
    monkeypatch.setenv("TV_FEED", ",".join(f"https://x{i}.invalid/rss" for i in range(50)))
    assert len(tv.feed_urls()) == tv.MAX_FEED

def test_l_aggiornamento_manuale_lo_dice_se_non_ha_portato_niente(client, monkeypatch):
    """Il pulsante «Aggiorna» aspetta la rete e riporta l'esito: un aggiornamento
    che non ha portato niente di nuovo non deve sembrare riuscito."""
    monkeypatch.setattr(tv, "_apri", lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    d = client.post("/api/tv/aggiorna").get_json()
    assert d["aggiornati"] == {"video": False, "notizie": False, "gym": False,
                               "quiz": False, "suggerimento": False, "arte": False}

def test_il_database_vecchio_riceve_la_tabella_della_cache(client):
    """`tv_cache` e' una tabella nuova: `CREATE TABLE IF NOT EXISTS` la crea su
    ogni casa, vecchia o nuova. Se non arrivasse, la sezione TV fallirebbe solo
    sulle case con piu' dati — il posto peggiore."""
    db = app_module.get_db()
    tabelle = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "tv_cache" in tabelle
