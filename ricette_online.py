"""Ricerca di ricette su un sito esterno, per l'uso personale di chi usa l'app.

Perche' un modulo a parte: la fonte esterna e' l'unico pezzo dell'app che dipende
da un sito che non controlliamo. Cambia la grafica, cambia l'indirizzo, il sito
chiude: tenendo qui lettura e interpretazione, il resto dell'app non se ne accorge
e si sostituisce questa sola parte.

Perche' non si copia la pagina: le ricette sono testo di altri. Si legge il dato
strutturato che il sito pubblica per i motori di ricerca (JSON-LD schema.org
`Recipe`) e si tengono nome, dosi e passi per uso personale, **citando la fonte**
(che finisce nel campo `source` della ricetta). La foto non si scarica:
resta un collegamento sul sito.

Nota sui permessi: prima di leggere si controlla il `robots.txt` del sito e non si
procede se la pagina e' vietata. GialloZafferano vieta esplicitamente gli agenti
di intelligenza artificiale (GPTBot, ClaudeBot, ...): leggerlo per conto
dell'utente non li riguarda, ma e' bene saperlo prima di usarlo.
"""
from __future__ import annotations

import html as _html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

SITO = "GialloZafferano"
RICERCA_URL = "https://www.giallozafferano.it/ricerca-ricette/{q}/"
RICETTA_HOST = "ricette.giallozafferano.it"

# Un identificativo onesto: non ci si spaccia per un browser, cosi' il sito puo'
# riconoscerci e rispondere di conseguenza.
USER_AGENT = "IlMaggiordomo/1.0 (ricette per uso personale)"
TIMEOUT = 15.0

_MAX_RISULTATI = 8


class NonDisponibile(Exception):
    """La ricerca online non ha potuto rispondere: rete, sito o pagina vietata."""


def _apri(url):
    richiesta = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "it-IT,it;q=0.9",
    })
    with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:
        return risposta.read().decode("utf-8", errors="replace")


def _permesso(url):
    """Il robots.txt del sito consente di leggere questa pagina?

    Se il robots.txt non si raggiunge si procede: non poterlo leggere non e' un
    divieto. Se invece si raggiunge e vieta la pagina, ci si ferma — e' la regola
    che il sito ha scritto, e ignorarla sarebbe una scelta, non una distrazione.

    Si scarica il file con il nostro identificativo e si interpreta con `parse()`.
    `read()` non va bene qui: scarica con lo UA di `urllib` ("Python-urllib/..."),
    che questo sito respinge con 403, e `robotparser` legge un 403 come "vieta
    tutto ai non nominati": il risultato era che *nessuna* pagina risultava
    permessa, anche quelle che il sito lascia leggere.
    """
    parti = urllib.parse.urlsplit(url)
    robot = f"{parti.scheme}://{parti.netloc}/robots.txt"
    try:
        testo = _apri(robot)
    except Exception:
        return True
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(testo.splitlines())
    return rp.can_fetch(USER_AGENT, url)


