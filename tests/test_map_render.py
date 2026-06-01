from app.map_render import render_map

_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [-73.760, 42.650],
        [-73.750, 42.650],
        [-73.750, 42.660],
        [-73.760, 42.660],
        [-73.760, 42.650],
    ]],
}

_LINE = {
    "type": "LineString",
    "coordinates": [[-73.760, 42.645], [-73.750, 42.655]],
}

_POINT = {"type": "Point", "coordinates": [-73.755, 42.655]}

_FULL_LAYERS = {
    "center_lat": 42.655,
    "center_lng": -73.755,
    "parcel": _POLYGON,
    "transmission": [_LINE],
    "substations": [_POINT],
    "flood": [_POLYGON],
    "nwi": [_POLYGON],
    "padus": [_POLYGON],
}


def test_render_map_contains_all_layer_tooltips():
    html = render_map(_FULL_LAYERS, parcel_fallback=False)
    assert "HIFLD" in html
    assert "Electric Power Transmission Lines" in html
    assert "Electric Substations" in html
    assert "FEMA National Flood Hazard Layer" in html
    assert "USFWS National Wetlands Inventory" in html
    assert "USGS Protected Areas Database (PAD-US)" in html


def test_render_map_has_layer_control():
    html = render_map(_FULL_LAYERS, parcel_fallback=False)
    assert "L.control.layers" in html


def test_render_map_parcel_polygon_embedded():
    html = render_map(_FULL_LAYERS, parcel_fallback=False)
    assert "-73.760" in html or "-73.75" in html


def test_render_map_normal_parcel_tooltip():
    html = render_map(_FULL_LAYERS, parcel_fallback=False)
    assert "Parcel boundary" in html


def test_render_map_fallback_shows_estimated_buffer_note():
    layers = {**_FULL_LAYERS, "parcel": _POLYGON}
    html = render_map(layers, parcel_fallback=True)
    assert "Estimated 500m buffer" in html
    assert "no parcel polygon" in html


def test_render_map_fallback_uses_distinct_style():
    fallback_html = render_map({**_FULL_LAYERS, "parcel": _POLYGON}, parcel_fallback=True)
    normal_html = render_map({**_FULL_LAYERS, "parcel": _POLYGON}, parcel_fallback=False)
    # Fallback uses orange (#ff7800), normal uses blue (#3388ff)
    assert "#ff7800" in fallback_html
    assert "#3388ff" in normal_html


def test_render_map_empty_layers_still_renders():
    layers = {
        "center_lat": 42.655,
        "center_lng": -73.755,
        "parcel": None,
        "transmission": [],
        "substations": [],
        "flood": [],
        "nwi": [],
        "padus": [],
    }
    html = render_map(layers, parcel_fallback=False)
    assert "L.control.layers" in html
    assert len(html) > 1000
