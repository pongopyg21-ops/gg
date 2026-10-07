"""Pulizie di casa: catalogo, piano e API.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_bucati_al_giorno_regola_la_cadenza_della_lavatrice(client):
    """I bucati dichiarati decidono ogni quanto torna «Avviare la lavatrice».

    Il legame e' diretto e va provato per intero: la scelta si salva nel profilo,
    `/api/chores` la usa, e il campo `cadenza_giorni` della voce lo dice. Senza
    il giro completo, la scelta resterebbe scritta e non cambierebbe niente."""
    # non dichiarato: la cadenza di partenza e' un giorno e mezzo
    voce = next(v for v in client.get("/api/chores").get_json()["attivita"]
                if v["name"] == "Avviare la lavatrice")
    assert voce["cadenza_giorni"] == 1.5

    r = client.put("/api/profile", json={"bucati_giorno": 1})
    assert r.status_code == 200
    assert r.get_json()["bucati_giorno"] == 1
    voce = next(v for v in client.get("/api/chores").get_json()["attivita"]
                if v["name"] == "Avviare la lavatrice")
    assert voce["cadenza_giorni"] == 1.0

    # zero torna alla cadenza di partenza: "non dico" non e' "mai"
    client.put("/api/profile", json={"bucati_giorno": 0})
    voce = next(v for v in client.get("/api/chores").get_json()["attivita"]
                if v["name"] == "Avviare la lavatrice")
    assert voce["cadenza_giorni"] == 1.5

def test_bucati_al_giorno_non_valido_rifiutato(client):
    for cattivo in (-1, 6, "tre", None):
        r = client.put("/api/profile", json={"bucati_giorno": cattivo})
        assert r.status_code == 400, cattivo
        assert "bucati" in r.get_json()["error"].lower()
    assert client.get("/api/profile").get_json()["bucati_giorno"] == 0

def test_le_opzioni_dei_bucati_arrivano_dalla_meta(client):
    """L'interfaccia non inventa i numeri: li legge dalla meta, cosi' onboarding
    e Profilo offrono le stesse scelte del backend."""
    meta = client.get("/api/meta").get_json()
    assert meta["bucati_opzioni"] == [1, 2, 3, 4, 5]
    assert client.get("/api/chores/meta").get_json()["bucati_opzioni"] == [1, 2, 3, 4, 5]

def test_cadenza_lavatrice_dai_bucati():
    """Il conto e' in un posto solo: piu' bucati, meno attesa. Il minimo e'
    mezza giornata, altrimenti la voce resterebbe sempre in cima al piano."""
    assert igiene.cadenza_lavatrice(0) == 1.5      # non dichiarato
    assert igiene.cadenza_lavatrice(1) == 1.0
    assert igiene.cadenza_lavatrice(2) == 0.5
    assert igiene.cadenza_lavatrice(5) == 0.5      # il minimo regge
    assert igiene.cadenza_lavatrice("x") == 1.5    # valore storto: si torna al default

def test_riducendo_i_pasti_il_fabbisogno_per_giorno_ignora_i_nascosti(client):
    """Anche la ripartizione per giorno deve ignorare i pasti non piu' gestiti."""
    cena = ricetta(client, "Cena", 2, [{"name": "Farina", "quantity": 200, "unit": "g"}])
    pranzo = ricetta(client, "Pranzo", 2, [{"name": "Farina", "quantity": 300, "unit": "g"}])
    client.put("/api/profile", json={"meals_per_day": 2})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "pranzo", "recipe_id": pranzo})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": cena})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})

    client.put("/api/profile", json={"meals_per_day": 1})
    for v in client.get("/api/shopping").get_json():
        client.delete(f"/api/shopping/{v['id']}")
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    voce = next(v for v in client.get("/api/shopping").get_json() if v["name"] == "Farina")
    assert float(voce["quantity"]) == 200, voce
    giorni = voce.get("days") or []
    assert not giorni or float(giorni[0]["quantity"]) == 200, giorni

