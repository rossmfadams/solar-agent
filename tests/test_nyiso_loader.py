"""Unit tests for the NYISO queue loader's normalization + matching logic.

No database or network calls are made here — pure-function tests only.
"""

import sys
from pathlib import Path

# Make the scripts/ directory importable without installing it as a package.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from load_nyiso_queue import normalize_name, match_poi, build_substation_index  # noqa: E402


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


def test_normalize_strips_voltage_suffix():
    assert normalize_name("Marcy 345kV") == "MARCY"


def test_normalize_strips_voltage_with_space():
    assert normalize_name("Marcy 345 kV") == "MARCY"


def test_normalize_uppercases():
    assert normalize_name("marcy") == "MARCY"


def test_normalize_strips_punctuation():
    assert normalize_name("East Hampton Sub.") == "EAST HAMPTON SUB"


def test_normalize_collapses_whitespace():
    assert normalize_name("  Niagara  Mohawk  ") == "NIAGARA MOHAWK"


def test_normalize_tbd_returns_empty():
    assert normalize_name("TBD") == ""


def test_normalize_na_returns_empty():
    assert normalize_name("N/A") == ""


def test_normalize_none_returns_empty():
    assert normalize_name(None) == ""


def test_normalize_empty_string_returns_empty():
    assert normalize_name("") == ""


def test_normalize_marcy_345kv_equals_marcy():
    """Key property: the same normalized form used for index lookup."""
    assert normalize_name("Marcy 345kV") == normalize_name("MARCY")


# ---------------------------------------------------------------------------
# match_poi / build_substation_index
# ---------------------------------------------------------------------------

_SUBSTATIONS = [
    {"id": 1, "name": "Marcy", "wkt": "POINT(-75.43 43.17)"},
    {"id": 2, "name": "Niagara Mohawk", "wkt": "POINT(-78.85 43.09)"},
    {"id": 3, "name": "East Hampton", "wkt": "POINT(-72.18 40.96)"},
]


def _index():
    return build_substation_index(_SUBSTATIONS)


def test_exact_match_normalized():
    index = _index()
    sub, method = match_poi("Marcy 345kV", index)
    assert method == "exact"
    assert sub is not None
    assert sub["id"] == 1


def test_exact_match_case_insensitive():
    index = _index()
    sub, method = match_poi("marcy", index)
    assert method == "exact"
    assert sub["id"] == 1


def test_fuzzy_match_substring():
    """'East Hampton Sub' normalizes to 'EAST HAMPTON SUB'; contains 'EAST HAMPTON'."""
    index = _index()
    sub, method = match_poi("East Hampton Sub 115kV", index)
    assert method == "fuzzy"
    assert sub["id"] == 3


def test_no_match_returns_county_method():
    index = _index()
    sub, method = match_poi("Some Unknown Line", index)
    assert method == "county"
    assert sub is None


def test_tbd_poi_returns_county_method():
    index = _index()
    sub, method = match_poi("TBD", index)
    assert method == "county"
    assert sub is None


def test_none_poi_returns_county_method():
    index = _index()
    sub, method = match_poi(None, index)
    assert method == "county"
    assert sub is None


def test_index_skips_substations_with_no_name():
    subs = [{"id": 99, "name": None, "wkt": "POINT(0 0)"}]
    index = build_substation_index(subs)
    assert index == {}
