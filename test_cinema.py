"""Cinema: film del momento, notevoli e preferiti.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_avvio_avvisa_se_la_chiave_del_cinema_manca():
    """La sezione Cinema diceva "Cinema non ancora acceso" quando il server era
    partito **senza** `TMDB_API_KEY` nel suo ambiente: la chiave era registrata
    fra i segreti, ma il nome esatto non compariva nel comando di avvio, quindi
    il sistema non l'aveva iniettata. Sembrava un guasto dell'app.

    Stessa lezione della voce: l'avvio deve dire se la chiave c'e' stata letta.
    Si esegue lo script due volte, con e senza la variabile, e si guarda il
    messaggio."""
    import os
    import subprocess

    senza = dict(os.environ)
    senza.pop("TMDB_API_KEY", None)
    esito = subprocess.run(["./avvia.sh", "status"], cwd=BASE_APP,
                           env=senza, capture_output=True, text=True)
    uscita = esito.stdout + esito.stderr
    assert "cinema: spento" in uscita, uscita
    assert "TMDB_API_KEY" in uscita, uscita

    con = dict(os.environ)
    con["TMDB_API_KEY"] = "a" * 32
    esito = subprocess.run(["./avvia.sh", "status"], cwd=BASE_APP,
                           env=con, capture_output=True, text=True)
    uscita = esito.stdout + esito.stderr
    assert "cinema: chiave TMDB attiva" in uscita, uscita

def test_il_tetto_della_voce_non_lascia_muti_per_venti_secondi(client):
    """Il difetto riferito: dopo il "Si." l'assistente torna muto e non trascrive
    i comandi. La causa e' il tetto dell'attesa di "fine parlato": se la sintesi
    non annuncia la fine (succede), la pausa durava fino a 20 s **fissi**, e in
    quei venti secondi il microfono resta chiuso.

    Si esegue `tettoVoceMs` **vera**: il tetto dev'essere proporzionale alla
    frase, cosi' una parola come "Si." non fa aspettare venti secondi."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "tettoVoceMs")
    d = _esegui_node(blocco + """
console.log(JSON.stringify({
  si: tettoVoceMs('Si.'),
  comandi: tettoVoceMs('Comandi.'),
  lunga: tettoVoceMs('Fatto. Farina in dispensa, 2 kg.'),
}));""")
    # una parola breve: pochi secondi, non venti
    assert d["si"] <= 3000, d
    assert d["comandi"] <= 3500, d
    # una conferma lunga ha piu' tempo, ma sempre sotto il vecchio tetto fisso
    assert d["lunga"] > d["si"]
    assert d["lunga"] <= 12000

def test_il_cinema_vive_dentro_la_sezione_tv(client):
    """Il Cinema non e' piu' una sezione a se': e' intrattenimento come i video
    e le notizie, quindi sta **dentro** la sezione TV. Niente scheda in home,
    niente scheda nella barra: una scheda in piu' per la stessa cosa era un
    doppione. Il carosello e i suoi comandi restano, e `renderCinema` parte
    aprendo la scheda TV."""
    html = client.get("/static/index.html").get_data(as_text=True)
    # dentro la sezione TV, non in una sua
    assert 'id="tab-intrattenimento"' in html
    assert html.index('id="tab-intrattenimento"') < html.index('id="cinema-carosello"')
    assert html.index('id="cinema-carosello"') < html.index('id="tab-gym"')
    # il carosello e i suoi comandi
    assert 'id="cinema-carosello"' in html
    assert 'id="cinema-prima"' in html and 'id="cinema-dopo"' in html
    assert 'id="cinema-punti"' in html
    assert 'id="cinema-vista-preferiti"' in html
    assert 'id="cinema-griglia"' in html
    # niente piu' sezione/tab/scheda dedicata
    assert 'id="tab-cinema"' not in html
    assert 'data-tab="cinema"' not in html
    assert 'data-section="cinema"' not in html
    # nessun id duplicato: era proprio il doppione a rompere la vista Preferiti
    ids = re.findall(r'id="([^"]+)"', html)
    assert len(ids) == len(set(ids)), "id duplicati in index.html"
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function renderCinema" in js
    assert "/api/cinema" in js
    # renderCinema si chiama aprendo la scheda TV, insieme a renderTv
    assert "renderTv(); renderCinema();" in js
    assert "cinema:   { titolo:" not in js and "cinema: { titolo:" not in js

