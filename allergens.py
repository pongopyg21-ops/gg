"""Riconoscimento di allergeni e intolleranze a partire dal nome dell'ingrediente.

Gli allergeni gestiti sono quelli dell'allegato II del Regolamento UE 1169/2011,
gli stessi che per legge vanno evidenziati in etichetta. Oltre a questi l'utente
può dichiarare termini liberi (nichel, fruttosio, ...), che vengono cercati
direttamente nel nome degli ingredienti.

Il riconoscimento avviene per parola intera sul nome dell'ingrediente, quindi è
una stima basata sui nomi e **non sostituisce la lettura dell'etichetta**: un
ingrediente composto o lavorato può contenere un allergene che il nome non dice
(es. "salsa di soia" contiene grano, "pasta sfoglia" contiene burro).
"""
import re
import unicodedata

# Allegato II del Regolamento UE 1169/2011
ALLERGENS = {
    "glutine": "Cereali contenenti glutine",
    "crostacei": "Crostacei",
    "uova": "Uova",
    "pesce": "Pesce",
    "arachidi": "Arachidi",
    "soia": "Soia",
    "latte": "Latte e lattosio",
    "frutta_guscio": "Frutta a guscio",
    "sedano": "Sedano",
    "senape": "Senape",
    "sesamo": "Semi di sesamo",
    "solfiti": "Anidride solforosa e solfiti",
    "lupini": "Lupini",
    "molluschi": "Molluschi",
}

# Regole in ordine di precedenza: le prime sono eccezioni a quelle generiche
# (che altrimenti darebbero falsi positivi), quindi vanno tenute in cima.
# (frase, allergeni, esclusiva) — se una regola esclusiva trova riscontro,
# le altre vengono ignorate.
_RULES = [
    # eccezioni: nomi che contengono la parola di un allergene senza esserlo
    ("noce moscata", (), True),
    ("burro di arachidi", ("arachidi",), True),
    ("burro di cacao", (), True),
    ("latte di soia", ("soia",), True),
    ("latte di mandorla", ("frutta_guscio",), True),
    ("noodles di riso", (), True),
    ("latte di cocco", (), True),
    # un ordine di grandezza: le salse composte dichiarano più allergeni
    ("salsa di soia", ("soia", "glutine"), True),
    ("salsa di pesce", ("pesce",), True),

    # cereali contenenti glutine
    ("farina", ("glutine",), False), ("pasta", ("glutine",), False),
    ("spaghetti", ("glutine",), False), ("penne", ("glutine",), False),
    ("fusilli", ("glutine",), False), ("rigatoni", ("glutine",), False),
    ("tagliatelle", ("glutine",), False), ("lasagne", ("glutine",), False),
    ("gnocchi", ("glutine",), False), ("ravioli", ("glutine",), False),
    ("tortellini", ("glutine",), False), ("pane", ("glutine",), False),
    ("calamarata", ("glutine",), False), ("bucatini", ("glutine",), False),
    ("farfalle", ("glutine",), False), ("orecchiette", ("glutine",), False),
    ("maccheroni", ("glutine",), False), ("conchiglie", ("glutine",), False),
    ("ditalini", ("glutine",), False), ("trofie", ("glutine",), False),
    ("vermicelli", ("glutine",), False), ("capellini", ("glutine",), False),
    ("pappardelle", ("glutine",), False), ("tortelloni", ("glutine",), False),
    ("pangrattato", ("glutine",), False), ("savoiardi", ("glutine",), False),
    ("biscotti", ("glutine",), False), ("cracker", ("glutine",), False),
    ("pizza", ("glutine",), False), ("focaccia", ("glutine",), False),
    ("couscous", ("glutine",), False), ("orzo", ("glutine",), False),
    ("farro", ("glutine",), False), ("spelta", ("glutine",), False),
    ("kamut", ("glutine",), False), ("seitan", ("glutine",), False),
    ("birra", ("glutine",), False), ("brioche", ("glutine",), False),
    ("croissant", ("glutine",), False), ("crouton", ("glutine",), False),
    ("noodles", ("glutine",), False),

    # uova
    ("uova", ("uova",), False), ("uovo", ("uova",), False),
    ("albume", ("uova",), False), ("tuorlo", ("uova",), False),
    ("maionese", ("uova",), False),

    # latte e derivati
    ("latte", ("latte",), False), ("burro", ("latte",), False),
    ("panna", ("latte",), False), ("formaggio", ("latte",), False),
    ("parmigiano", ("latte",), False), ("grana", ("latte",), False),
    ("pecorino", ("latte",), False), ("mozzarella", ("latte",), False),
    ("mascarpone", ("latte",), False), ("ricotta", ("latte",), False),
    ("gorgonzola", ("latte",), False), ("gruyere", ("latte",), False),
    ("emmental", ("latte",), False), ("brie", ("latte",), False),
    ("stracchino", ("latte",), False), ("provola", ("latte",), False),
    ("scamorza", ("latte",), False), ("fiordilatte", ("latte",), False),
    ("yogurt", ("latte",), False), ("besciamella", ("latte",), False),
    ("bechamel", ("latte",), False),

    # pesce
    ("pesce", ("pesce",), False), ("orata", ("pesce",), False),
    ("branzino", ("pesce",), False), ("tonno", ("pesce",), False),
    ("salmone", ("pesce",), False), ("merluzzo", ("pesce",), False),
    ("platessa", ("pesce",), False), ("nasello", ("pesce",), False),
    ("sardine", ("pesce",), False), ("acciughe", ("pesce",), False),
    ("alici", ("pesce",), False), ("sgombro", ("pesce",), False),
    ("trota", ("pesce",), False), ("pesce spada", ("pesce",), False),
    ("cernia", ("pesce",), False), ("rombo", ("pesce",), False),
    ("baccala", ("pesce",), False), ("stoccafisso", ("pesce",), False),
    ("surimi", ("pesce",), False),

    # crostacei
    ("gamberi", ("crostacei",), False), ("gambero", ("crostacei",), False),
    ("gamberetti", ("crostacei",), False), ("gamberoni", ("crostacei",), False),
    ("scampi", ("crostacei",), False), ("mazzancolle", ("crostacei",), False),
    ("aragosta", ("crostacei",), False), ("astice", ("crostacei",), False),
    ("granchio", ("crostacei",), False),

    # molluschi
    ("vongole", ("molluschi",), False), ("vongola", ("molluschi",), False),
    ("cozze", ("molluschi",), False), ("cozza", ("molluschi",), False),
    ("seppia", ("molluschi",), False), ("seppie", ("molluschi",), False),
    ("calamari", ("molluschi",), False), ("calamaro", ("molluschi",), False),
    ("polpo", ("molluschi",), False), ("polpi", ("molluschi",), False),
    ("totani", ("molluschi",), False), ("ostriche", ("molluschi",), False),
    ("capesante", ("molluschi",), False), ("cannolicchi", ("molluschi",), False),
    ("frutti di mare", ("molluschi", "crostacei"), False),

    # arachidi e frutta a guscio
    ("arachidi", ("arachidi",), False), ("arachide", ("arachidi",), False),
    ("mandorle", ("frutta_guscio",), False), ("mandorla", ("frutta_guscio",), False),
    ("nocciole", ("frutta_guscio",), False), ("nocciola", ("frutta_guscio",), False),
    ("noci", ("frutta_guscio",), False), ("noce", ("frutta_guscio",), False),
    ("pistacchi", ("frutta_guscio",), False), ("anacardi", ("frutta_guscio",), False),
    ("pinoli", ("frutta_guscio",), False), ("pecan", ("frutta_guscio",), False),
    ("macadamia", ("frutta_guscio",), False),

    # soia
    ("soia", ("soia",), False), ("tofu", ("soia",), False),
    ("edamame", ("soia",), False), ("tempeh", ("soia",), False),
    ("miso", ("soia",), False),

    # sedano, senape, sesamo, lupini
    ("sedano", ("sedano",), False), ("celeriaco", ("sedano",), False),
    ("senape", ("senape",), False), ("mostarda", ("senape",), False),
    ("sesamo", ("sesamo",), False), ("tahina", ("sesamo",), False),
    ("tahini", ("sesamo",), False), ("hummus", ("sesamo",), False),
    ("lupini", ("lupini",), False), ("lupino", ("lupini",), False),

    # anidride solforosa e solfiti (l'aceto non è di per sé solfitato)
    ("solfiti", ("solfiti",), False), ("anidride solforosa", ("solfiti",), False),
    ("vino", ("solfiti",), False),
    ("uvetta", ("solfiti",), False), ("albicocche secche", ("solfiti",), False),
    ("mosto", ("solfiti",), False),
]


