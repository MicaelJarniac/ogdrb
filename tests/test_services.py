"""Tests for services."""

# ruff: noqa: PLR2004

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pycountry
import pytest
from haversine import Unit  # type: ignore[import-untyped]
from repeaterbook import Repeater
from repeaterbook.models import ExportQuery
from repeaterbook.utils import LatLon, Radius

from ogdrb.services import build_export_queries, get_repeaters, prepare_local_repeaters

if TYPE_CHECKING:
    from pycountry.db import Country


def test_build_export_queries_without_us() -> None:
    """Keep a single query when USA is not selected."""
    canada = cast("Country", pycountry.countries.lookup("CA"))  # type: ignore[no-untyped-call]
    query = ExportQuery(countries=frozenset((canada,)))

    result = build_export_queries(query, us_state_ids=frozenset({"CA"}))

    assert result == [query]


def test_build_export_queries_split_us_states() -> None:
    """Split USA query into one request per selected state."""
    usa = cast("Country", pycountry.countries.lookup("US"))  # type: ignore[no-untyped-call]
    canada = cast("Country", pycountry.countries.lookup("CA"))  # type: ignore[no-untyped-call]
    query = ExportQuery(countries=frozenset((usa, canada)))

    result = build_export_queries(query, us_state_ids=frozenset({"CA", "NY"}))

    assert result[0].countries == frozenset((canada,))
    assert result[0].state_ids == frozenset()
    assert result[1].countries == frozenset((usa,))
    assert result[1].state_ids == frozenset(("CA",))
    assert result[2].countries == frozenset((usa,))
    assert result[2].state_ids == frozenset(("NY",))


def test_build_export_queries_raises_on_us_without_states() -> None:
    """Raise ValueError when US is selected but no states provided."""
    usa = cast("Country", pycountry.countries.lookup("US"))  # type: ignore[no-untyped-call]
    query = ExportQuery(countries=frozenset((usa,)))

    with pytest.raises(ValueError, match="US states must be selected"):
        build_export_queries(query, us_state_ids=frozenset())


@pytest.mark.anyio
async def test_prepare_local_repeaters_downloads_and_deduplicates() -> None:
    """Test that prepare_local_repeaters downloads, deduplicates, and populates."""
    canada = cast("Country", pycountry.countries.lookup("CA"))  # type: ignore[no-untyped-call]
    query = ExportQuery(countries=frozenset((canada,)))

    # Create mock repeaters with duplicates
    repeater1 = Repeater(
        state_id="BC",
        repeater_id=123,
        country="Canada",
        frequency=Decimal("146.52"),
        input_frequency=Decimal("146.52"),
        latitude=Decimal("49.2827"),
        longitude=Decimal("-123.1207"),
        location_nearest_city="Vancouver",
        analog_capable=True,
        dmr_capable=False,
        operational_status="On-air",
        use_membership="Open",
    )
    repeater2 = repeater1  # Duplicate (same state_id, repeater_id)
    repeater3 = Repeater(
        state_id="ON",
        repeater_id=456,
        country="Canada",
        frequency=Decimal("146.94"),
        input_frequency=Decimal("146.94"),
        latitude=Decimal("43.6532"),
        longitude=Decimal("-79.3832"),
        location_nearest_city="Toronto",
        analog_capable=True,
        dmr_capable=False,
        operational_status="On-air",
        use_membership="Open",
    )

    with (
        patch("ogdrb.services._RB_API") as mock_api,
        patch("ogdrb.services._RB") as mock_rb,
    ):
        # Mock download to return repeaters with duplicates
        mock_api.download = AsyncMock(return_value=[repeater1, repeater2, repeater3])

        # Mock populate and query
        mock_rb.populate = MagicMock()
        mock_rb.query = MagicMock(return_value=[repeater1, repeater3])

        result = await prepare_local_repeaters(query, us_state_ids=frozenset())

        # Verify download was called
        assert mock_api.download.called

        # Verify populate was called with deduplicated repeaters
        mock_rb.populate.assert_called_once()
        populated_repeaters = list(mock_rb.populate.call_args[0][0])
        # Should have 2 unique repeaters (repeater1 == repeater2)
        assert len(populated_repeaters) == 2

        # Verify query was called
        assert mock_rb.query.called

        # Verify result
        assert result == [repeater1, repeater3]


def test_get_repeaters_queries_by_zone() -> None:
    """Test that get_repeaters queries the database by zone without re-downloading."""
    # Create a test zone
    zones = {
        "Test Zone": Radius(
            origin=LatLon(lat=49.2827, lon=-123.1207),
            distance=10.0,
            unit=Unit.KILOMETERS,
        )
    }

    # Create mock repeaters
    repeater1 = Repeater(
        state_id="BC",
        repeater_id=123,
        country="Canada",
        frequency=Decimal("146.52"),
        input_frequency=Decimal("146.52"),
        latitude=Decimal("49.2827"),
        longitude=Decimal("-123.1207"),
        location_nearest_city="Vancouver",
        analog_capable=True,
        dmr_capable=False,
        operational_status="On-air",
        use_membership="Open",
        fm_bandwidth=Decimal("25.0"),
    )

    with patch("ogdrb.services._RB") as mock_rb:
        # Mock query to return test repeater
        mock_rb.query = MagicMock(return_value=[repeater1])

        result = get_repeaters(zones)

        # Verify query was called (but NOT download)
        assert mock_rb.query.called

        # Verify result structure
        assert "Test Zone" in result
        assert len(result["Test Zone"]) == 1
        # The actual filtering is done by queries.filter_radius which we're not mocking
