"""Conversione delle unita' di misura.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_normalize_aliases():
    assert units.normalize("Grammi") == "g"
    assert units.normalize("KG") == "kg"
    assert units.normalize("") == "pz"
    assert units.normalize("  Cucchiai ") == "cucchiaio"
    assert units.normalize(None) == "pz"

def test_convert_compatible():
    assert units.convert(1, "kg", "g") == 1000
    assert units.convert(500, "g", "kg") == 0.5
    assert units.convert(2, "cucchiaio", "ml") == 30
    assert units.convert(1, "l", "ml") == 1000

def test_convert_incompatible_returns_none():
    assert units.convert(1, "kg", "l") is None
    assert units.convert(1, "pz", "g") is None
    assert units.convert(1, "confezione", "kg") is None

def test_group_key_merges_same_dimension():
    assert units.group_key("g") == units.group_key("kg")
    assert units.group_key("ml") == units.group_key("cucchiaio")
    assert units.group_key("pz") != units.group_key("confezione")
    assert units.group_key("g") != units.group_key("ml")

def test_display_unit_picks_readable():
    assert units.display_unit(1500, units.MASSA, "g") == "kg"
    assert units.display_unit(200, units.MASSA, "g") == "g"
    assert units.display_unit(1, units.MASSA, "g") == "g"
    assert units.display_unit(400, units.VOLUME, "ml") == "ml"
    assert units.display_unit(2500, units.VOLUME, "ml") == "l"

def test_cucchiai_mantenuti_solo_per_piccole_quantita():
    """5 ml di sale si leggono come 1 cucchiaino, 360 ml no."""
    assert units.display_unit(5, units.VOLUME, "cucchiaino") == "cucchiaino"
    assert units.display_unit(45, units.VOLUME, "cucchiaio") == "cucchiaio"
    assert units.display_unit(360, units.VOLUME, "cucchiaio") == "ml"
    assert units.display_unit(1500, units.VOLUME, "cucchiaio") == "l"

def test_display_unit_keeps_unconvertible():
    assert units.display_unit(3, None, "confezione") == "confezione"
