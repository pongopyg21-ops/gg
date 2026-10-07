"""Progetti e attivita' da fare.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_progetto_si_crea_con_tutti_i_campi(client):
    r = client.post("/api/projects", json={
        "title": "Sistemare il garage", "description": "Liberare l'angolo",
        "start_date": "2026-09-01", "end_date": "2026-09-30", "priority": 5,
    })
    assert r.status_code == 201
    p = r.get_json()
    assert p["title"] == "Sistemare il garage"
    assert p["priority"] == 5
    assert p["done"] is False

def test_progetto_senza_titolo_rifiutato(client):
    assert client.post("/api/projects", json={"description": "x"}).status_code == 400

def test_progetto_priorita_fuori_scala_rifiutata(client):
    assert client.post("/api/projects", json={"title": "X", "priority": 6}).status_code == 400
    assert client.post("/api/projects", json={"title": "X", "priority": 0}).status_code == 400

def test_progetto_fine_prima_dell_inizio_rifiutata(client):
    r = client.post("/api/projects", json={
        "title": "X", "start_date": "2026-09-30", "end_date": "2026-09-01"})
    assert r.status_code == 400

def test_progetto_si_conclude_e_si_riapre(client):
    pid = client.post("/api/projects", json={"title": "X", "priority": 3}).get_json()["id"]
    assert client.put(f"/api/projects/{pid}", json={"done": True}).get_json()["done"] is True
    assert client.put(f"/api/projects/{pid}", json={"done": False}).get_json()["done"] is False

def test_concludere_un_progetto_non_ne_cancella_i_campi(client):
    """Spuntare "concluso" non deve richiedere di rimandare tutto il resto."""
    pid = client.post("/api/projects", json={
        "title": "X", "description": "Nota", "priority": 4}).get_json()["id"]
    client.put(f"/api/projects/{pid}", json={"done": True})
    p = client.get("/api/projects").get_json()[0]
    assert p["description"] == "Nota" and p["priority"] == 4

def test_progetti_ordinati_per_priorita(client):
    for t, p in (("Bassa", 1), ("Alta", 5), ("Media", 3)):
        client.post("/api/projects", json={"title": t, "priority": p})
    assert [p["title"] for p in client.get("/api/projects").get_json()] == ["Alta", "Media", "Bassa"]

def test_progetti_conclusi_in_fondo(client):
    a = client.post("/api/projects", json={"title": "A", "priority": 5}).get_json()["id"]
    client.post("/api/projects", json={"title": "B", "priority": 1})
    client.put(f"/api/projects/{a}", json={"done": True})
    assert [p["title"] for p in client.get("/api/projects").get_json()] == ["B", "A"]

def test_progetto_eliminato(client):
    pid = client.post("/api/projects", json={"title": "X"}).get_json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert client.get("/api/projects").get_json() == []

def test_progetto_inesistente_da_404(client):
    assert client.put("/api/projects/999", json={"title": "X"}).status_code == 404
    assert client.delete("/api/projects/999").status_code == 404

def test_progetto_priorita_predefinita_tre(client):
    assert client.post("/api/projects", json={"title": "X"}).get_json()["priority"] == 3