def test_la_vista_preferiti_ha_id_distinti(client):
    """La vista «Preferiti» era invisibile: il contenitore aveva lo stesso id del
    pulsante `#cinema-vista-preferiti`, e `$()` prende il primo (il pulsante).
    `classList.toggle('hidden', false)` finiva sul pulsante, non sul contenitore,
    che restava `hidden` e misurava 0x0 — la griglia c'era ma non si vedeva.

    La regressione si tiene in modo strutturale: gli id sono unici, e il
    contenitore della vista ha un id suo."""
    html = client.get("/static/index.html").get_data(as_text=True)
    ids = re.findall(r'id="([^"]+)"', html)
    assert len(ids) == len(set(ids)), "id duplicati in index.html"
    assert html.count('id="cinema-vista-preferiti"') == 1
    assert 'id="cinema-pannello-preferiti"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "$('#cinema-pannello-preferiti').classList.toggle('hidden', ora)" in js

def test_il_cinema_ha_il_pulsante_elimina_e_il_ripristino(client):
    """Eliminare un titolo che non piace: il pulsante sta accanto alla stella, e
    la riga dei film eliminati dice che l'eliminazione non e' definitiva e
    offre di rimetterli. Senza, nessuno oserebbe toccare niente."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="cinema-elimina"' in html
    assert 'id="cinema-nascosti"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function cinemaElimina" in js
    assert "function cinemaRipristina" in js
    assert "'/api/cinema/nascondi'" in js
    assert "'/api/cinema/ripristina'" in js
    assert "function disegnaNascosti" in js

def test_il_cinema_si_sfoglia_da_destra_a_sinistra(client):
    """Sfogliare e' la richiesta: frecce, tastiera, rotellina e dito. Se una
    delle quattro sparisce, su un telefono o senza mouse il carosello si blocca."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function cinemaVai" in js
    assert "cinemaIndice" in js
    # il dito: `touchstart` + `touchend`, col gesto orizzontale
    assert "'touchstart'" in js and "'touchend'" in js
    # la rotellina e la tastiera
    assert "'wheel'" in js and "ArrowRight" in js and "ArrowLeft" in js
    # lo scorrimento e' ciclico: si torna al primo dopo l'ultimo
    assert "% cinemaFilm.length" in js

def test_senza_chiave_il_cinema_non_e_un_guasto(client, monkeypatch):
    """Senza `TMDB_API_KEY` la sezione e' spenta, non rotta: 200 con un elenco
    vuoto e la spiegazione di cosa manca."""
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})  # non rileggere i file
    d = client.get("/api/cinema").get_json()
    assert d["film"] == []
    assert d["configurato"] is False
    assert "TMDB_API_KEY" in d["manca"]
    # anche il pulsante lo dice, e non tenta la rete
    r = client.post("/api/cinema/aggiorna")
    assert r.status_code == 400
    assert "TMDB_API_KEY" in r.get_json()["error"]

def test_la_chiave_tmdb_si_legge_dall_ambiente(monkeypatch):
    """La chiave viene dall'ambiente, e la sezione risulta configurata."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    assert cinema.configurato() is True
    assert cinema.messaggio_stato() == ""
    assert cinema.chiave() == "0123456789abcdef0123456789abcdef"

def test_la_regione_del_cinema_e_l_italia_per_predefinito(monkeypatch):
    """La regione decide quali piattaforme compaiono: il predefinito e' l'Italia,
    e si puo' cambiare."""
    monkeypatch.delenv("CINEMA_REGION", raising=False)
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    assert cinema.regione() == "IT"
    monkeypatch.setenv("CINEMA_REGION", "us")
    assert cinema.regione() == "US"

def test_i_film_si_leggono_e_si_schedano(monkeypatch):
    """Una risposta di TMDB diventa schede con solo i campi che si mostrano, e
    un film senza locandina si scarta: e' una sezione di immagini.

    I fornitori e le traduzioni si chiedono insieme, film per film, sul
    dettaglio: `discover` non allega ne' gli uni ne' le altre.
    """
    scoperta = {
        "results": [
            {"id": 1, "title": "Film Bello", "release_date": "2024-05-01",
             "vote_average": 8.234, "vote_count": 1200, "overview": "Una trama.",
             "poster_path": "/abc.jpg"},
            {"id": 2, "title": "Senza locandina", "poster_path": "",
             "vote_average": 7.0},
        ]
    }
    fornitori = {"results": {"IT": {"flatrate": [
        {"provider_name": "Netflix"}, {"provider_name": "Prime Video"}]}}}

    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri",
                        _apri_tmdb(principale=scoperta, piattaforme=fornitori))
    film = cinema._scarica(None)
    assert len(film) == 1
    scheda = film[0]
    assert scheda["titolo"] == "Film Bello"
    assert scheda["anno"] == "2024"
    assert scheda["voto"] == 8.2
    assert scheda["locandina"].endswith("/abc.jpg")
    assert scheda["piattaforme"] == ["Netflix", "Prime Video"]

