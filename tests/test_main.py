"""Tests for main module (ZoneManager)."""

# ruff: noqa: SLF001, PLR2004, D107, PLC0415

from __future__ import annotations

from typing import TYPE_CHECKING

from ogdrb.main import ZoneManager, ZoneRow

if TYPE_CHECKING:
    from typing import Any


class MockLeaflet:
    """Mock Leaflet map for testing."""

    id = "test-map"


class MockGrid:
    """Mock AG Grid for testing."""

    id = "test-grid"

    def __init__(self, rows: list[ZoneRow] | None = None) -> None:
        self.options = {"rowData": rows or []}


def test_zone_manager_id_generation() -> None:
    """Test that _new_id() generates sequential IDs."""
    zm = ZoneManager(MockLeaflet(), MockGrid())  # type: ignore[arg-type]

    assert zm._new_id() == 1
    assert zm._new_id() == 2
    assert zm._new_id() == 3


def test_zone_manager_register_unregister() -> None:
    """Test bidirectional ID mapping."""
    zm = ZoneManager(MockLeaflet(), MockGrid())  # type: ignore[arg-type]

    # Register mapping
    zm._register(row_id=100, leaflet_id=200)

    assert zm._row_to_leaflet[100] == 200
    assert zm._leaflet_to_row[200] == 100

    # Unregister mapping
    zm._unregister(100)

    assert 100 not in zm._row_to_leaflet
    assert 200 not in zm._leaflet_to_row


def test_zone_manager_row_index() -> None:
    """Test O(1) row lookups with _rows_by_id index."""
    initial_rows = [
        ZoneRow(id=1, name="Zone 1", lat=10.0, lng=20.0, radius=5.0),
        ZoneRow(id=2, name="Zone 2", lat=30.0, lng=40.0, radius=10.0),
    ]
    grid = MockGrid(initial_rows)
    zm = ZoneManager(MockLeaflet(), grid)  # type: ignore[arg-type]

    # Manually populate the index (normally done by event handlers)
    for row in initial_rows:
        zm._rows_by_id[row["id"]] = row

    # Test lookups
    row1 = zm._find_row(1)
    assert row1 is not None
    assert row1["name"] == "Zone 1"
    assert row1["lat"] == 10.0

    row2 = zm._find_row(2)
    assert row2 is not None
    assert row2["name"] == "Zone 2"

    # Test non-existent row
    row3 = zm._find_row(999)
    assert row3 is None


def test_zone_manager_resolve_row_id() -> None:
    """Test resolving row ID from layer dict."""
    zm = ZoneManager(MockLeaflet(), MockGrid())  # type: ignore[arg-type]
    zm._register(row_id=100, leaflet_id=200)

    # Resolve via leaflet_id mapping
    layer1 = {"_leaflet_id": 200}
    assert zm._resolve_row_id(layer1) == 100

    # Resolve via _ogdrb_row_id stamp
    layer2 = {"_ogdrb_row_id": 100}
    assert zm._resolve_row_id(layer2) == 100

    # Resolve with both (leaflet_id takes precedence)
    layer3 = {"_leaflet_id": 200, "_ogdrb_row_id": 999}
    assert zm._resolve_row_id(layer3) == 100

    # Resolve with neither
    layer4: dict[str, Any] = {}
    assert zm._resolve_row_id(layer4) is None


def test_zone_manager_update_rows_from_layers() -> None:
    """Test updating rows from layer data."""
    initial_rows = [
        ZoneRow(id=1, name="Zone 1", lat=10.0, lng=20.0, radius=5.0),
    ]
    grid = MockGrid(initial_rows)
    zm = ZoneManager(MockLeaflet(), grid)  # type: ignore[arg-type]

    # Manually populate the index
    zm._rows_by_id[1] = initial_rows[0]

    # Simulate layer data from Leaflet
    layers = [
        {
            "_leaflet_id": 999,
            "_ogdrb_row_id": 1,  # Points to row ID 1
            "_latlng": {"lat": 50.0, "lng": 60.0},
            "_mRadius": 15000,  # 15 km in meters
        }
    ]

    zm._update_rows_from_layers(layers)

    # Check that row was updated
    row = zm._find_row(1)
    assert row is not None
    assert row["lat"] == 50.0
    assert row["lng"] == 60.0
    assert row["radius"] == 15.0  # Converted from meters to km
    assert row["name"] == "Zone 1"  # Name unchanged


def test_zone_manager_iter_event_layers() -> None:
    """Test extracting layers from draw events."""
    from unittest.mock import Mock

    # Test with layers dict
    event1 = Mock()
    event1.args = {
        "layers": {
            "_layers": {
                "1": {"_leaflet_id": 1},
                "2": {"_leaflet_id": 2},
            }
        }
    }
    layers1 = ZoneManager._iter_event_layers(event1)
    assert len(layers1) == 2
    assert {"_leaflet_id": 1} in layers1
    assert {"_leaflet_id": 2} in layers1

    # Test with single layer
    event2 = Mock()
    event2.args = {"layer": {"_leaflet_id": 1}}
    layers2 = ZoneManager._iter_event_layers(event2)
    assert len(layers2) == 1
    assert layers2[0] == {"_leaflet_id": 1}

    # Test with no layers
    event3 = Mock()
    event3.args = {}
    layers3 = ZoneManager._iter_event_layers(event3)
    assert len(layers3) == 0