def _blocchi_json_ld(pagina):
    for grezzo in re.findall(
            r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', pagina, re.S | re.I):
        try:
            dati = json.loads(grezzo.strip())
        except (ValueError, TypeError):
            continue
        for voce in (dati if isinstance(dati, list) else [dati]):
            if isinstance(voce, dict):
                yield voce


def _prima(dati, chiave):
    valore = dati.get(chiave)
    if isinstance(valore, list):
        return valore[0] if valore else None
    return valore


def _ricetta_ld(pagina):
    """Il primo JSON-LD di tipo Recipe nella pagina, o None."""
    for voce in _blocchi_json_ld(pagina):
        if voce.get("@type") == "Recipe":
            return voce
        # a volte la ricetta e' dentro un @graph
        for figlio in voce.get("@graph") or []:
            if isinstance(figlio, dict) and figlio.get("@type") == "Recipe":
                return figlio
    return None


def _minuti(iso):
    """Durata ISO 8601 di schema.org ("PT1H20M") in minuti, o None."""
    if not iso:
        return None
    m = re.match(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$", str(iso).strip())
    if not m:
        return None
    giorni, ore, minuti = (int(g or 0) for g in m.groups())
    totale = giorni * 1440 + ore * 60 + minuti
    return totale or None


def _porzioni(valore):
    """Il primo numero di `recipeYield` ("4 porzioni" -> 4)."""
    if isinstance(valore, list):
        valore = valore[0] if valore else None
    m = re.search(r"\d+", str(valore or ""))
    return int(m.group()) if m else None


def _numero(testo):
    """Un numero, anche in forma di frazione ("1/2") o con la virgola."""
    testo = str(testo).replace(",", ".")
    if "/" in testo:
        try:
            sopra, sotto = testo.split("/", 1)
            return float(sopra) / float(sotto)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(testo)
    except ValueError:
        return None


def dividi_ingrediente(testo):
    """Da "Spaghettoni 320 g" a ("Spaghettoni", 320.0, "g").

    Le dosi dei siti sono scritte per esteso e in modi diversi ("Tuorli 4",
    "Sale q.b."). Si toglie la nota fra parentesi e si cerca la quantita' in
    fondo, che e' dove sta quasi sempre. Senza numero si mette 0: "q.b." diventa
    una quantita' che l'utente completa a mano, meglio di una dose inventata.
    """
    pulito = re.sub(r"\([^)]*\)", " ", str(testo or ""))
    pulito = re.sub(r"\bq\.?\s*b\.?\b", " ", pulito, flags=re.I)
    pulito = re.sub(r"\s+", " ", pulito).strip()

    m = re.search(r"(\d+(?:\.\d+)?(?:/\d+)?)\s*([a-zA-Zàèéìòùµ]+)?\s*$", pulito)
    quantita = _numero(m.group(1)) if m else None
    if quantita is None:
        # senza dose resta il nome, ripulito dalla punteggiatura che si tira
        # dietro ("Sale q.b." -> "Sale", non "Sale .")
        return pulito.strip(" .,-") or pulito, 0.0, "pz"
    nome = pulito[:m.start()].strip(" .,-") or pulito
    unita = (m.group(2) or "pz").lower()
    return nome, quantita, unita


def _passi(valore):
    """Le istruzioni in un unico testo, un passo per riga."""
    if isinstance(valore, str):
        return valore.strip()
    if not isinstance(valore, list):
        return ""
    righe = []
    for passo in valore:
        if isinstance(passo, dict):
            testo = passo.get("text") or passo.get("name") or ""
        else:
            testo = str(passo)
        testo = re.sub(r"<[^>]+>", " ", testo)          # a volte c'e' dell'HTML
        testo = _html.unescape(re.sub(r"\s+", " ", testo)).strip()
        if testo:
            righe.append(testo)
    return "\n\n".join(righe)


def cerca(query):
    """Le ricette che il sito trova per `query`, con titolo e indirizzo.

    Si leggono i collegamenti alle pagine di ricetta nella pagina dei risultati,
    che portano gia' il titolo: non serve interpretare la grafica. Si tiene
    l'ordine del sito, che e' la sua idea di pertinenza.
    """
    query = re.sub(r"\s+", " ", str(query or "")).strip()
    if not query:
        return []
    url = RICERCA_URL.format(q=urllib.parse.quote(query))
    if not _permesso(url):
        raise NonDisponibile(f"{SITO} non consente la lettura automatica di questa pagina.")
    try:
        pagina = _apri(url)
    except urllib.error.HTTPError as e:
        raise NonDisponibile(f"{SITO} ha risposto {e.code} alla ricerca.") from e
    except Exception as e:
        raise NonDisponibile(f"Non riesco a contattare {SITO} ({type(e).__name__}).") from e

    trovate, visti = [], set()
    for href, titolo in re.findall(
            r'<a[^>]*href="(https://' + re.escape(RICETTA_HOST) + r'/[^"]+\.html)"'
            r'(?:[^>]*title="([^"]*)")?', pagina):
        if href in visti:
            continue
        visti.add(href)
        etichetta = _html.unescape(titolo or "").strip()
        if not etichetta:
            etichetta = urllib.parse.unquote(href.rsplit("/", 1)[-1][:-5]).replace("-", " ")
        trovate.append({"titolo": etichetta, "url": href})
        if len(trovate) >= _MAX_RISULTATI:
            break
    return trovate


def importa(url):
    """Legge una ricetta dal sito e la restituisce in forma di dati dell'app.

    Non salva niente: la ricetta passa dal modulo come se fosse scritta a mano,
    cosi' l'utente la rivede e la corregge prima che entri in dispensa e nel
    piano. Un dato di un altro sito che finisce in archivio senza passare da un
    controllo sarebbe difficile da accorgersi che e' sbagliato.
    """
    if RICETTA_HOST not in (url or ""):
        raise NonDisponibile("Indirizzo di ricetta non riconosciuto.")
    if not _permesso(url):
        raise NonDisponibile(f"{SITO} non consente la lettura di questa ricetta.")
    try:
        pagina = _apri(url)
    except urllib.error.HTTPError as e:
        raise NonDisponibile(f"{SITO} ha risposto {e.code}.") from e
    except Exception as e:
        raise NonDisponibile(f"Non riesco a contattare {SITO} ({type(e).__name__}).") from e

    ld = _ricetta_ld(pagina)
    if not ld:
        raise NonDisponibile("Questa pagina non contiene una ricetta leggibile.")

    ingredienti = []
    for grezzo in (ld.get("recipeIngredient") or []):
        nome, quantita, unita = dividi_ingrediente(grezzo)
        if nome:
            ingredienti.append({"name": nome, "quantity": quantita, "unit": unita})

    autore = _prima(ld, "author")
    if isinstance(autore, dict):
        autore = autore.get("name")
    autore = str(autore).strip() if autore else ""
    # il sito si nomina spesso come autore: ripeterlo nella fonte la rende
    # illeggibile ("GialloZafferano — GialloZafferano — ...")
    parti = [autore] if autore and autore.lower() != SITO.lower() else []
    parti += [SITO, url]
    fonte = " — ".join(parti)

    return {
        "name": _html.unescape(str(_prima(ld, "name") or "")).strip(),
        "servings": _porzioni(_prima(ld, "recipeYield")) or 2,
        "time_minutes": _minuti(_prima(ld, "totalTime")),
        "difficulty": "facile",
        "instructions": _passi(ld.get("recipeInstructions")),
        "items": ingredienti,
        "image": "",
        "source": fonte,
    }
