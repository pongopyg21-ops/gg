"""Il gioco Snake nella sezione Giochi.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_il_serpente_avanza_e_la_coda_segue(client):
    """Un passo senza cibo: la testa va avanti di una cella e la coda si accorcia
    di una. La lunghezza non cambia, il serpente scivola."""
    d = _snake_puro(client, """
const s = snakeNuovo(() => 0);           // cibo in (0,0)
const prima = s.corpo.length;
const dopo = snakePasso(s, () => 0);
console.log(JSON.stringify({ testa: dopo.corpo[0], lung: dopo.corpo.length,
                             prima: prima, punti: dopo.punteggio, finito: dopo.finito }));
""")
    assert d["testa"] == {"x": 8, "y": 7}, d
    assert d["lung"] == d["prima"] == 3
    assert d["punti"] == 0 and d["finito"] is False

def test_il_serpente_mangia_e_cresce(client):
    """Mangiando, la coda non si toglie: il serpente si allunga di una cella e il
    punteggio sale. E' l'unica cosa che fa crescere."""
    d = _snake_puro(client, """
const s = { cols: 15, rows: 15, corpo: [{x:7,y:7},{x:6,y:7},{x:5,y:7}],
            dir: {x:1,y:0}, cibo: {x:8,y:7}, punteggio: 0, finito: false };
const dopo = snakePasso(s, () => 0);
console.log(JSON.stringify({ lung: dopo.corpo.length, punti: dopo.punteggio,
                             cibo: dopo.cibo }));
""")
    assert d["lung"] == 4
    assert d["punti"] == 1
    assert d["cibo"] is not None, "dopo aver mangiato il cibo ricompare"

def test_il_serpente_muore_contro_il_muro(client):
    """Uscire dal campo e' la fine: la testa non puo' stare fuori griglia."""
    d = _snake_puro(client, """
const s = { cols: 15, rows: 15, corpo: [{x:14,y:7},{x:13,y:7}],
            dir: {x:1,y:0}, cibo: {x:0,y:0}, punteggio: 3, finito: false };
const dopo = snakePasso(s, () => 0);
console.log(JSON.stringify({ finito: dopo.finito, punti: dopo.punteggio }));
""")
    assert d["finito"] is True
    assert d["punti"] == 3, "la morte non cancella il punteggio"

def test_il_serpente_muore_contro_se_stesso(client):
    """Toccarsi e' la fine, ma solo toccando il corpo vero: la coda che si sta
    spostando non conta (vedi il test successivo)."""
    d = _snake_puro(client, """
const s = { cols: 15, rows: 15,
            corpo: [{x:5,y:5},{x:6,y:5},{x:6,y:6},{x:5,y:6},{x:4,y:6}],
            dir: {x:0,y:1}, cibo: {x:0,y:0}, punteggio: 0, finito: false };
const dopo = snakePasso(s, () => 0);
console.log(JSON.stringify({ finito: dopo.finito }));
""")
    assert d["finito"] is True

def test_il_serpente_non_muore_inseguendo_la_coda(client):
    """La cella lasciata libera dalla coda in movimento non e' un ostacolo:
    altrimenti il serpente morirebbe inseguendo la propria coda, che e' un
    movimento normale."""
    d = _snake_puro(client, """
const s = { cols: 15, rows: 15,
            corpo: [{x:5,y:5},{x:6,y:5},{x:6,y:6},{x:5,y:6}],
            dir: {x:0,y:1}, cibo: {x:0,y:0}, punteggio: 0, finito: false };
const dopo = snakePasso(s, () => 0);
console.log(JSON.stringify({ finito: dopo.finito, testa: dopo.corpo[0] }));
""")
    assert d["finito"] is False, "la coda che si sposta non e' un muro"
    assert d["testa"] == {"x": 5, "y": 6}

def test_il_serpente_non_torna_indietro(client):
    """La direzione opposta si ignora: applicandola il serpente entrerebbe nella
    propria testa e morirebbe per un tasto sbagliato."""
    d = _snake_puro(client, """
const indietro = snakeDirezione({x:-1,y:0}, {x:1,y:0});
const laterale = snakeDirezione({x:0,y:1}, {x:1,y:0});
const avanti = snakeDirezione({x:1,y:0}, {x:1,y:0});
console.log(JSON.stringify({ indietro: indietro, laterale: laterale, avanti: avanti }));
""")
    assert d["indietro"] == {"x": 1, "y": 0}, "il contrario non si applica"
    assert d["laterale"] == {"x": 0, "y": 1}
    assert d["avanti"] == {"x": 1, "y": 0}

def test_la_sezione_giochi_ha_il_campo_e_i_comandi(client):
    """Giochi e' una sotto-scheda della TV, con il campo, la croce direzionale e
    il record. Senza i nodi il disegno scriverebbe nel vuoto e la scheda
    resterebbe muta."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'data-tvp="giochi"' in html, "manca la sotto-scheda Giochi"
    assert 'data-tvp-panel="giochi"' in html, "manca il pannello Giochi"
    assert 'id="snake-canvas"' in html, "manca il campo di gioco"
    assert 'id="snake-avvia"' in html and 'id="snake-record"' in html
    assert html.count("snake-freccia") == 4, "la croce direzionale ha quattro frecce"
    assert "/static/snake.js" in html, "il gioco va caricato"

def test_app_js_non_conosce_il_gioco(client):
    """Il gioco si aggancia da solo, `app.js` non lo chiama.

    Non e' una preferenza: `app.js` e' scandito da un test che pretende che ogni
    funzione chiamata esista **in quel file**, e le funzioni del gioco vivono in
    `snake.js`. Chiamandole da `app.js` il test le vedrebbe come orfane — ed e'
    il difetto vero (un `ReferenceError` all'accesso) che quel test esiste per
    cogliere."""
    js = client.get("/static/app.js").get_data(as_text=True)
    for nome in ("avviaSnake", "snakePasso", "snakeNuovo", "snakeDisegna"):
        assert nome not in js, f"app.js non deve nominare {nome}"

def test_lo_snake_js_non_chiama_funzioni_che_non_esiste(client):
    """Stesso controllo fatto su `app.js`, ma sul file del gioco: un riferimento
    a una funzione rimossa e' un `ReferenceError` a runtime, non un errore di
    sintassi, e non si vede finche' quella riga non viene raggiunta.

    I due file sono script classici e **condividono lo scope**: `snake.js` puo'
    chiamare `suonoAttivo`, definita in `app.js`, perche' quando il gioco gira
    l'altro file e' gia' caricato. Quindi si controlla l'unione dei due, non
    `snake.js` da solo."""
    js = _snake_js(client)
    app_js = client.get("/static/app.js").get_data(as_text=True)
    orfane = _nomi_chiamati_senza_definizione(app_js + "\n" + js)
    assert not orfane, "il gioco chiama funzioni che non esistono: " + ", ".join(orfane)

def test_il_gioco_e_nella_scocca_e_versionato(client):
    """`snake.js` va salvato dal service worker (il gioco funziona anche senza
    rete) e va versionato come `app.js`: senza la versione, il browser terrebbe
    la copia vecchia dopo un aggiornamento."""
    sw = client.get("/static/sw.js").get_data(as_text=True)
    assert "/static/snake.js" in sw, "il gioco deve stare nella scocca"
    assert "maggiordomo-scocca-v12" in sw, "alzare la versione sfratta le copie vecchie"
    html = client.get("/").get_data(as_text=True)
    import re
    assert re.search(r'/static/snake\.js\?v=', html), "manca la versione nell'indirizzo"
