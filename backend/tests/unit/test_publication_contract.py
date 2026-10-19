import copy

import pytest

from app.services.publication import canonical, checksum, sanitize_overlay


def test_canonical_checksum_order_and_invalid_numbers():
    assert canonical({"b": 2, "a": ["é", 1]}) == b'{"a":["\xc3\xa9",1],"b":2}'
    assert checksum({"a": 1, "b": 2}) == checksum({"b": 2, "a": 1})
    assert checksum({"a": 1}) != checksum({"a": 2})
    with pytest.raises(ValueError):
        canonical({"distance": float("nan")})


def test_derivative_requires_explicit_public_features_and_strips_original_properties():
    original = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"label": "Synthetic only", "public": True, "secret": "private"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0.1, 0.1]},
                "properties": {"label": "Restricted geometry", "public": False},
            },
        ],
    }
    before = copy.deepcopy(original)
    clean = sanitize_overlay(original)
    assert len(clean["features"]) == 1
    assert clean["features"][0]["properties"] == {"label": "Synthetic only"}
    assert original == before
    original["features"][0]["properties"]["public"] = False
    with pytest.raises(ValueError, match="mark approved public"):
        sanitize_overlay(original)


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Point", "coordinates": [181, 0]},
        {"type": "LineString", "coordinates": [[0, 0]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
        {"type": "MultiPolygon", "coordinates": []},
    ],
)
def test_invalid_derivative_geometry(geometry):
    with pytest.raises(ValueError):
        sanitize_overlay(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": geometry, "properties": {"public": True}}
                ],
            }
        )