def test_un_film_resta_anche_se_i_dettagli_non_rispondono(monkeypatch):
    """Le piattaforme sono un di piu': se il dettaglio fallisce il film resta,
    senza le piattaforme. E anche il dubbio sulla lingua non lo scarta: un film
    buono non si perde perche' la rete non ha risposto (vedi `_dettagli`)."""
    scoperta = {"results": [
        {"id": 1, "title": "Film Bello", "release_date": "2024-05-01",
         "vote_average": 8.0, "poster_path": "/abc.jpg"},
    ]}

    def finta(url):
        if "/discover/movie" in url:
            return json.dumps(scoperta).encode()
        raise cinema.NonDisponibile("dettaglio giu'")

    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri", finta)
    film = cinema._scarica(None)
    assert [f["titolo"] for f in film] == ["Film Bello"]
    assert film[0]["piattaforme"] == []

def test_la_scoperta_esclude_azione_e_marvel(monkeypatch):
    """Azione, film per bambini/ragazzi e film Marvel restano fuori dal giro:
    l'azione e i cinecomic sono i piu' popolari e da soli coprirebbero tutto il
    resto, mentre i film per bambini non sono quello che si cerca per una
    serata. Si escludono per genere e per casa, non per titolo."""
    visti = []

    def finta(url):
        visti.append(url)
        if "/watch/providers" in url:
            return json.dumps({}).encode()
        return json.dumps({"results": []}).encode()

    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri", finta)
    cinema._scarica(None)
    scoperte = [u for u in visti if "/discover/movie" in u]
    assert scoperte
    for url in scoperte:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        # azione + animazione + famiglia, in un unico parametro
        assert q.get("without_genres") == [f"{cinema.GENERI_ESCLUSI},{cinema.GENERI_BAMBINI}"]
        assert q.get("without_companies") == [cinema.CASE_ESCLUSE]
        assert "28" in cinema.GENERI_ESCLUSI
        # 16 = Animazione, 10751 = Famiglia: i film destinati a bambini e ragazzi
        assert "16" in cinema.GENERI_BAMBINI
        assert "10751" in cinema.GENERI_BAMBINI
        assert "420" in cinema.CASE_ESCLUSE

def test_la_scoperta_mette_un_tetto_ai_voti(monkeypatch):
    """I blockbuster escono dal giro: il segno che un film "l'ha visto tutti"
    non e' il voto ma **quanti** voti ha. Senza tetto, Interstellar (41k voti) e
    Blade Runner 2049 (16k) restano fra i piu' popolari per anni e occupano il
    carosello. La finestra sui voti e' quello che li toglie, senza una lista di
    titoli da aggiornare a mano."""
    visti = []

    def finta(url):
        visti.append(url)
        if "/watch/providers" in url:
            return json.dumps({}).encode()
        return json.dumps({"results": []}).encode()

    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri", finta)
    cinema._scarica(None)
    principali = [u for u in visti
                  if "/discover/movie" in u and "with_keywords" not in u]
    assert principali
    q = urllib.parse.parse_qs(urllib.parse.urlparse(principali[0]).query)
    assert q.get("vote_count.gte") == [str(cinema.VOTI_MIN)]
    assert q.get("vote_count.lte") == [str(cinema.VOTI_MAX)]
    assert q.get("vote_average.gte") == [str(cinema.VOTO_MIN)]
    # il tetto e' l'ordine di grandezza di un film "visto da tutti", non un
    # numero che taglierebbe anche i film normali
    assert cinema.VOTI_MAX <= 10000