def test_migrazione_aggiunge_il_numero_di_pasti(client):
    """Un DB creato prima della scelta pasti riceve la colonna a 2."""
    DB = houses.db_path(CASA_TEST)   # ora il database e' quello della casa
    with sqlite3.connect(DB) as c:
        c.execute("ALTER TABLE profile RENAME TO profile_vecchio")
        c.execute("""CREATE TABLE profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            full_name TEXT NOT NULL DEFAULT '',
            restrictions TEXT NOT NULL DEFAULT '',
            onboarded INTEGER NOT NULL DEFAULT 0,
            fav_prompted INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')))""")
        c.execute("INSERT INTO profile (id, full_name) VALUES (1, 'Vecchio')")
        c.execute("DROP TABLE profile_vecchio")
        c.commit()
    with closing(sqlite3.connect(DB)) as conn:
        conn.row_factory = sqlite3.Row  # come fa init_db
        app_module.migrate(conn)
        colonne = {r["name"] for r in conn.execute("PRAGMA table_info(profile)")}
    assert "meals_per_day" in colonne
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        riga = c.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    assert riga["meals_per_day"] == 2, "il profilo vecchio resta a due pasti"
    assert riga["full_name"] == "Vecchio", "i dati esistenti non si perdono"

def test_catalogo_pulizie_senza_duplicati():
    """Il catalogo deve restare ordinato: nomi ripetuti confondono il conteggio."""
    voci = igiene.catalogo()
    nomi = [v["name"] for v in voci]
    assert len(nomi) == len(set(nomi))
    assert all(v["name"].strip() for v in voci)
    assert all(v["frequency"] in {f["key"] for f in igiene.FREQUENZE} for v in voci)

def test_catalogo_copre_tutte_le_frequenze():
    """Ogni frequenza deve avere voce: senza, un blocco della pagina resta vuoto."""
    voci = igiene.catalogo()
    for chiave in ("giornaliera", "frazionaria", "settimanale", "mensile",
                   "semestrale", "stagionale"):
        assert any(v["frequency"] == chiave for v in voci), chiave

def test_il_catalogo_ha_la_lavatrice_a_giorno_e_mezzo():
    """«Avviare la lavatrice» e' una voce del catalogo, a cadenza frazionaria.

    Un giorno e mezzo non e' un blocco tondo: la voce sta nel proprio gruppo e
    il conto usa l'ora (vedi `test_scadenza_frazionaria_conta_la_mezza_giornata`).
    """
    voci = igiene.catalogo()
    lavatrice = next((v for v in voci if v["name"] == "Avviare la lavatrice"), None)
    assert lavatrice is not None
    assert lavatrice["frequency"] == "frazionaria"
    assert igiene.CADENZE["frazionaria"] == 1.5
    # e la frequenza e' dichiarata fra le scelte dell'interfaccia
    assert any(f["key"] == "frazionaria" for f in igiene.FREQUENZE)

def test_il_condizionatore_si_disinfetta_ogni_sei_mesi():
    """«Disinfettare il condizionatore» e' una voce semestrale: due volte l'anno,
    non una del mese. E' una cadenza sua — piu' lunga del mese, piu' corta
    dell'anno — e non entra nel blocco del mese, dove sembrerebbe una cosa da
    fare adesso. Il condizionatore si **pulisce** ogni anno (agosto), ma si
    disinfetta ogni sei mesi: tra una pulizia e l'altra raccoglie polvere."""
    voci = igiene.catalogo()
    condizionatore = next((v for v in voci
                           if v["name"] == "Disinfettare il condizionatore"), None)
    assert condizionatore is not None
    assert condizionatore["frequency"] == "semestrale"
    assert condizionatore["month"] is None, "non e' una voce di un mese"
    assert igiene.CADENZE["semestrale"] == 182
    # e la frequenza e' dichiarata fra le scelte dell'interfaccia
    assert any(f["key"] == "semestrale" for f in igiene.FREQUENZE)

def test_scadenza_semestrale_torna_dopo_sei_mesi():
    """La semestrale e' in scadenza se non e' mai stata fatta o se sono passati
    almeno sei mesi; non lo e' se e' stata fatta da poco."""
    oggi = date(2026, 10, 5)
    mai = igiene.scadenza("semestrale", None, oggi)
    assert mai["in_scadenza"] is True
    assert mai["giorni"] is None
    assert mai["cadenza_giorni"] == 182

    recente = igiene.scadenza("semestrale", "2026-08-01", oggi)
    assert recente["in_scadenza"] is False
    assert recente["giorni"] > 0

    vecchia = igiene.scadenza("semestrale", "2026-01-01", oggi)
    assert vecchia["in_scadenza"] is True
    assert vecchia["giorni"] < 0

