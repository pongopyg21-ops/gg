"""Impegni e promemoria del calendario.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_la_griglia_del_mese_comincia_di_lunedi_e_finisce_di_domenica():
    """Le settimane devono essere intere: una riga che comincia a meta' confonde
    piu' di quanto aiuti. Febbraio 2026 comincia di domenica, quindi la prima
    settimana ha sei giorni di gennaio davanti."""
    g = calendario.mese_di(2026, 2)
    assert g["celle"][0]["iso"] == "2026-01-26"       # lunedi'
    assert g["celle"][0]["nel_mese"] is False
    assert g["celle"][0]["weekend"] is False
    assert g["celle"][5]["iso"] == "2026-01-31"
    assert g["celle"][6]["iso"] == "2026-02-01"       # domenica: prima del mese
    assert len(g["celle"]) % 7 == 0
    assert g["primo"] == "2026-02-01" and g["ultimo"] == "2026-02-28"

def test_il_weekend_e_il_sabato_e_la_domenica():
    g = calendario.mese_di(2026, 3)
    for c in g["celle"]:
        atteso = calendario._data(c["iso"]).weekday() >= 5
        assert c["weekend"] is atteso

def test_i_giorni_di_distanza_seguono_il_segno_delle_pulizie():
    """Stessa convenzione di `igiene.scadenza`: negativo se e' passato, 0 oggi,
    positivo se deve venire. Chi legge i due moduli non deve ricordare due
    regole diverse."""
    s = calendario.stato_impegno("2026-09-10", oggi="2026-09-12", promemoria=0)
    assert s["giorni"] == -2 and s["passato"] and s["in_ritardo"]
    s = calendario.stato_impegno("2026-09-12", oggi="2026-09-12", promemoria=0)
    assert s["giorni"] == 0 and s["oggi"] and not s["passato"]
    s = calendario.stato_impegno("2026-09-15", oggi="2026-09-12", promemoria=0)
    assert s["giorni"] == 3 and not s["passato"]

def test_il_promemoria_scatta_da_n_giorni_prima_fino_al_giorno_stesso():
    """Il promemoria non e' "il giorno prima": e' quanti giorni prima, e resta
    acceso fino al giorno dell'impegno compreso."""
    assert calendario.stato_impegno("2026-09-15", oggi="2026-09-12", promemoria=3)["avvisa"] is True
    assert calendario.stato_impegno("2026-09-15", oggi="2026-09-12", promemoria=2)["avvisa"] is False
    assert calendario.stato_impegno("2026-09-15", oggi="2026-09-15", promemoria=1)["avvisa"] is True

def test_una_cosa_passata_non_avvisa_piu_ma_resta_in_ritardo():
    """Un promemoria per una cosa gia' successa non e' un promemoria; ma una
    cosa passata e non chiusa deve restare visibile, altrimenti sparisce in
    silenzio, che e' il modo peggiore di fallire un promemoria."""
    s = calendario.stato_impegno("2026-09-01", oggi="2026-09-10", promemoria=30)
    assert s["avvisa"] is False
    assert s["in_ritardo"] is True

def test_zero_giorni_prima_e_il_giorno_stesso_non_un_nessun_promemoria():
    s = calendario.stato_impegno("2026-09-15", oggi="2026-09-15", promemoria=0)
    assert s["avvisa"] is True

def test_un_impegno_senza_data_non_cade():
    """`when_date` e' obbligatoria, ma una riga scritta a mano nel database puo'
    non averla: la scheda deve mostrare "senza data" invece di sollevare."""
    s = calendario.stato_impegno("", oggi="2026-09-12")
    assert s["giorni"] is None and s["avvisa"] is False
    assert calendario.quando_detto(s) == "senza data"

def test_le_frasi_di_quando_sono_brevi_e_italiane():
    oggi = "2026-09-12"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-12", oggi)) == "oggi"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-13", oggi)) == "domani"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-11", oggi)) == "ieri"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-15", oggi)) == "fra 3 giorni"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-09", oggi)) == "3 giorni fa"

def test_una_categoria_sconosciuta_ricade_sulla_predefinita():
    """Un'etichetta sbagliata non deve far perdere un appuntamento: si ricade
    invece di rifiutare, come per le FAQ."""
    assert calendario.categoria_valida("Lavoro") == "lavoro"
    assert calendario.categoria_valida("inventata") == calendario.CATEGORIA_DEFAULT
    assert calendario.categoria_valida("") == calendario.CATEGORIA_DEFAULT