def test_i_film_di_nicchia_si_cercano_per_tag_e_si_accodano(monkeypatch):
    """La nicchia si cerca per **tag** (cinema indipendente, d'autore, cult,
    commedia nera, surrealismo): un film nuovo che porta quel tag entra da solo,
    come per generi e case. Si accoda ai film del momento, con lo stesso tetto
    ai voti, e un film non compare due volte."""
    principale = {"results": [
        {"id": 1, "title": "Del Momento", "release_date": "2026-01-01",
         "vote_average": 7.5, "poster_path": "/a.jpg"},
    ]}
    nicchia = {"results": [
        {"id": 1, "title": "Del Momento", "release_date": "2026-01-01",
         "vote_average": 7.5, "poster_path": "/a.jpg"},
        {"id": 2, "title": "Fuori Dal Coro", "release_date": "2004-01-01",
         "vote_average": 8.0, "poster_path": "/b.jpg"},
    ]}
    visti = []
    base = _apri_tmdb(principale=principale, nicchia=nicchia)

    def finta(url):
        visti.append(url)
        return base(url)

    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri", finta)
    film = cinema._scarica(None)
    assert [f["titolo"] for f in film] == ["Del Momento", "Fuori Dal Coro"]

    nicchia_url = next(u for u in visti
                       if "/discover/movie" in u and "with_keywords" in u)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(nicchia_url).query)
    assert q.get("with_keywords") == ["|".join(cinema.PAROLE_NICCHIA)]
    assert q.get("vote_count.lte") == [str(cinema.VOTI_NICCHIA_MAX)]
    assert q.get("vote_count.gte") == [str(cinema.VOTI_NICCHIA_MIN)]
    assert q.get("sort_by") == ["vote_average.desc"]
    # i tag sono id numerici di TMDB, non nomi: un nome verrebbe ignorato
    assert all(k.isdigit() for k in cinema.PAROLE_NICCHIA)

def test_i_preferiti_si_segnano_e_si_tolgono(client, monkeypatch):
    """La stella segna un film; `preferiti` lo ritrova, e la risposta lo dice
    sia come elenco a parte sia come flag sul film."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    risposta = {"results": [
        {"id": 9, "title": "Da Preferire", "release_date": "2022-09-09",
         "vote_average": 6.8, "poster_path": "/y.jpg", "overview": "Trama."},
    ]}
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb(principale=risposta))
    cinema.aggiorna(app_module.get_db(), forse=False)

    d = client.get("/api/cinema").get_json()
    assert d["film"][0]["preferito"] is False and d["preferiti"] == []

    d = client.post("/api/cinema/preferiti", json={"id": 9, "preferito": True}).get_json()
    assert d["film"][0]["preferito"] is True
    assert [f["id"] for f in d["preferiti"]] == [9]
    assert d["preferiti_ids"] == [9]

    d = client.post("/api/cinema/preferiti", json={"id": 9, "preferito": False}).get_json()
    assert d["film"][0]["preferito"] is False and d["preferiti"] == []

def test_un_preferito_resta_anche_se_esce_dal_giro(client, monkeypatch):
    """La scheda del preferito e' salvata intera: se il film sparisce dai film
    del momento, il preferito resta (con locandina e titolo)."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    prima = {"results": [
        {"id": 42, "title": "Sparirà", "release_date": "2020-01-01",
         "vote_average": 7.9, "poster_path": "/s.jpg", "overview": "Trama."},
    ]}
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb(principale=prima))
    with app_module.app.app_context():
        cinema.aggiorna(app_module.get_db(), forse=False)
    client.post("/api/cinema/preferiti", json={"id": 42, "preferito": True})

    # il giro dopo il film non c'e' piu': il preferito resta
    dopo = {"results": [
        {"id": 7, "title": "Nuovo", "release_date": "2026-01-01",
         "vote_average": 7.0, "poster_path": "/n.jpg", "overview": ""},
    ]}
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb(principale=dopo))
    with app_module.app.app_context():
        cinema.aggiorna(app_module.get_db(), forse=False)
    d = client.get("/api/cinema").get_json()
    assert [f["id"] for f in d["film"]] == [7]
    assert [f["titolo"] for f in d["preferiti"]] == ["Sparirà"]
    assert d["preferiti"][0]["locandina"].endswith("/s.jpg")

def test_il_preferito_di_un_film_non_mostrato_non_si_segna(client, monkeypatch):
    """Non si segna un film che non e' fra quelli mostrati: senza la sua scheda
    il preferito sarebbe una locandina vuota."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    r = client.post("/api/cinema/preferiti", json={"id": 999999, "preferito": True})
    assert r.status_code == 400
    assert client.get("/api/cinema").get_json()["preferiti"] == []

def test_eliminare_un_film_ne_carica_subito_uno_nuovo(client, monkeypatch):
    """Eliminando un titolo la sezione non si accorcia: il server ne accoda
    subito uno nuovo. Pescando da una pagina **diversa**, il film appena tolto
    non torna e il rimpiazzo e' davvero nuovo."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb_a_pagine({
        1: [_film(1, "Primo")],
        2: [_film(2, "Secondo")],
    }))
    cinema.aggiorna(app_module.get_db(), forse=False)
    assert [f["titolo"] for f in cinema.film(app_module.get_db())] == ["Primo"]

    d = client.post("/api/cinema/nascondi", json={"id": 1}).get_json()
    titoli = [f["titolo"] for f in d["film"]]
    assert "Primo" not in titoli, "il film eliminato non deve restare"
    assert "Secondo" in titoli, "il server deve aver accodato un film nuovo"
    assert d["nascosti"] == [1]