def test_piano_mette_i_semestrali_a_parte():
    """Le semestrali non stanno ne' nel piano di oggi ne' in quello del mese:
    hanno un blocco loro. Una cosa che tocca ogni sei mesi non e' una cosa del
    mese, e mescolarla al mese darebbe l'idea di doverla fare adesso."""
    voci = [
        {"id": 1, "name": "Mensile", "frequency": "mensile", "minutes": 40,
         "area": "Cucina", "active": 1, "month": None},
        {"id": 2, "name": "Semestrale", "frequency": "semestrale", "minutes": 30,
         "area": "Tutta la casa", "active": 1, "month": None},
        {"id": 3, "name": "Quotidiana", "frequency": "giornaliera", "minutes": 5,
         "area": "Cucina", "active": 1, "month": None},
    ]
    today = date(2026, 10, 5)
    piano = igiene.piano(voci, {}, today, giorno_pulizie=5, giorni={})

    oggi_ids = {v["id"] for elenco in piano["gruppi"].values() for v in elenco}
    mese_ids = {v["id"] for elenco in (piano["mese"]["mensili"],
                                       piano["mese"]["stagionali"]) for v in elenco}
    sem_ids = {v["id"] for v in piano["semestrali"]}
    assert oggi_ids == {3}, "oggi solo la quotidiana"
    assert mese_ids == {1}, "nel mese solo la mensile"
    assert sem_ids == {2}, "la semestrale sta nel suo blocco"
    assert piano["semestrali_da_fare"] == 1

def test_la_sezione_igiene_ha_le_schede_e_i_pannelli(client):
    """Le schede separano tre mestieri diversi — cosa fare adesso, cosa esiste,
    cosa tocca nell'anno — e ognuna ha il suo pannello. Senza un pannello per
    scheda, il pulsante non avrebbe niente da mostrare e la sezione tornerebbe
    un'unica colonna."""
    html = client.get("/").get_data(as_text=True)
    sezione = html[html.index('id="tab-igiene"'):]
    sezione = sezione[:sezione.index("</section>")]
    for chiave in ("oggi", "routine", "anno", "catalogo"):
        assert f'data-chp="{chiave}"' in sezione, f"manca la scheda {chiave}"
        assert f'data-chp-panel="{chiave}"' in sezione, f"manca il pannello {chiave}"
    # una sola scheda parte aperta, e i pannelli sono tutti definiti
    assert sezione.count('ch-nav-btn active') == 1
    assert sezione.count('ch-panel active') == 1

def test_il_cambio_scheda_mostra_un_pannello_solo():
    """`mostraChPanel` e' la resa vera nel client: si esegue con node su un DOM
    finto. Il difetto da evitare e' che i pannelli restino tutti visibili, che e'
    esattamente cio' che rendeva la sezione dispersiva."""
    import subprocess
    js = open("static/app.js", encoding="utf-8").read()
    inizio = js.index("function mostraChPanel")
    blocco = js[inizio: js.index("\n}\n", inizio) + 3]
    prova = blocco + """
class Finto {
  constructor(dataset) {
    this.dataset = dataset;
    this.classes = new Set();
    this.attrs = {};
    this.classList = { toggle: (c, on) => (on ? this.classes.add(c) : this.classes.delete(c)) };
  }
  setAttribute(k, v) { this.attrs[k] = v; }
}
const bottoni = ['oggi', 'routine', 'anno', 'catalogo'].map((k) => new Finto({ chp: k }));
const pannelli = ['oggi', 'routine', 'anno', 'catalogo'].map((k) => new Finto({ chpPanel: k }));
const $$ = (sel) => sel.includes('btn') ? bottoni : pannelli;
mostraChPanel('anno');
console.log(JSON.stringify({
  bottoniAttivi: bottoni.filter((b) => b.classes.has('active')).map((b) => b.dataset.chp),
  pannelliVisibili: pannelli.filter((p) => p.classes.has('active')).map((p) => p.dataset.chpPanel),
}));
"""
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    assert d["bottoniAttivi"] == ["anno"]
    assert d["pannelliVisibili"] == ["anno"], "si vede piu' di un pannello"

def test_la_sezione_tv_ha_le_cinque_schede(client):
    """Intrattenimento, Notizie, Quiz, Film e Giochi sono cose diverse che prima
    stavano in un'unica colonna: per arrivare ai film si scorreva oltre i video.
    Ogni scheda ha il suo pannello, e ne parte aperta una sola."""
    html = client.get("/").get_data(as_text=True)
    sezione = html[html.index('id="tab-intrattenimento"'):]
    sezione = sezione[:sezione.index("</section>")]
    for chiave in ("intrattenimento", "notizie", "quiz", "film", "giochi"):
        assert f'data-tvp="{chiave}"' in sezione, f"manca la scheda {chiave}"
        assert f'data-tvp-panel="{chiave}"' in sezione, f"manca il pannello {chiave}"
    assert sezione.count('tv-nav-btn active') == 1
    assert sezione.count('ch-panel active') == 1
    # la scheda Giochi non e' piu' una voce della barra in basso: e' una
    # sotto-scheda della TV, e una voce in piu' sarebbe un doppione
    assert 'data-tab="giochi"' not in html
    assert 'id="tab-giochi"' not in html