def test_ogni_categoria_ha_un_colore_che_e_una_variabile_css():
    """Il colore e' un nome di variabile CSS, non un esadecimale: cosi' il tema
    scuro la schiarisce da sola. Una categoria senza colore lascerebbe il
    puntino invisibile."""
    for c in calendario.CATEGORIE:
        assert c["colore"].startswith("--")
    assert set(calendario.meta()["category_colors"]) == {c["key"] for c in calendario.CATEGORIE}

def test_i_dodici_mesi_sono_in_italiano():
    assert calendario.mesi()[0] == "Gennaio"
    assert calendario.mesi()[11] == "Dicembre"
    assert len(calendario.mesi()) == 12

def test_un_promemoria_fuori_scala_viene_riportato_nei_limiti():
    assert calendario.promemoria_giorni(-5) == 0
    assert calendario.promemoria_giorni(9999) == calendario.PROMEMORIA_MAX
    assert calendario.promemoria_giorni("non un numero") == 0

def test_un_ora_scritta_male_non_fa_perdere_l_impegno():
    """L'ora e' facoltativa e l'impegno e' la parte che conta: un'ora storta si
    scarta, non fa rifiutare tutto."""
    assert calendario._ora("09:30") == "09:30"
    assert calendario._ora("09:30:00") == "09:30"
    assert calendario._ora("") == ""
    assert calendario._ora("venticinque") == ""

def test_impegno_si_crea_con_tutti_i_campi(client):
    r = client.post("/api/appointments", json={
        "title": "Dentista", "when_date": "2026-09-20", "time": "09:30",
        "category": "salute", "notes": "Portare la tessera", "reminder_days": 3,
    })
    assert r.status_code == 201
    a = r.get_json()
    assert a["title"] == "Dentista"
    assert a["category"] == "salute"
    assert a["category_label"] == "Salute"
    assert a["time"] == "09:30"
    assert a["reminder_days"] == 3
    assert a["done"] is False
    assert a["stato"]["giorni"] is not None

def test_impegno_senza_titolo_o_senza_data_rifiutato(client):
    assert client.post("/api/appointments", json={"when_date": "2026-09-20"}).status_code == 400
    assert client.post("/api/appointments", json={"title": "X"}).status_code == 400
    assert client.post("/api/appointments", json={"title": "X", "when_date": "non-data"}).status_code == 400

def test_impegno_si_conclude_e_si_riapre(client):
    aid = client.post("/api/appointments", json={
        "title": "X", "when_date": "2026-09-20"}).get_json()["id"]
    assert client.put(f"/api/appointments/{aid}", json={"done": True}).get_json()["done"] is True
    assert client.put(f"/api/appointments/{aid}", json={"done": False}).get_json()["done"] is False

def test_spuntare_un_impegno_non_cancella_il_resto(client):
    """`done` si tocca da solo, come per i progetti: spuntare una casella non
    deve richiedere di rimandare titolo, data e promemoria."""
    aid = client.post("/api/appointments", json={
        "title": "Dentista", "when_date": "2026-09-20", "time": "09:30",
        "category": "salute", "notes": "tessera", "reminder_days": 3,
    }).get_json()["id"]
    a = client.put(f"/api/appointments/{aid}", json={"done": True}).get_json()
    assert a["title"] == "Dentista" and a["time"] == "09:30"
    assert a["category"] == "salute" and a["notes"] == "tessera"
    assert a["reminder_days"] == 3

def test_un_impegno_si_puo_spostare_e_il_promemoria_lo_segue(client):
    """Il promemoria e' quanti giorni prima, non una data: spostando l'impegno
    si sposta anche il promemoria, invece di lasciarlo indietro."""
    aid = client.post("/api/appointments", json={
        "title": "X", "when_date": "2026-09-20", "reminder_days": 2}).get_json()["id"]
    a = client.put(f"/api/appointments/{aid}", json={"when_date": "2026-10-01"}).get_json()
    assert a["when_date"] == "2026-10-01"
    assert a["reminder_days"] == 2

def test_impegno_eliminato(client):
    aid = client.post("/api/appointments", json={
        "title": "X", "when_date": "2026-09-20"}).get_json()["id"]
    assert client.delete(f"/api/appointments/{aid}").status_code == 200
    assert client.get("/api/appointments?giorno=2026-09-20").get_json()["appointments"] == []