def test_il_rimpiazzo_non_ripesca_i_gia_mostrati(client, monkeypatch):
    """Se la pagina nuova riporta un film che c'e' gia', si salta: la copia non
    deve riempirsi di doppioni."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb_a_pagine({
        1: [_film(1, "Primo")],
        # la pagina 2 riporta lo stesso film, poi uno nuovo
        2: [_film(1, "Primo"), _film(2, "Secondo")],
    }))
    cinema.aggiorna(app_module.get_db(), forse=False)
    d = client.post("/api/cinema/nascondi", json={"id": 1}).get_json()
    ids = [f["id"] for f in d["film"]]
    assert ids.count(1) == 0
    assert ids == [2]

def test_il_rimpiazzo_non_esce_dal_tetto_delle_pagine(monkeypatch):
    """Se ogni pagina porta solo film gia' visti, `sostituisci` si ferma al
    tetto invece di girare all'infinito: ogni pagina sono chiamate di dettaglio."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    pagine = []

    def apri(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "/discover/movie" in url and "with_keywords" not in q:
            pagine.append(int(q.get("page", ["1"])[0]))
            return json.dumps({"results": [_film(1, "Sempre lo stesso")]}).encode()
        if re.search(r"/movie/\d+", url):
            return json.dumps({"translations": {"translations": [{"iso_639_1": "it"}]},
                               "watch/providers": {}}).encode()
        return json.dumps({"results": []}).encode()

    monkeypatch.setattr(cinema, "_apri", apri)
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE tv_cache (chiave TEXT PRIMARY KEY, dati TEXT, aggiornato REAL)")
    db.execute("INSERT INTO tv_cache (chiave, dati, aggiornato) VALUES ('cinema', ?, 0)",
               (json.dumps([_film(1, "Sempre lo stesso")]),))
    assert cinema.sostituisci(db) == []
    # si e' fermato: nessuna pagina oltre il tetto
    assert pagine and max(pagine) <= cinema.RIMPIAZZI_MASSIMI

def test_i_film_si_mettono_in_cache_e_si_rileggono(client, monkeypatch):
    """La copia vive in `tv_cache` (chiave `cinema`): la sezione si apre con quello che c'e',
    anche senza rete, e `aggiorna` non riscarica se la copia e' fresca."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    risposta = {"results": [
        {"id": 7, "title": "Rimasto", "release_date": "2023-01-01",
         "vote_average": 7.5, "poster_path": "/x.jpg", "overview": ""},
    ]}
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb(principale=risposta))
    db = app_module.get_db()
    assert cinema.aggiorna(db, forse=False) is True
    assert [f["titolo"] for f in cinema.film(db)] == ["Rimasto"]
    # copia fresca: `forse=True` non riscarica (e `_apri` nemmeno verrebbe chiamato)
    assert cinema.aggiorna(db, forse=True) is False

def test_l_endpoint_cinema_serve_la_copia_e_gli_incorpora(client, monkeypatch):
    """`/api/cinema` serve la copia senza aspettare la rete, e ogni film porta
    locandina e piattaforme."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    risposta = {"results": [
        {"id": 9, "title": "In Cache", "release_date": "2022-09-09",
         "vote_average": 6.8, "poster_path": "/y.jpg", "overview": "Trama."},
    ]}
    fornitori = {"results": {"IT": {"flatrate": [{"provider_name": "Disney+"}]}}}

    monkeypatch.setattr(cinema, "_apri",
                        _apri_tmdb(principale=risposta, piattaforme=fornitori))
    cinema.aggiorna(app_module.get_db(), forse=False)
    d = client.get("/api/cinema").get_json()
    assert d["configurato"] is True and d["manca"] == ""
    assert len(d["film"]) == 1
    assert d["film"][0]["locandina"].endswith("/y.jpg")
    assert d["film"][0]["piattaforme"] == ["Disney+"]
    assert d["aggiornato"]

