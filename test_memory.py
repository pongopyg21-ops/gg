"""Il Memory, il secondo gioco della sezione Giochi (accanto a Snake).

La logica del gioco e' pura: si prova con node, come lo Snake. Fixture in
`conftest.py`; helper in `test_comuni.py`.
"""
from test_comuni import *  # noqa: F401,F403


def _memory_js(client):
    return client.get("/static/memory.js").get_data(as_text=True)


def _memory_puro(client, coda):
    """Estrae le funzioni pure del Memory e le esegue con node.

    Le funzioni prendono lo stato e ne restituiscono uno nuovo, senza DOM: il
    test decide la posizione delle carte invece di sperare nel mescolamento."""
    js = _memory_js(client)
    costanti = ("const MEMORY_COPPIE = 8;\n"
                "const MEMORY_SIMBOLI = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];\n")
    codice = "".join(_estrai_funzione_js(js, n)
                     for n in ("memoryMazzo", "memoryNuovo", "memoryGira",
                               "memoryNascondi", "memoryAspetta"))
    return _esegui_node(costanti + codice + coda)


def test_il_mazzo_ha_ogni_coppia_due_volte(client):
    """Il mazzo e' otto coppie: sedici carte, ogni simbolo esattamente due volte.
    Fisher-Yates mescola una permutazione del mazzo, quindi il conteggio non
    cambia qualunque cosa esca dal generatore."""
    d = _memory_puro(client, """
const m = memoryMazzo(() => 0.5);
const conti = {};
m.forEach((s) => { conti[s] = (conti[s] || 0) + 1; });
const stato = memoryNuovo(() => 0.5);
console.log(JSON.stringify({ lung: m.length, conti: conti,
                             stato: stato.carte.length, mosse: stato.mosse,
                             coperte: stato.carte.every((c) => c.stato === 'coperta') }));
""")
    assert d["lung"] == 16, d
    assert d["stato"] == 16
    assert d["conti"] == {str(i): 2 for i in range(8)}, d
    assert d["mosse"] == 0
    assert d["coperte"] is True


def test_due_carte_uguali_restano_scoperte_per_sempre(client):
    """Girare due carte con lo stesso simbolo le segna come **trovate**, conta
    una mossa e svuota l'attesa: non c'e' niente da nascondere. Con l'unica
    coppia del mazzo, la partita e' anche finita."""
    d = _memory_puro(client, """
const stato = { carte: [
  { simbolo: 0, stato: 'coperta' }, { simbolo: 0, stato: 'coperta' }],
  indice: [], mosse: 0, finito: false };
const s1 = memoryGira(stato, 0);
const s2 = memoryGira(s1, 1);
console.log(JSON.stringify({ dopo1: s1.carte[0].stato, attesa1: s1.indice.length,
  a: s2.carte[0].stato, b: s2.carte[1].stato, mosse: s2.mosse,
  attesa: s2.indice.length, finito: s2.finito }));
""")
    assert d["dopo1"] == "scoperta"
    assert d["attesa1"] == 1, "alla prima carta non si decide ancora"
    assert d["a"] == d["b"] == "trovata"
    assert d["mosse"] == 1
    assert d["attesa"] == 0, "la coppia trovata non resta in attesa"
    assert d["finito"] is True, "con tutte le carte trovate il gioco e' finito"


def test_due_carte_diverse_si_ricoprono(client):
    """Due carte diverse restano **scoperte** e in attesa (cosi' l'utente le
    vede), poi `memoryNascondi` le rimette coperte. La decisione sta nella
    funzione pura, il 'quando' lo decide l'interfaccia."""
    d = _memory_puro(client, """
const stato = { carte: [
  { simbolo: 0, stato: 'coperta' }, { simbolo: 0, stato: 'coperta' },
  { simbolo: 1, stato: 'coperta' }, { simbolo: 1, stato: 'coperta' }],
  indice: [], mosse: 0, finito: false };
const s1 = memoryGira(stato, 0);
const s2 = memoryGira(s1, 2);
const attesa = memoryAspetta(s2);
const s3 = memoryNascondi(s2);
console.log(JSON.stringify({ a: s2.carte[0].stato, b: s2.carte[2].stato,
  attesa: attesa, indice: s2.indice.length, mosse: s2.mosse, finito: s2.finito,
  dopoA: s3.carte[0].stato, dopoB: s3.carte[2].stato, dopoIndice: s3.indice.length,
  dopoMosse: s3.mosse }));
""")
    assert d["a"] == d["b"] == "scoperta"
    assert d["attesa"] is True
    assert d["indice"] == 2 and d["mosse"] == 1 and d["finito"] is False
    assert d["dopoA"] == d["dopoB"] == "coperta"
    assert d["dopoIndice"] == 0
    assert d["dopoMosse"] == 1, "ricoprire non e' una mossa"