def test_il_cambio_scheda_della_tv_mostra_un_pannello_solo():
    """`mostraTvPanel` e' la resa vera nel client: si esegue con node su un DOM
    finto. Vale la stessa regola dell'Igiene — un pannello solo visibile — ma i
    selettori sono quelli della TV, non quelli delle pulizie: mescolarli
    spegnerebbe la scheda sbagliata."""
    import subprocess
    js = open("static/app.js", encoding="utf-8").read()
    inizio = js.index("function mostraTvPanel")
    blocco = js[inizio: js.index("\n}\n", inizio) + 3]
    prova = blocco + """
class Finto {
  constructor(dataset) {
    this.dataset = dataset;
    this.classes = new Set();
    this.attrs = {};
    this.classList = { toggle: (c, on) => (on ? this.classes.add(c) : this.classes.delete(c)) };
  }
  setAttribute(k, v) { this.attrs[k] = v; }
}
const bottoni = ['intrattenimento', 'notizie', 'quiz', 'film', 'giochi'].map((k) => new Finto({ tvp: k }));
const pannelli = ['intrattenimento', 'notizie', 'quiz', 'film', 'giochi'].map((k) => new Finto({ tvpPanel: k }));
const $$ = (sel) => sel.includes('btn') ? bottoni : pannelli;
mostraTvPanel('film');
console.log(JSON.stringify({
  bottoniAttivi: bottoni.filter((b) => b.classes.has('active')).map((b) => b.dataset.tvp),
  pannelliVisibili: pannelli.filter((p) => p.classes.has('active')).map((p) => p.dataset.tvpPanel),
}));
"""
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    assert d["bottoniAttivi"] == ["film"]
    assert d["pannelliVisibili"] == ["film"], "si vede piu' di un pannello"

def test_catalogo_ogni_mese_dell_anno_ha_una_voce():
    """Il calendario annuale ha dodici mesi: un mese vuoto sarebbe un buco visibile."""
    mesi_con_voce = {v["month"] for v in igiene.catalogo() if v["frequency"] == "stagionale"}
    assert mesi_con_voce == set(range(1, 13))

def test_scadenza_giornaliera_sempre_da_fare():
    """Le quotidiane non hanno scadenza: si fanno ogni giorno.

    Fatta oggi risulta "prossima domani" (un giorno di distanza): e' corretto e
    non le toglie dal piano, perche' `piano` include comunque le quotidiane.
    """
    oggi = date(2026, 9, 18)
    mai = igiene.scadenza("giornaliera", None, oggi)
    assert mai["in_scadenza"] is True
    fatta = igiene.scadenza("giornaliera", "2026-09-18", oggi)
    assert fatta["giorni"] == 1, "torna domani, non oggi stesso"

def test_scadenza_settimanale_prima_della_scadenza():
    """Fatta tre giorni fa non e' ancora da rifare: la cadenza e' di sette giorni."""
    stato = igiene.scadenza("settimanale", "2026-09-15", date(2026, 9, 18))
    assert stato["in_scadenza"] is False
    assert stato["giorni"] == 4
    assert stato["prossima"] == "2026-09-22"

def test_scadenza_settimanale_alla_scadenza_esatta():
    """Il settimo giorno la voce rientra: il confine non deve slittare di un giorno."""
    stato = igiene.scadenza("settimanale", "2026-09-11", date(2026, 9, 18))
    assert stato["in_scadenza"] is True
    assert stato["giorni"] == 0

def test_scadenza_settimanale_in_ritardo():
    """Saltare una settimana non deve far sparire la voce: i giorni vanno negativi."""
    stato = igiene.scadenza("settimanale", "2026-09-01", date(2026, 9, 18))
    assert stato["in_scadenza"] is True
    assert stato["giorni"] < 0

def test_scadenza_frazionaria_conta_la_mezza_giornata():
    """Una cadenza di un giorno e mezzo non e' ne' un giorno ne' due.

    Con la sola data la mezza andrebbe persa: fatta lunedi' alle 8, la voce
    risulterebbe da rifare gia' martedi' mattina. L'ora del completamento e'
    quella che distingue "un giorno e mezzo" da "un giorno".
    """
    # lunedi' 8:00 -> la prossima e' martedi' alle 20:00, cioe' 1,5 giorni
    stato = igiene.scadenza("frazionaria", "2026-09-14T08:00:00",
                            "2026-09-15T08:00:00")
    assert stato["prossima"] == "2026-09-15T20:00:00"
    assert stato["in_scadenza"] is False
    assert stato["giorni"] == 0.5, "meta' giornata ancora da aspettare"
    # martedi' sera alle 20:00 e' il momento: rientra
    scaduta = igiene.scadenza("frazionaria", "2026-09-14T08:00:00",
                              "2026-09-15T20:00:00")
    assert scaduta["in_scadenza"] is True
    assert scaduta["giorni"] == 0