def _norm(text):
    """Minuscolo e senza accenti, così 'Caffè' e 'caffe' coincidono."""
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


_COMPILED = [
    (re.compile(rf"\b{re.escape(_norm(phrase))}\b"), frozenset(tags), exclusive)
    for phrase, tags, exclusive in _RULES
]


def allergens_for(name):
    """Insieme delle chiavi di allergene riconosciute nel nome di un ingrediente."""
    text = _norm(name)
    if not text:
        return set()
    found = set()
    for pattern, tags, exclusive in _COMPILED:
        if pattern.search(text):
            if exclusive:
                return set(tags)
            found |= tags
    return found


def tags_for(names):
    """Unione degli allergeni di più ingredienti."""
    found = set()
    for name in names or []:
        found |= allergens_for(name)
    return found


def label_for(term):
    """Etichetta leggibile; un termine libero viene restituito com'è."""
    return ALLERGENS.get(term, term)


# indici normalizzati per riconoscere un termine scritto in italiano
_BY_LABEL = {_norm(label): key for key, label in ALLERGENS.items()}
_BY_LABEL["lattosio"] = "latte"
_BY_LABEL["intolleranza al lattosio"] = "latte"
_BY_LABEL["frutta secca"] = "frutta_guscio"
_BY_LABEL["frutta a guscio"] = "frutta_guscio"
_BY_LABEL["solfiti e anidride solforosa"] = "solfiti"
_BY_LABEL["cereali"] = "glutine"


def resolve(term):
    """Chiave di allergene corrispondente al termine, o None se è un termine libero."""
    needle = _norm(term)
    if needle in ALLERGENS:
        return needle
    return _BY_LABEL.get(needle)


def matching_terms(declared, tags, names):
    """Termini dichiarati dall'utente che trovano riscontro in una ricetta.

    Un termine può essere un allergene noto, scritto come chiave (`latte`) o
    come etichetta (`Latte e lattosio`), oppure un termine libero (`nichel`),
    cercato nel nome degli ingredienti.
    """
    hits = set()
    normalized_names = [_norm(n) for n in names or []]
    for term in declared or []:
        raw = str(term or "").strip()
        if not raw:
            continue
        key = resolve(raw)
        if key:
            if key in tags:
                hits.add(raw)
            continue
        pattern = re.compile(rf"\b{re.escape(_norm(raw))}\b")
        if any(pattern.search(n) for n in normalized_names):
            hits.add(raw)
    return sorted(hits, key=lambda t: _norm(t))