def test_senza_rete_il_cinema_resta_con_la_copia_vecchia(client, monkeypatch):
    """Un guasto di rete non deve svuotare la sezione: si tiene l'ultima copia."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    risposta = {"results": [
        {"id": 3, "title": "Gia' scaricato", "release_date": "2021-01-01",
         "vote_average": 7.0, "poster_path": "/z.jpg", "overview": ""},
    ]}
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb(principale=risposta))
    db = app_module.get_db()
    cinema.aggiorna(db, forse=False)
    # ora la rete e' giu': l'aggiornamento non porta niente, ma la copia resta
    monkeypatch.setattr(cinema, "_apri",
                        lambda url: (_ for _ in ()).throw(cinema.NonDisponibile("giu")))
    assert cinema.aggiorna(db, forse=False) is False
    assert [f["titolo"] for f in cinema.film(db)] == ["Gia' scaricato"]

def test_la_chiave_tmdb_non_compare_nella_risposta(client, monkeypatch):
    """La chiave resta del server: non si espone nella risposta, in nessuna forma."""
    segreta = "deadbeefdeadbeefdeadbeefdeadbeef"
    monkeypatch.setenv("TMDB_API_KEY", segreta)
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    testo = client.get("/api/cinema").get_data(as_text=True)
    assert segreta not in testo
    assert "api_key" not in testo

def test_l_aggiornamento_in_sottofondo_del_cinema_non_esplode(client, monkeypatch):
    """Il filo di sottofondo e' un percorso che l'utente non vede: se solleva,
    la sezione risponde 500 invece di aprirsi. Qui si controlla che parta e
    finisca, con la copia vecchia (nessuna rete)."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    chiamate = []
    monkeypatch.setattr(cinema, "aggiorna", lambda db, forse=True: chiamate.append(forse))
    db = app_module.get_db()
    app_module._aggiorna_cinema_in_sottofondo(db)  # copia assente: parte il filo
    for _ in range(50):
        if chiamate:
            break
        time.sleep(0.05)
    assert chiamate == [True]
    # e l'endpoint, senza stub, non risponde 500 con la chiave finta
    monkeypatch.setattr(cinema, "_apri",
                        lambda url: (_ for _ in ()).throw(cinema.NonDisponibile("finta")))
    assert client.get("/api/cinema").status_code == 200

def test_i_film_senza_versione_italiana_si_scartano(monkeypatch):
    """Un film che non ha una **traduzione italiana** non entra in sezione: la
    serata in casa deve poter essere guardata. E' il segnale `translations` di
    TMDB, non la lingua originale: i film stranieri doppiati (Match Point) hanno
    la traduzione `it` e restano, un film che non e' mai arrivato qui no."""
    principale = {"results": [
        {"id": 1, "title": "Doppiato", "release_date": "2024-01-01",
         "vote_average": 7.5, "poster_path": "/a.jpg"},
        {"id": 2, "title": "Mai Arrivato", "release_date": "2024-01-01",
         "vote_average": 7.6, "poster_path": "/b.jpg"},
    ]}
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri",
                        _apri_tmdb(principale=principale, senza_it=(2,)))
    film = cinema._scarica(None)
    assert [f["titolo"] for f in film] == ["Doppiato"]

def test_i_film_sulla_scia_dei_capisaldi_si_accodano(monkeypatch):
    """I film "sulla scia" vengono dalle **raccomandazioni** dei capisaldi
    (`cinema.SCIA`), non da una lista scritta a mano: si accodano ai film del
    momento senza doppioni. I generi che la scia non vuole (azione, bambini,
    documentari, musicali) restano fuori."""
    principale = {"results": [
        {"id": 1, "title": "Del Momento", "release_date": "2026-01-01",
         "vote_average": 7.5, "poster_path": "/a.jpg"},
    ]}
    scia = {"results": [
        {"id": 1, "title": "Del Momento", "release_date": "2026-01-01",
         "vote_average": 7.5, "poster_path": "/a.jpg", "genre_ids": [18]},
        {"id": 2, "title": "Sulla Scia", "release_date": "2005-01-01",
         "vote_average": 8.0, "poster_path": "/b.jpg", "genre_ids": [18, 53]},
        {"id": 3, "title": "Documentario", "release_date": "2005-01-01",
         "vote_average": 8.5, "poster_path": "/c.jpg", "genre_ids": [99]},
        {"id": 4, "title": "Azione", "release_date": "2005-01-01",
         "vote_average": 8.0, "poster_path": "/d.jpg", "genre_ids": [28]},
        {"id": 5, "title": "Troppo Poco Visto", "release_date": "2005-01-01",
         "vote_average": 9.0, "vote_count": 5, "poster_path": "/e.jpg",
         "genre_ids": [18]},
    ]}
    # le raccomandazioni portano `vote_count`: il minimo tiene fuori il film 5
    scia["results"][1]["vote_count"] = 3000
    scia["results"][2]["vote_count"] = 3000
    scia["results"][3]["vote_count"] = 3000
    scia["results"][4]["vote_count"] = 5
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb(principale=principale, scia=scia))
    film = cinema._scarica(None)
    assert [f["titolo"] for f in film] == ["Del Momento", "Sulla Scia"]
    # i capisaldi sono id di TMDB, non titoli: un titolo cambia, un id no
    assert all(isinstance(i, int) for i in cinema.SCIA)