def test_impegno_inesistente_da_404(client):
    assert client.put("/api/appointments/99999", json={"done": True}).status_code == 404
    assert client.delete("/api/appointments/99999").status_code == 404

def test_il_mese_si_chiede_con_la_sua_data(client):
    client.post("/api/appointments", json={"title": "Dentro", "when_date": "2026-09-20"})
    client.post("/api/appointments", json={"title": "Fuori", "when_date": "2026-10-20"})
    d = client.get("/api/appointments?mese=2026-09").get_json()
    assert [a["title"] for a in d["appointments"]] == ["Dentro"]
    assert d["mese"]["anno"] == 2026 and d["mese"]["mese"] == 9
    assert len(d["mese"]["celle"]) % 7 == 0

def test_senza_mese_si_serve_quello_corrente(client):
    d = client.get("/api/appointments").get_json()
    oggi = date.today()
    assert d["mese"]["anno"] == oggi.year and d["mese"]["mese"] == oggi.month

def test_gli_impegni_di_un_giorno_si_leggono_insieme(client):
    client.post("/api/appointments", json={"title": "Uno", "when_date": "2026-09-20", "time": "09:00"})
    client.post("/api/appointments", json={"title": "Due", "when_date": "2026-09-20", "time": "15:00"})
    d = client.get("/api/appointments?giorno=2026-09-20").get_json()
    assert [a["title"] for a in d["appointments"]] == ["Uno", "Due"]

def test_gli_avvisi_sono_i_promemoria_scattati_non_tutti_i_prossimi(client):
    """Un promemoria per una cosa fra sei mesi non e' un promemoria: gli avvisi
    sono solo quelli scattati o in ritardo."""
    oggi = date.today()
    vicino = (oggi + timedelta(days=2)).isoformat()
    lontano = (oggi + timedelta(days=120)).isoformat()
    client.post("/api/appointments", json={"title": "Vicino", "when_date": vicino, "reminder_days": 3})
    client.post("/api/appointments", json={"title": "Lontano", "when_date": lontano, "reminder_days": 0})
    d = client.get("/api/appointments").get_json()
    titoli = [a["title"] for a in d["prossimi"]]
    assert "Vicino" in titoli and "Lontano" not in titoli

def test_un_impegno_in_ritardo_resta_negli_avvisi_finche_non_si_chiude(client):
    ieri = (date.today() - timedelta(days=3)).isoformat()
    aid = client.post("/api/appointments", json={
        "title": "Mancato", "when_date": ieri}).get_json()["id"]
    titoli = [a["title"] for a in client.get("/api/appointments").get_json()["prossimi"]]
    assert "Mancato" in titoli
    client.put(f"/api/appointments/{aid}", json={"done": True})
    titoli = [a["title"] for a in client.get("/api/appointments").get_json()["prossimi"]]
    assert "Mancato" not in titoli

def test_il_calendario_richiede_l_accesso(anon):
    assert anon.get("/api/appointments").status_code == 401
    assert anon.post("/api/appointments", json={"title": "X", "when_date": "2026-09-20"}).status_code == 401

def test_il_calendario_meta_ha_categorie_promemoria_e_mesi(client):
    m = client.get("/api/calendario/meta").get_json()
    assert "salute" in m["categories"] and m["category_labels"]["salute"] == "Salute"
    assert m["category_colors"]["salute"].startswith("--")
    assert m["reminders"][0]["giorni"] == 0
    assert len(m["months"]) == 12

def test_il_calendario_ha_il_pulsante_dei_promemoria(client):
    """Il permesso per le notifiche si chiede da un tocco, quindi ci vuole un
    pulsante. Se non c'e', i promemoria restano solo dentro l'app — che e' il
    difetto che questa funzione esiste per togliere."""
    html = client.get("/").get_data(as_text=True)
    assert 'id="cal-notifiche"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    for nome in ("controllaPromemoria", "avviaPromemoria", "mostraPulsanteNotifiche"):
        assert f"function {nome}" in js, f"manca {nome}"

