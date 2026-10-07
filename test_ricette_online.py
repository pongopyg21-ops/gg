"""Ricette cercate su un sito esterno.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_dividi_ingrediente_toglie_le_dosi_in_fondo():
    assert ricette_online.dividi_ingrediente("Spaghetti 320 g") == ("Spaghetti", 320.0, "g")
    assert ricette_online.dividi_ingrediente("Tuorli 6") == ("Tuorli", 6.0, "pz")

def test_dividi_ingrediente_ignora_note_e_quantita_a_sentimento():
    # la nota fra parentesi spiega il prodotto, non e' parte del nome; "q.b." non
    # e' una dose: inventarne una falserebbe la dispensa, quindi resta a zero
    assert ricette_online.dividi_ingrediente("Guanciale (stagionato) 200 g") == ("Guanciale", 200.0, "g")
    nome, quantita, _ = ricette_online.dividi_ingrediente("Sale q.b.")
    assert nome == "Sale" and quantita == 0

def test_minuti_da_durata_iso():
    assert ricette_online._minuti("PT25M") == 25
    assert ricette_online._minuti("PT1H20M") == 80
    assert ricette_online._minuti(None) is None

def test_importa_legge_la_ricetta_dal_dato_strutturato(monkeypatch):
    url = "https://ricette.giallozafferano.it/Spaghetti-alla-Carbonara.html"
    finta_rete(monkeypatch, {url: pagina_ricetta()})
    d = ricette_online.importa(url)
    assert d["name"] == "Spaghetti alla Carbonara"
    assert d["servings"] == 4
    assert d["time_minutes"] == 25
    assert [i["name"] for i in d["items"]] == ["Spaghetti", "Guanciale", "Tuorli"]
    assert "Rosolate il guanciale" in d["instructions"]
    # la fonte resta scritta: e' l'unica cosa che rende lecito tenere il testo altrui
    assert "GialloZafferano" in d["source"] and url in d["source"]

def test_importa_non_salva_niente(monkeypatch, client):
    # la ricetta importata si ferma sulla soglia: entra in archivio solo se
    # l'utente la salva dal modulo, mai per il solo fatto di averla letta
    url = "https://ricette.giallozafferano.it/Spaghetti-alla-Carbonara.html"
    finta_rete(monkeypatch, {url: pagina_ricetta(nome="Ricetta Mai Salvata")})
    assert client.get(f"/api/ricette/importa?url={url}").status_code == 200
    elenco = client.get("/api/recipes").get_json()
    assert all(r["name"] != "Ricetta Mai Salvata" for r in elenco)

def test_importa_ricetta_illeggibile_lo_dice(monkeypatch, client):
    url = "https://ricette.giallozafferano.it/vuota.html"
    finta_rete(monkeypatch, {url: "<html><body>niente ricetta qui</body></html>"})
    r = client.get(f"/api/ricette/importa?url={url}")
    assert r.status_code == 502
    assert "non contiene una ricetta leggibile" in r.get_json()["error"]

def test_importa_rifiuta_indirizzi_di_altri_siti():
    # non e' una difesa contro attacchi: e' che il modulo sa leggere *un* sito, e
    # mandarlo altrove e' un errore da dire subito, non da far fallire dopo
    with pytest.raises(ricette_online.NonDisponibile):
        ricette_online.importa("https://esempio.invalid/ricetta.html")

def test_importa_rispetta_i_divieti_del_robots(monkeypatch):
    url = "https://ricette.giallozafferano.it/vietata.html"
    finta_rete(monkeypatch, {url: pagina_ricetta()}, permesso=False)
    with pytest.raises(ricette_online.NonDisponibile):
        ricette_online.importa(url)

def test_il_robots_non_vieta_tutto_per_un_403_dello_scaricatore(monkeypatch):
    """Il robots.txt risponde 403 allo UA di `urllib`, non al nostro.

    `RobotFileParser.read()` scarica con "Python-urllib/...", che questo sito
    respinge; un 403 significa "vietato" e il parser lo leggeva come "vietato a
    tutti". Il risultato era che *nessuna* pagina risultava permessa. Il test
    fissa il comportamento: lo UA di default viene rifiutato, il nostro no, e la
    pagina consentita dal file deve risultare leggibile.
    """
    robot = "User-agent: *\nDisallow: /vietata/\n"
    monkeypatch.setattr(ricette_online, "_apri", lambda url: robot)
    # la pagina di ricerca non e' vietata dal file: deve risultare leggibile
    assert ricette_online._permesso("https://www.giallozafferano.it/ricerca-ricette/carbonara/") is True
    assert ricette_online._permesso("https://www.giallozafferano.it/vietata/pagina/") is False

    def apri(url):
        raise ricette_online.NonDisponibile("403 con lo UA sbagliato")

    # se il robots.txt non si legge si procede: non poterlo leggere non e' un divieto
    monkeypatch.setattr(ricette_online, "_apri", apri)
    assert ricette_online._permesso("https://ricette.giallozafferano.it/Spaghetti.html") is True

def test_cerca_legge_i_collegamenti_alle_ricette(monkeypatch):
    pagina = ('<html><body>'
              '<a href="https://ricette.giallozafferano.it/Carbonara.html" title="Carbonara">x</a>'
              '<a href="https://ricette.giallozafferano.it/Carbonara-di-mare.html" title="Carbonara di mare">y</a>'
              '<a href="https://ricette.giallozafferano.it/Carbonara.html" title="Carbonara">ripetuta</a>'
              '<a href="https://www.giallozafferano.it/altro.html">non una ricetta</a>'
              '</body></html>')
    finta_rete(monkeypatch, {"https://www.giallozafferano.it/ricerca-ricette/carbonara/": pagina})
    trovate = ricette_online.cerca("carbonara")
    assert [r["titolo"] for r in trovate] == ["Carbonara", "Carbonara di mare"]

def test_cerca_una_parola_vuota_non_chiede_niente_alla_rete(monkeypatch):
    monkeypatch.setattr(ricette_online, "_apri",
                        lambda url: pytest.fail("la rete non va interrogata senza testo"))
    assert ricette_online.cerca("   ") == []

def test_endpoint_della_ricerca_risponde_col_risultato(monkeypatch, client):
    pagina = '<a href="https://ricette.giallozafferano.it/Carbonara.html" title="Carbonara">x</a>'
    finta_rete(monkeypatch, {"https://www.giallozafferano.it/ricerca-ricette/carbonara/": pagina})
    r = client.get("/api/ricette/cerca?q=carbonara")
    assert r.status_code == 200
    d = r.get_json()
    assert d["sito"] == "GialloZafferano"
    assert d["risultati"][0]["titolo"] == "Carbonara"

def test_endpoint_della_ricerca_spiega_quando_il_sito_non_risponde(monkeypatch, client):
    finta_rete(monkeypatch, {})   # nessun indirizzo previsto: la lettura fallisce
    r = client.get("/api/ricette/cerca?q=carbonara")
    assert r.status_code == 502
    assert r.get_json()["error"]

def test_endpoint_della_ricerca_senza_testo_non_esce_dal_server(client):
    r = client.get("/api/ricette/cerca?q=")
    assert r.status_code == 400

def test_fonte_di_una_ricetta_importata_si_salva_senza_foto(client):
    """Una ricetta presa da un sito non ha foto ma ha una fonte da citare.

    Legare la fonte alla foto la faceva sparire al salvataggio: la ricetta
    entrava in archivio senza dire da dove veniva.
    """
    ric = crea_ricetta(client, source="GialloZafferano — https://esempio/ricetta")
    letto = client.get(f"/api/recipes/{ric['id']}").get_json()
    assert letto["source"] == "GialloZafferano — https://esempio/ricetta"
    assert letto["image"] == ""

def test_salvataggio_parziale_non_cancella_la_fonte(client):
    ric = crea_ricetta(client, source="Fonte originale")
    risposta = client.put(f"/api/recipes/{ric['id']}", json={
        "name": "Nome cambiato", "servings": 3, "instructions": "", "items": ric["items"]})
    assert risposta.get_json()["source"] == "Fonte originale"