def test_la_nicchia_non_soffoca_la_scia(monkeypatch):
    """La scia deve avere i suoi posti anche quando la nicchia ne porta molti.

    Difetto vero: i film del momento (20) piu' la nicchia (fino a 20) riempivano
    da soli il tetto (`QUANTI + QUANTI_NICCHIA + QUANTI_SCIA`), quindi la scia —
    che si accoda per ultima — non entrava **mai**. In produzione la coda era
    tutta nicchia e nessun film "sulla scia" si vedeva. Qui la nicchia porta
    venti film e la scia otto: i film sulla scia devono comparire lo stesso."""
    principale = {"results": [
        {"id": i, "title": f"Momento {i}", "release_date": "2026-01-01",
         "vote_average": 7.5, "poster_path": f"/m{i}.jpg"}
        for i in range(1, 21)
    ]}
    nicchia = {"results": [
        {"id": 100 + i, "title": f"Nicchia {i}", "release_date": "2004-01-01",
         "vote_average": 8.0, "poster_path": f"/n{i}.jpg"}
        for i in range(20)
    ]}
    scia = {"results": [
        {"id": 200 + i, "title": f"Scia {i}", "release_date": "2005-01-01",
         "vote_average": 8.2, "vote_count": 3000, "poster_path": f"/s{i}.jpg",
         "genre_ids": [18]}
        for i in range(cinema.QUANTI_SCIA)
    ]}
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri",
                        _apri_tmdb(principale=principale, nicchia=nicchia, scia=scia))
    film = cinema._scarica(None)
    titoli = [f["titolo"] for f in film]
    assert len(film) == cinema.QUANTI + cinema.QUANTI_NICCHIA + cinema.QUANTI_SCIA
    assert sum(t.startswith("Scia ") for t in titoli) == cinema.QUANTI_SCIA
    # e i film del momento restano tutti, non solo quelli che avanzano
    assert sum(t.startswith("Momento ") for t in titoli) == cinema.QUANTI

def test_la_scia_riempie_i_posti_lasciati_liberi(monkeypatch):
    """Se una sorgente non ha abbastanza film, i posti liberi si riprendono
    dalle altre: l'elenco non resta bucato."""
    principale = {"results": [
        {"id": i, "title": f"Momento {i}", "release_date": "2026-01-01",
         "vote_average": 7.5, "poster_path": f"/m{i}.jpg"}
        for i in range(1, cinema.QUANTI + 1)
    ]}
    nicchia = {"results": []}  # nessun film di nicchia
    # la scia ne ha piu' del suo posto, quindi puo' riempire quelli della nicchia
    scia = {"results": [
        {"id": 200 + i, "title": f"Scia {i}", "release_date": "2005-01-01",
         "vote_average": 8.2, "vote_count": 3000, "poster_path": f"/s{i}.jpg",
         "genre_ids": [18]}
        for i in range(cinema.QUANTI_SCIA + cinema.QUANTI_NICCHIA + 4)
    ]}
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri",
                        _apri_tmdb(principale=principale, nicchia=nicchia, scia=scia))
    film = cinema._scarica(None)
    # i posti della nicchia (vuota) se li prende la scia, che ne ha abbastanza
    assert [f["titolo"] for f in film[:cinema.QUANTI]] == [
        f"Momento {i}" for i in range(1, cinema.QUANTI + 1)]
    assert sum(f["titolo"].startswith("Scia ") for f in film) == \
        cinema.QUANTI_SCIA + cinema.QUANTI_NICCHIA