def test_i_promemoria_avvisano_una_volta_sola_al_giorno():
    """`controllaPromemoria` eseguita davvero con node: con un permesso concesso
    e un impegno che avvisa, parte **una** notifica; richiamata subito dopo, non
    ne parte una seconda (la memoria di oggi sta in `localStorage`). Senza la
    memoria, il controllo periodico ripeterebbe lo stesso avviso ogni mezz'ora."""
    js = open(os.path.join(BASE_APP, "static", "app.js"), encoding="utf-8").read()
    corpo = (_estrai_funzione_js(js, "notificheAttive")
             + _estrai_funzione_js(js, "avvisiGia_")
             + _estrai_funzione_js(js, "segnaAvvisato")
             + _estrai_funzione_js(js, "controllaPromemoria"))
    prova = """
const store = {};
const localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = v; },
};
const inviate = [];
class Notification { constructor(t, o) { inviate.push([t, o.body]); } }
Notification.permission = 'granted';
function iso() { return '2026-10-05'; }
const api = async () => ({ prossimi: [
  { id: 7, title: 'Dentista', when_date: '2026-10-05', time: '09:00', quando_detto: 'oggi' }] });
""" + corpo + """
(async () => {
  await controllaPromemoria();
  await controllaPromemoria();   // seconda volta: non deve ripetere
  console.log(JSON.stringify({ inviate, chiavi: JSON.parse(store.promemoriaAvvisati).chiavi }));
})();
"""
    d = _esegui_node(prova)
    assert len(d["inviate"]) == 1, d
    assert d["inviate"][0][0] == "📆 Dentista"
    assert d["chiavi"] == ["7|2026-10-05"], d

def test_senza_permesso_non_parte_nessuna_notifica():
    """Se il permesso non c'e' (o e' stato negato), il controllo non fa nulla:
    chiedere il permesso senza un gesto lo farebbe bloccare dal browser, e una
    notifica negata non si recupera. Il pulsante e' l'unico modo per concederlo."""
    js = open(os.path.join(BASE_APP, "static", "app.js"), encoding="utf-8").read()
    corpo = (_estrai_funzione_js(js, "notificheAttive")
             + _estrai_funzione_js(js, "controllaPromemoria"))
    prova = """
const inviate = [];
class Notification { constructor() { inviate.push(1); } }
Notification.permission = 'default';
const localStorage = { getItem: () => null, setItem: () => {} };
function iso() { return '2026-10-05'; }
let chiamateApi = 0;
const api = async () => { chiamateApi++; return { prossimi: [{ id: 1, title: 'X', when_date: '2026-10-05' }] }; };
""" + corpo + """
(async () => {
  await controllaPromemoria();
  console.log(JSON.stringify({ inviate, chiamateApi }));
})();
"""
    d = _esegui_node(prova)
    assert d["inviate"] == [], d
    assert d["chiamateApi"] == 0, "senza permesso non si chiama nemmeno il server"

def test_il_database_vecchio_riceve_la_tabella_del_calendario(client):
    """`appointments` e' una tabella nuova: `CREATE TABLE IF NOT EXISTS` la crea
    su ogni casa, vecchia o nuova. Se non arrivasse, il calendario fallirebbe
    solo sulle case con piu' dati — il posto peggiore."""
    db = app_module.get_db()
    tabelle = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "appointments" in tabelle

def test_la_griglia_del_calendario_ha_i_puntini_delle_categorie():
    """Ogni cella con un impegno porta un puntino del colore della categoria:
    e' quello che fa leggere il mese a colpo d'occhio."""
    js = open(os.path.join(BASE_APP, "static", "app.js"), encoding="utf-8").read()
    assert "cal-dot" in js and "category_colors" in js
    assert "cal-celle" in js

def test_ogni_colore_di_categoria_e_definito_in_entrambi_i_temi():
    """Il modulo nomina le variabili CSS, ma sono il foglio di stile a
    definirle. Un colore che esiste solo nel tema chiaro lascerebbe il puntino
    invisibile di notte — e il difetto non si vedrebbe di giorno."""
    css = open(os.path.join(BASE_APP, "static", "style.css"), encoding="utf-8").read()
    chiaro = css.split('html[data-tema="scuro"]')[0]
    scuro = css.split('html[data-tema="scuro"]', 1)[1]
    for c in calendario.CATEGORIE:
        assert f"{c['colore']}:" in chiaro, f"{c['colore']} manca nel tema chiaro"
        assert f"{c['colore']}:" in scuro, f"{c['colore']} manca nel tema scuro"
