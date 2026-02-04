"""Tests for services."""

from __future__ import annotations

import pycountry
from repeaterbook.models import ExportQuery

from ogdrb.services import build_export_queries


def test_build_export_queries_without_us() -> None:
    """Keep a single query when USA is not selected."""
    canada = pycountry.countries.lookup("CA")
    query = ExportQuery(countries=frozenset((canada,)))

    result = build_export_queries(query, us_state_ids=frozenset({"CA"}))

    assert result == [query]


def test_build_export_queries_split_us_states() -> None:
    """Split USA query into one request per selected state."""
    usa = pycountry.countries.lookup("US")
    canada = pycountry.countries.lookup("CA")
    query = ExportQuery(countries=frozenset((usa, canada)))

    result = build_export_queries(query, us_state_ids=frozenset({"CA", "NY"}))

    assert result[0].countries == frozenset((canada,))
    assert result[0].state_ids == frozenset()
    assert result[1].countries == frozenset((usa,))
    assert result[1].state_ids == frozenset(("CA",))
    assert result[2].countries == frozenset((usa,))
    assert result[2].state_ids == frozenset(("NY",))