def test_i_film_eliminati_spariscono_e_si_ripristinano(client, monkeypatch):
    """L'utente puo' togliere un titolo che non gradisce. L'eliminazione e'
    reversibile e non tocca la copia di TMDB: si annota l'id, e `film()` lo
    salta; ripristinare lo rimette senza riscaricare."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    risposta = {"results": [
        {"id": 9, "title": "Da Togliere", "release_date": "2022-09-09",
         "vote_average": 6.8, "poster_path": "/y.jpg", "overview": "Trama."},
        {"id": 10, "title": "Da Tenere", "release_date": "2021-01-01",
         "vote_average": 7.1, "poster_path": "/z.jpg", "overview": ""},
    ]}
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb(principale=risposta))
    cinema.aggiorna(app_module.get_db(), forse=False)

    d = client.post("/api/cinema/nascondi", json={"id": 9}).get_json()
    assert [f["titolo"] for f in d["film"]] == ["Da Tenere"]
    assert d["nascosti"] == [9]
    # la copia di TMDB non e' stata toccata
    assert [f["titolo"] for f in cinema.film(app_module.get_db())] == ["Da Tenere"]

    d = client.post("/api/cinema/ripristina", json={"id": 9}).get_json()
    assert [f["titolo"] for f in d["film"]] == ["Da Togliere", "Da Tenere"]
    assert d["nascosti"] == []

def test_il_ripristino_senza_id_rimette_tutti(client, monkeypatch):
    """`/api/cinema/ripristina` senza `id` rimette in sezione tutti i film
    eliminati: e' il pulsante «Ripristina tutti» della riga dei nascosti."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    risposta = {"results": [
        {"id": 9, "title": "Uno", "release_date": "2022-01-01",
         "vote_average": 6.8, "poster_path": "/a.jpg"},
        {"id": 10, "title": "Due", "release_date": "2021-01-01",
         "vote_average": 7.1, "poster_path": "/b.jpg"},
    ]}
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb(principale=risposta))
    cinema.aggiorna(app_module.get_db(), forse=False)
    client.post("/api/cinema/nascondi", json={"id": 9})
    d = client.post("/api/cinema/nascondi", json={"id": 10}).get_json()
    assert d["film"] == [] and d["nascosti"] == [10, 9]

    d = client.post("/api/cinema/ripristina", json={}).get_json()
    assert sorted(f["id"] for f in d["film"]) == [9, 10]
    assert d["nascosti"] == []

def test_non_si_elimina_un_film_non_mostrato(client, monkeypatch):
    """Non si elimina un film che non e' fra quelli mostrati: sarebbe una riga
    di nascosti per un id che non si e' mai visto, e il pulsante non deve
    poterlo fare."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    r = client.post("/api/cinema/nascondi", json={"id": 999999})
    assert r.status_code == 400
    assert client.get("/api/cinema").get_json()["nascosti"] == []
    # e senza id e' un errore, non un'eliminazione a caso
    assert client.post("/api/cinema/nascondi", json={}).status_code == 400

def test_la_tabella_dei_film_eliminati_arriva_anche_a_un_db_vecchio(monkeypatch):
    """`cinema_nascosti` e' una tabella nuova: la crea lo schema, che `get_db()`
    applica a **ogni** casa. Su un database che non l'aveva deve comparire,
    altrimenti l'eliminazione fallirebbe solo li' (proprio chi ha piu' dati)."""
    path = os.path.join(tempfile.mkdtemp(), "vecchio-cinema.db")
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
            CREATE TABLE cinema_preferiti (
                movie_id INTEGER PRIMARY KEY, dati TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')));
        """)
    app_module.init_db(path)  # quello che fa `get_db()` su ogni casa
    with sqlite3.connect(path) as db:
        nomi = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "cinema_nascosti" in nomi
    app_module.init_db(path)  # rieseguire non deve fallire

def test_il_riquadro_igiene_ha_l_anello_e_la_fascia_di_colore(client):
    """La grafica dell'Igiene: il riquadro «adesso» ha una fascia d'accento e un
    anello che mostra quanto si e' fatto. Sono la parte visibile del lavoro, e
    vanno provati insieme al markup che li disegna."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert 'class="ch-ring"' in js
    assert "ch-hero-main" in js and "ch-hero-meta" in js
    assert "aria-label=" in js and "attività fatte oggi" in js
    css = client.get("/static/style.css").get_data(as_text=True)
    assert ".ch-ring" in css
    assert "conic-gradient" in css, "l'anello si disegna col gradiente conico"
    assert "--pct" in css
    # la riga ha il colore dell'ambiente: raggruppa le voci della stessa zona
    assert '.ch-area[data-area="cucina"]' in css
    assert "areaChiave" in js