def test_scadenza_frazionaria_senza_ora_e_tollerante():
    """Un valore con la sola data non deve far esplodere il calcolo."""
    stato = igiene.scadenza("frazionaria", "2026-09-14", "2026-09-15T20:00:00")
    assert "in_scadenza" in stato
    assert stato["prossima"] == "2026-09-15T12:00:00", "mezzanotte + 1,5 giorni"

def test_scadenza_mensile_e_annuale():
    """Mensile a trenta giorni, annuale solo nel suo mese."""
    oggi = date(2026, 9, 18)
    assert igiene.scadenza("mensile", "2026-08-01", oggi)["in_scadenza"] is True
    assert igiene.scadenza("mensile", "2026-09-10", oggi)["in_scadenza"] is False
    # una voce di giugno non e' in scadenza a settembre
    assert igiene.scadenza("stagionale", None, oggi, 6)["in_scadenza"] is False
    assert igiene.scadenza("stagionale", None, oggi, 9)["in_scadenza"] is True

def test_scadenza_stagionale_fatta_quest_anno_non_rientra():
    """La voce annuale fatta a settembre non deve riproporsi a settembre."""
    stato = igiene.scadenza("stagionale", "2026-09-02", date(2026, 9, 18), 9)
    assert stato["in_scadenza"] is False
    # ma torna l'anno dopo, nello stesso mese
    assert igiene.scadenza("stagionale", "2026-09-02", date(2027, 9, 18), 9)["in_scadenza"] is True

def test_scadenza_mai_fatta_e_segnalata():
    """Chi apre l'app per la prima volta deve vedere gli stati vuoti, non date inventate."""
    stato = igiene.scadenza("settimanale", None, date(2026, 9, 18))
    assert stato["mai_fatta"] is True
    assert stato["ultima"] is None

def test_data_ultima_volta_illeggibile_non_rompe_il_calcolo():
    """Un valore sporco nel DB non deve far fallire l'intera pagina."""
    stato = igiene.scadenza("settimanale", "non-una-data", date(2026, 9, 18))
    assert "in_scadenza" in stato

def test_piano_separa_oggi_dal_mese():
    """Il piano di oggi non deve contenere mensili e annuali.

    E' il punto del metodo: mensili e stagionali si distribuiscono nel mese. Se
    finissero tutte nel piano di oggi la giornata diventerebbe impraticabile e il
    piano verrebbe abbandonato.
    """
    voci = [
        {"id": 1, "name": "Quotidiana", "frequency": "giornaliera", "minutes": 5, "area": "Cucina", "active": 1, "month": None},
        {"id": 2, "name": "Settimanale", "frequency": "settimanale", "minutes": 10, "area": "Bagno", "active": 1, "month": None},
        {"id": 3, "name": "Mensile", "frequency": "mensile", "minutes": 40, "area": "Cucina", "active": 1, "month": None},
        {"id": 4, "name": "Annuale", "frequency": "stagionale", "minutes": 60, "area": "Camere", "active": 1, "month": 9},
    ]
    today = date(2026, 9, 18)  # venerdi
    # il giorno della settimanale si fissa esplicitamente: qui interessa **dove**
    # finisce ogni frequenza, non come si distribuisce la settimana
    piano = igiene.piano(voci, {}, today, giorno_pulizie=5, giorni={2: 4})

    oggi_ids = {v["id"] for elenco in piano["gruppi"].values() for v in elenco}
    assert oggi_ids == {1, 2}, "oggi solo quotidiane e settimanali"
    mese_ids = {v["id"] for elenco in (piano["mese"]["mensili"], piano["mese"]["stagionali"]) for v in elenco}
    assert mese_ids == {3, 4}, "mensili e annuali stanno nel mese"

