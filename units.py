"""Conversione tra unità di misura compatibili.

Solo le unità che appartengono alla stessa dimensione sono sommabili:
massa (g, kg) e volume (ml, l, cucchiaino, cucchiaio). Unità come pz o
confezione restano indipendenti, perché non hanno un fattore fisso.
"""

MASSA = "massa"
VOLUME = "volume"

# dimensione -> (unità base, fattori verso l'unità base)
_DIMENSIONS = {
    MASSA: ("g", {"g": 1.0, "kg": 1000.0}),
    VOLUME: ("ml", {"ml": 1.0, "l": 1000.0, "cucchiaino": 5.0, "cucchiaio": 15.0}),
}

# unità fra cui si sceglie automaticamente per la visualizzazione: i cucchiai
# restano fuori, altrimenti 400 ml diventerebbero "26,67 cucchiai"
_LADDER = {
    MASSA: ["g", "kg"],
    VOLUME: ["ml", "l"],
}

_SPOONS = {"cucchiaio", "cucchiaino"}
# oltre questa soglia i cucchiai non sono più leggibili ("24 cucchiai" -> "360 ml")
_SPOON_LIMIT = 250.0

_ALIASES = {
    "grammi": "g", "grammo": "g", "gr": "g",
    "chili": "kg", "chilo": "kg", "chilogrammi": "kg", "chilogrammo": "kg",
    "litri": "l", "litro": "l",
    "millilitri": "ml", "millilitro": "ml",
    "cucchiai": "cucchiaio", "cucchiaini": "cucchiaino",
    "pezzi": "pz", "pezzo": "pz", "unita": "pz", "unità": "pz",
    "confezioni": "confezione", "pacco": "confezione", "pacchi": "confezione",
    "fette": "fetta",
}


def normalize(unit):
    """Uniforma il nome dell'unità; stringa vuota diventa 'pz'."""
    u = (unit or "").strip().lower().rstrip(".")
    return _ALIASES.get(u, u) or "pz"


def _info(unit):
    """(dimensione, fattore, unità base) oppure (None, None, unità normalizzata)."""
    u = normalize(unit)
    for dim, (base, table) in _DIMENSIONS.items():
        if u in table:
            return dim, table[u], base
    return None, None, u


def dimension(unit):
    """Dimensione convertibile dell'unità, o None se non convertibile."""
    return _info(unit)[0]


def base_unit(dim):
    return _DIMENSIONS[dim][0]


def group_key(unit):
    """Chiave di raggruppamento: quantità con la stessa chiave sono sommabili."""
    dim = dimension(unit)
    return dim if dim else f"unit:{normalize(unit)}"


def to_base(quantity, unit):
    """Quantità espressa nell'unità base della sua dimensione."""
    _dim, factor, base = _info(unit)
    return (quantity * factor if factor is not None else quantity), base


def convert(quantity, from_unit, to_unit):
    """Converte fra unità compatibili, altrimenti restituisce None."""
    dim, factor, _ = _info(from_unit)
    dim_to, factor_to, _ = _info(to_unit)
    if dim is None or dim != dim_to:
        return None
    return quantity * factor / factor_to


def display_unit(base_quantity, dim, preferred=None):
    """Unità più leggibile in cui la quantità vale almeno 1.

    Con 2500 ml sceglie 'l' (2.5), con 400 ml resta 'ml', con 1500 g sceglie
    'kg'. Le unità a cucchiaio sono mantenute solo per piccole quantità, dove
    sono più comode dei millilitri; oltre la soglia si passa a ml/l. Unità non
    convertibili restano invariate.
    """
    if dim is None:
        return normalize(preferred)
    pref = normalize(preferred)

    # i cucchiai restano se la quantità è piccola e l'utente li ha usati
    if pref in _SPOONS and base_quantity <= _SPOON_LIMIT:
        return pref

    table = _DIMENSIONS[dim][1]
    ladder = _LADDER[dim]
    chosen = pref if pref in ladder else ladder[0]
    for unit in ladder:  # unità base -> multiplo
        if base_quantity / table[unit] >= 1:
            chosen = unit
    return chosen


def format_quantity(value):
    """Numero leggibile: niente zeri inutili, massimo due decimali."""
    rounded = round(value + 0.0, 2)
    if rounded == int(rounded):
        return int(rounded)
    return rounded