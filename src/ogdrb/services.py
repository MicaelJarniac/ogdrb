"""Services."""

from __future__ import annotations

__all__: tuple[str, ...] = (
    "US_COUNTRY_CODE",
    "US_COUNTRY_NAME",
    "UniRepeater",
    "build_export_queries",
    "get_compatible_repeaters",
    "get_repeaters",
    "prepare_local_repeaters",
)

from typing import TYPE_CHECKING, Any, cast

import anyio
import pycountry
from anyio import Path
from attrs import evolve, field, frozen
from loguru import logger
from repeaterbook import Repeater, RepeaterBook, queries
from repeaterbook.models import ExportQuery, Status, Use
from repeaterbook.queries import Bands
from repeaterbook.services import RepeaterBookAPI
from sqlmodel import col, or_

from ogdrb.converters import BANDWIDTH, repeater_to_channels

if TYPE_CHECKING:  # pragma: no cover
    from typing import Self

    from opengd77.models import AnalogChannel, DigitalChannel
    from pycountry.db import Country
    from repeaterbook.utils import Radius
    from sqlalchemy.sql.elements import BinaryExpression, ColumnElement


# US country constants
_US_COUNTRY_OBJ = cast("Country", pycountry.countries.lookup("US"))  # type: ignore[no-untyped-call]
US_COUNTRY_CODE = "US"  # Alpha-2 code for use in comparisons
US_COUNTRY_NAME = _US_COUNTRY_OBJ.name  # "United States" - for database queries

# Module-level service instances (reused across calls)
_RB_API = RepeaterBookAPI(
    app_name="ogdrb",
    app_email="micael@jarniac.dev",
    working_dir=Path(),
)
_RB = RepeaterBook(working_dir=Path())


@frozen
class UniRepeater:
    """Universal repeater model."""

    rb: Repeater = field(eq=False)
    id: tuple[str, str, int]
    analog: AnalogChannel | None = field(default=None, eq=False)
    digital: DigitalChannel | None = field(default=None, eq=False)

    @classmethod
    def from_rb(cls, rb: Repeater) -> Self:
        """Create a UniRepeater from a RepeaterBook repeater."""
        analog, digital = repeater_to_channels(rb)
        return cls(
            rb=rb,
            id=(rb.country or "", rb.state_id, rb.repeater_id),
            analog=analog,
            digital=digital,
        )


def build_export_queries(
    export: ExportQuery,
    *,
    us_state_ids: frozenset[str],
) -> list[ExportQuery]:
    """Build export queries, splitting USA requests per state when provided."""
    us_country = next(
        (country for country in export.countries if country.alpha_2 == "US"),
        None,
    )
    if us_country is None:
        return [export]

    if not us_state_ids:
        msg = "US states must be selected when US is in countries"
        raise ValueError(msg)

    queries_: list[ExportQuery] = []
    non_us_countries = frozenset(
        country for country in export.countries if country.alpha_2 != "US"
    )
    if non_us_countries:
        queries_.append(
            evolve(
                export,
                countries=non_us_countries,
                state_ids=frozenset(),
            )
        )

    queries_.extend(
        evolve(
            export,
            countries=frozenset((us_country,)),
            state_ids=frozenset((state_id,)),
        )
        for state_id in sorted(us_state_ids)
    )
    return queries_


def _compatibility_filters() -> list[Any]:
    """Return SQL filters for repeater compatibility with OpenGD77.

    These filters are used by both map display and zone export to ensure
    consistency. Repeaters must meet ALL of these criteria:
    - Be DMR or analog capable
    - Have "On-air" operational status
    - Have "Open" membership (not private/closed)
    - Operate on 2m (144-148 MHz) or 70cm (420-450 MHz) bands
    - Have valid FM bandwidth (12.5/25 kHz) or None (digital-only)
    """
    return [
        Repeater.dmr_capable | Repeater.analog_capable,
        Repeater.operational_status == Status.ON_AIR,
        Repeater.use_membership == Use.OPEN,
        queries.band(Bands.M_2.value, Bands.CM_70.value),
        or_(
            col(Repeater.fm_bandwidth).is_(None),
            *(Repeater.fm_bandwidth == bw for bw in BANDWIDTH),
        ),
    ]


def get_compatible_repeaters(
    export: ExportQuery,
    *,
    us_state_ids: frozenset[str] = frozenset(),
) -> list[Repeater]:
    """Query compatible repeaters from local database.

    Returns only repeaters that pass the compatibility filters.
    Used by the map display to determine which repeaters to show in blue vs red.

    NOTE: Database must be pre-populated via prepare_local_repeaters() first.
    """
    country_names = {country.name for country in export.countries}
    where: list[BinaryExpression[bool] | ColumnElement[bool]] = list(
        _compatibility_filters()
    )

    if country_names:
        where.append(col(Repeater.country).in_(country_names))
    if us_state_ids:
        where.append(
            or_(
                Repeater.country != US_COUNTRY_NAME,
                col(Repeater.state_id).in_(us_state_ids),
            )
        )

    return list(_RB.query(*where))


def get_repeaters(
    zones: dict[str, Radius],
    *,
    country_names: frozenset[str] = frozenset(),
    us_state_ids: frozenset[str] = frozenset(),
) -> dict[str, list[UniRepeater]]:
    """Query repeaters from local database by zone.

    NOTE: Expects the database to be pre-populated via prepare_local_repeaters().
    The UI should call prepare_local_repeaters() before calling this function.
    """
    extra_filters: list[BinaryExpression[bool] | ColumnElement[bool]] = []
    if country_names:
        extra_filters.append(col(Repeater.country).in_(country_names))
    if us_state_ids:
        extra_filters.append(
            or_(
                Repeater.country != US_COUNTRY_NAME,
                col(Repeater.state_id).in_(us_state_ids),
            )
        )

    result: dict[str, list[UniRepeater]] = {}
    for name, radius in zones.items():
        logger.info(
            f"Zone '{name}': lat={radius.origin.lat}, lon={radius.origin.lon}, "
            f"radius={radius.distance} {radius.unit}"
        )

        queried = _RB.query(
            queries.square(radius), *_compatibility_filters(), *extra_filters
        )
        filtered = list(queries.filter_radius(queried, radius))
        logger.info(f"Found {len(filtered)} repeaters in zone '{name}'")
        result[name] = [UniRepeater.from_rb(r) for r in filtered]

    return result


async def prepare_local_repeaters(
    export: ExportQuery,
    *,
    us_state_ids: frozenset[str] = frozenset(),
) -> list[Repeater]:
    """Download repeaters and populate local database for the selected filters.

    Downloads are performed in parallel for faster processing when multiple
    queries are needed (e.g., multiple US states).
    """
    results: list[list[Repeater]] = []

    async def _download_one(query: ExportQuery) -> None:
        result = await _RB_API.download(query=query)
        results.append(result)

    queries_list = build_export_queries(export, us_state_ids=us_state_ids)
    async with anyio.create_task_group() as tg:
        for query in queries_list:
            tg.start_soon(_download_one, query)

    unique_repeaters = {
        (repeater.country or "", repeater.state_id, repeater.repeater_id): repeater
        for batch in results
        for repeater in batch
    }

    _RB.populate(unique_repeaters.values())

    country_names = {country.name for country in export.countries}
    where: list[BinaryExpression[bool] | ColumnElement[bool]] = []
    if country_names:
        where.append(col(Repeater.country).in_(country_names))
    if us_state_ids:
        where.append(
            or_(
                Repeater.country != US_COUNTRY_NAME,
                col(Repeater.state_id).in_(us_state_ids),
            )
        )

    return list(_RB.query(*where))