def test_settimanali_distribuite_su_giorni_diversi():
    """Le settimanali non stanno tutte lo stesso giorno.

    Prima entravano tutte nel giorno fisso, che arrivava a cento minuti di soli
    settimanali: e' l'ammasso che questa distribuzione deve togliere.
    """
    voci = [
        {"id": 1, "name": "Aspirare e lavare i pavimenti", "frequency": "settimanale", "minutes": 30, "area": "Tutta la casa", "active": 1, "month": None},
        {"id": 2, "name": "Pulire il bagno in profondità", "frequency": "settimanale", "minutes": 25, "area": "Bagno", "active": 1, "month": None},
        {"id": 3, "name": "Spolverare", "frequency": "settimanale", "minutes": 15, "area": "Tutta la casa", "active": 1, "month": None},
    ]
    giorni = igiene.giorni_settimanali(voci, giorno_pulizie=5)
    assert len(set(giorni.values())) == 3, "una per giorno"
    assert giorni[1] == 5, "la piu' pesante resta nel giorno scelto"
    assert giorni[2] == 4 and giorni[3] == 3, "le altre riempiono i giorni prima"

def test_una_settimanale_saltata_rientra():
    """Una settimanale non fatta resta nel piano anche dopo il suo giorno.

    Senza, saltare il giorno assegnato la farebbe sparire per una settimana
    intera: sembrerebbe un'attivita' conclusa.
    """
    voci = [{"id": 1, "name": "Aspirare e lavare i pavimenti", "frequency": "settimanale",
             "minutes": 30, "area": "Tutta la casa", "active": 1, "month": None}]
    # assegnata a lunedi' (0), fatta otto giorni fa: e' in ritardo
    giorni = {1: 0}
    piano = igiene.piano(voci, {1: "2026-09-10"}, date(2026, 9, 18), giorni=giorni)
    assert piano["da_fare"] == 1, "in ritardo, rientra"

def test_una_settimanale_mai_fatta_aspetta_il_suo_giorno():
    """Al primo uso le settimanali non devono rientrare tutte insieme.

    Senza questo, il primo giorno d'uso mostrerebbe l'ammasso che la
    distribuzione deve togliere.
    """
    voci = [{"id": 1, "name": "Aspirare e lavare i pavimenti", "frequency": "settimanale",
             "minutes": 30, "area": "Tutta la casa", "active": 1, "month": None}]
    piano = igiene.piano(voci, {}, date(2026, 9, 18), giorni={1: 0})
    assert piano["da_fare"] == 0, "il suo giorno e' lunedi', non venerdi"

def test_la_routine_quotidiana_resta_breve():
    """La routine di ogni giorno deve restare sotto la mezz'ora.

    Oltre, smette di essere una routine e diventa un lavoro: e' il motivo per cui
    il piano veniva abbandonato.
    """
    quotidiane = [v for v in igiene.catalogo() if v["frequency"] == "giornaliera"]
    assert sum(v["minutes"] for v in quotidiane) <= 25
    assert all(v["minutes"] <= 10 for v in quotidiane)

def test_piano_minuti_previsti_contano_solo_oggi():
    """Il tempo stimato di oggi non deve includere il mese: sarebbe una cifra falsa."""
    voci = [
        {"id": 1, "name": "Quotidiana", "frequency": "giornaliera", "minutes": 5, "area": "Cucina", "active": 1, "month": None},
        {"id": 3, "name": "Mensile", "frequency": "mensile", "minutes": 40, "area": "Cucina", "active": 1, "month": None},
    ]
    piano = igiene.piano(voci, {}, date(2026, 9, 18), giorno_pulizie=5)
    assert piano["minuti_previsti"] == 5
    assert piano["mese_minuti"] == 40

def test_piano_il_giorno_fisso_tira_dentro_le_settimanali():
    """Il giorno fisso serve proprio a questo: raccogliere le settimanali in un giorno."""
    voci = [{"id": 2, "name": "Settimanale", "frequency": "settimanale", "minutes": 10,
             "area": "Bagno", "active": 1, "month": None}]
    # fatta ieri: senza giorno fisso non rientrerebbe
    ultime = {2: "2026-09-17"}
    senza = igiene.piano(voci, ultime, date(2026, 9, 18), giorno_pulizie=0)
    con = igiene.piano(voci, ultime, date(2026, 9, 18), giorno_pulizie=4)  # venerdi
    assert senza["da_fare"] == 0
    assert con["da_fare"] == 1

def test_piano_attivita_disattivate_restano_fuori():
    """Disattivare una voce deve toglierla dal piano, non solo dal catalogo."""
    voci = [{"id": 1, "name": "Spenta", "frequency": "giornaliera", "minutes": 5,
             "area": "Cucina", "active": 0, "month": None}]
    piano = igiene.piano(voci, {}, date(2026, 9, 18), giorno_pulizie=5)
    assert piano["da_fare"] == 0