def test_non_si_scopre_una_terza_carta_in_attesa(client):
    """Con due carte ancora scoperte una terza non si gira: e' la guardia che
    impedisce di scoprirne tre e perdere il senso del Memory."""
    d = _memory_puro(client, """
const stato = { carte: [
  { simbolo: 0, stato: 'scoperta' }, { simbolo: 0, stato: 'coperta' },
  { simbolo: 1, stato: 'scoperta' }, { simbolo: 2, stato: 'coperta' }],
  indice: [0, 2], mosse: 1, finito: false };
const dopo = memoryGira(stato, 3);
console.log(JSON.stringify({ stesso: dopo === stato, terza: dopo.carte[3].stato,
  indice: dopo.indice.length }));
""")
    assert d["stesso"] is True, "la terza carta deve essere ignorata"
    assert d["terza"] == "coperta"
    assert d["indice"] == 2


def test_non_si_rigira_una_carta_gia_scoperta(client):
    """Toccare di nuovo una carta gia' scoperta non fa niente: non consuma una
    mossa ne' apre un'attesa nuova."""
    d = _memory_puro(client, """
const stato = { carte: [
  { simbolo: 0, stato: 'coperta' }, { simbolo: 0, stato: 'coperta' }],
  indice: [], mosse: 0, finito: false };
const s1 = memoryGira(stato, 0);
const s2 = memoryGira(s1, 0);
console.log(JSON.stringify({ stesso: s2 === s1, attesa: s2.indice.length,
  mosse: s2.mosse }));
""")
    assert d["stesso"] is True
    assert d["attesa"] == 1 and d["mosse"] == 0


def test_il_gioco_vince_col_mazzo_completo(client):
    """L'ultima coppia chiude la partita: `finito` diventa vero solo quando
    **tutte** le carte sono trovate, non quando lo sono quasi tutte."""
    d = _memory_puro(client, """
const carte = [];
for (let s = 0; s < 7; s++) {
  carte.push({ simbolo: s, stato: 'trovata' }, { simbolo: s, stato: 'trovata' });
}
carte.push({ simbolo: 7, stato: 'coperta' }, { simbolo: 7, stato: 'coperta' });
let stato = { carte: carte, indice: [], mosse: 0, finito: false };
stato = memoryGira(stato, 14);
const meta = stato.finito;
stato = memoryGira(stato, 15);
console.log(JSON.stringify({ meta: meta, finito: stato.finito, mosse: stato.mosse }));
""")
    assert d["meta"] is False, "finche' manca una coppia non si e' finito"
    assert d["finito"] is True
    assert d["mosse"] == 1


def test_la_scheda_giochi_ha_due_giochi(client):
    """Nella scheda Giochi ci sono **due** giochi: Snake e Memory. La scelta e'
    una riga di pulsanti, e un gioco per volta e' visibile."""
    html = client.get("/").get_data(as_text=True)
    assert 'data-gioco="snake"' in html and 'data-gioco="memory"' in html
    assert 'data-gioco-panel="snake"' in html and 'data-gioco-panel="memory"' in html
    assert 'id="memory-griglia"' in html
    assert 'id="memory-avvia"' in html and 'id="memory-mosse"' in html
    assert 'id="memory-record"' in html
    assert "/static/memory.js" in html, "il secondo gioco va caricato"
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function mostraGioco" in js, "app.js deve saper mostrare un gioco per volta"


def test_app_js_non_conosce_il_memory(client):
    """Come per Snake, `app.js` non nomina le funzioni del Memory: vivono in
    `memory.js` e il gioco si aggancia da solo alla sua scheda."""
    js = client.get("/static/app.js").get_data(as_text=True)
    for nome in ("avviaMemory", "memoryGira", "memoryNuovo", "memoryDisegna"):
        assert nome not in js, f"app.js non deve nominare {nome}"


def test_il_memory_js_non_chiama_funzioni_che_non_esiste(client):
    """Stesso controllo dello Snake sul file del Memory: un riferimento a una
    funzione rimossa e' un `ReferenceError` a runtime, non un errore di sintassi.
    I due file condividono lo scope, quindi si controlla l'unione."""
    js = _memory_js(client)
    app_js = client.get("/static/app.js").get_data(as_text=True)
    orfane = _nomi_chiamati_senza_definizione(app_js + "\n" + js)
    assert not orfane, "il gioco chiama funzioni che non esistono: " + ", ".join(orfane)


def test_il_memory_e_nella_scocca_e_versionato(client):
    """`memory.js` va salvato dal service worker (si gioca anche senza rete) e
    versionato come gli altri: senza la versione, il browser terrebbe la copia
    vecchia dopo un aggiornamento."""
    sw = client.get("/static/sw.js").get_data(as_text=True)
    assert "/static/memory.js" in sw, "il gioco deve stare nella scocca"
    assert "maggiordomo-scocca-v12" in sw
    html = client.get("/").get_data(as_text=True)
    import re
    assert re.search(r'/static/memory\.js\?v=', html), "manca la versione nell'indirizzo"