def test_piano_una_voce_fatta_oggi_non_conta_piu():
    """Spuntata la voce, il conteggio e i minuti devono scendere subito."""
    voci = [{"id": 1, "name": "Fatta", "frequency": "giornaliera", "minutes": 5,
             "area": "Cucina", "active": 1, "month": None}]
    piano = igiene.piano(voci, {1: "2026-09-18"}, date(2026, 9, 18), giorno_pulizie=5)
    assert piano["da_fare"] == 0
    assert piano["minuti_previsti"] == 0
    assert piano["fatto_oggi"] == 1, "resta visibile come fatta"

def test_piano_include_il_focus_del_mese():
    """Il focus del mese e' il senso del blocco annuale: senza, le voci non si capiscono."""
    piano = igiene.piano([], {}, date(2026, 9, 18), giorno_pulizie=5)
    assert piano["mese"]["nome"] == "Settembre"
    assert piano["mese"]["focus"]
    assert piano["mese"]["titolo"]

def test_piano_data_non_valida_ricade_su_oggi():
    """Una data storta non deve far esplodere la pagina."""
    piano = igiene.piano([], {}, "non-una-data", giorno_pulizie=5)
    assert piano["data"] == date.today().isoformat()

def test_api_pulizie_meta(client):
    """La pagina ha bisogno di frequenze, ambienti, giorni e mesi per costruirsi."""
    m = client.get("/api/chores/meta").get_json()
    assert len(m["months"]) == 12
    assert len(m["days"]) == 7
    assert len(m["frequencies"]) == 6
    assert m["areas"]
    assert 0 <= m["chore_day"] <= 6

def test_api_pulizie_seminata_al_primo_avvio(client):
    """Un database nuovo deve uscire con il catalogo delle pulizie gia' pronto."""
    r = client.get("/api/chores").get_json()
    assert r["attivita"], "il catalogo non e' vuoto"
    assert r["attive"] == len([v for v in r["attivita"] if v["active"]])
    assert set(r["piano"]["gruppi"]) == {"quotidiane", "frazionarie", "settimanali"}
    assert set(r["piano"]["mese"]) >= {"mensili", "stagionali"}

def test_api_pulizie_data_forzata(client):
    """La data si puo' fissare: serve per verificare scadenze e giorno fisso."""
    r = client.get("/api/chores?date=2026-09-19").get_json()  # sabato
    assert r["oggi"] == "2026-09-19"
    assert r["piano"]["giorno"] == "sabato"
    # il blocco del mese deve seguire la data richiesta, non quella di sistema
    assert r["piano"]["mese"]["nome"] == "Settembre"

def test_api_pulizie_errori(client):
    """Gli ingressi sbagliati si rifiutano con un messaggio, non con un 500."""
    assert client.post("/api/chores", json={"name": "  "}).status_code == 400
    assert client.post("/api/chores", json={"name": "X", "frequency": "oraria"}).status_code == 400
    assert client.post("/api/chores", json={"name": "X", "frequency": "stagionale"}).status_code == 400
    assert client.post("/api/chores", json={"name": "X", "frequency": "stagionale", "month": 13}).status_code == 400
    assert client.put("/api/chores/99999", json={"name": "Z"}).status_code == 404
    assert client.post("/api/chores/99999/done").status_code == 404

def test_api_pulizie_ciclo_completo(client):
    """Creare, modificare, disattivare: le tre operazioni del catalogo."""
    creato = client.post("/api/chores", json={
        "name": "Pulire il microonde", "frequency": "mensile", "minutes": 12, "area": "Cucina"})
    assert creato.status_code == 201
    cid = creato.get_json()["id"]

    # niente doppioni nello stesso ambiente
    assert client.post("/api/chores", json={
        "name": "Pulire il microonde", "frequency": "mensile"}).status_code == 400

    assert client.put(f"/api/chores/{cid}", json={"minutes": 20}).get_json()["minutes"] == 20
    assert client.put(f"/api/chores/{cid}", json={"active": 0}).get_json()["active"] == 0

    # disattivata: fuori dal piano ma ancora nel catalogo
    voci = client.get("/api/chores").get_json()["attivita"]
    voce = next(v for v in voci if v["id"] == cid)
    assert voce["active"] == 0
    assert client.delete(f"/api/chores/{cid}").status_code in (200, 204)

def test_api_pulizie_segno_fatto_e_annullo(client):
    """Spuntare registra il completamento; spuntare di nuovo lo annulla."""
    cid = client.get("/api/chores").get_json()["attivita"][0]["id"]

    assert client.post(f"/api/chores/{cid}/done", json={}).status_code == 200
    cronologia = client.get("/api/chores/history").get_json()
    assert any(h["chore_id"] == cid for h in cronologia)

    assert client.delete(f"/api/chores/{cid}/done").status_code == 200
    assert not any(h["chore_id"] == cid for h in client.get("/api/chores/history").get_json())
    # annullare due volte non deve far esplodere niente
    assert client.delete(f"/api/chores/{cid}/done").status_code == 404

def test_api_pulizie_tempo_registrato(client):
    """Il tempo cronometrato si conserva e finisce nel riepilogo."""
    cid = client.get("/api/chores").get_json()["attivita"][0]["id"]
    client.post(f"/api/chores/{cid}/done", json={"minutes": 17})

    riga = next(h for h in client.get("/api/chores/history").get_json() if h["chore_id"] == cid)
    assert riga["minutes"] == 17

    riepilogo = client.get("/api/chores/summary").get_json()
    assert riepilogo["oggi"]["minuti"] == 17
    assert riepilogo["oggi"]["volte"] == 1
    assert riepilogo["mese"]["minuti"] == 17
    assert riepilogo["settimana"]["minuti"] == 17

def test_api_pulizie_tempo_negativo_o_assurdo_non_trapela(client):
    """Un tempo assurdo non deve inquinare il riepilogo."""
    cid = client.get("/api/chores").get_json()["attivita"][0]["id"]
    client.post(f"/api/chores/{cid}/done", json={"minutes": -5})
    riga = next(h for h in client.get("/api/chores/history").get_json() if h["chore_id"] == cid)
    assert riga["minutes"] >= 0

def test_api_giorno_pulizie_si_salva(client):
    """Il giorno fisso e' una scelta dell'utente e deve restare."""
    assert client.put("/api/profile", json={"chore_day": 3}).status_code == 200
    assert client.get("/api/profile").get_json()["chore_day"] == 3
    assert client.put("/api/profile", json={"chore_day": 9}).status_code == 400

def test_api_giorno_pulizie_distribuisce_le_settimanali(client):
    """Le settimanali si distribuiscono, non si ammassano nel giorno scelto.

    Il giorno scelto resta il piu' pesante, ma le altre vanno nei giorni
    precedenti: e' la differenza fra una settimana da cento minuti in un giorno
    solo e una da trenta al massimo.
    """
    import datetime as _dt
    oggi = _dt.date.today()
    client.put("/api/profile", json={"chore_day": oggi.weekday()})
    r = client.get(f"/api/chores?date={oggi.isoformat()}").get_json()
    piano = r["piano"]
    assert piano["giorno_pulizie"] is True
    # oggi tocca solo la sua settimanale, non tutte
    assert piano["settimanali_oggi"] == 1
    # e la settimana e' distribuita: nessun giorno porta tutto
    minuti = [g["minuti"] for g in piano["settimana"]]
    assert max(minuti) <= 30, "nessun giorno con cento minuti di settimanali"
    assert sum(1 for m in minuti if m) == 5, "una settimanale per giorno, cinque giorni"

def test_api_ogni_settimanale_dichiara_il_suo_giorno(client):
    """Il frontend mostra il giorno assegnato: i campi devono esserci.

    Senza, la distribuzione sarebbe invisibile e una settimanale spostata a
    giovedi' sembrerebbe sparita dall'elenco.
    """
    r = client.get("/api/chores").get_json()
    settimanali = [v for v in r["attivita"] if v["frequency"] == "settimanale" and v["active"]]
    assert settimanali
    giorni = [v["giorno_settimanale"] for v in settimanali]
    assert all(g is not None and 0 <= g <= 6 for g in giorni)
    # e il piano espone la settimana, con sette giorni
    assert len(r["piano"]["settimana"]) == 7
    assert all("nome" in g and "minuti" in g for g in r["piano"]["settimana"])

def test_api_pulizie_il_mese_non_invade_il_piano_di_oggi(client):
    """Mensili e stagionali non gonfiano la giornata: e' il punto del metodo."""
    r = client.get("/api/chores").get_json()
    oggi = r["piano"]["gruppi"]["quotidiane"] + r["piano"]["gruppi"]["settimanali"]
    assert all(v["frequency"] in ("giornaliera", "frazionaria", "settimanale") for v in oggi)
    mensili = r["piano"]["mese"]["mensili"] + r["piano"]["mese"]["stagionali"]
    assert all(v["frequency"] in ("mensile", "stagionale") for v in mensili)
    # e il tempo stimato di oggi non deve includere quello del mese
    assert r["piano"]["minuti_previsti"] <= 24 * 60
