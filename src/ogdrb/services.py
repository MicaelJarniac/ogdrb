"""Services."""

from __future__ import annotations

__all__: tuple[str, ...] = (
    "UniRepeater",
    "build_export_queries",
    "get_repeaters",
    "prepare_local_repeaters",
)

from typing import TYPE_CHECKING

from anyio import Path
from attrs import evolve, field, frozen
from repeaterbook import Repeater, RepeaterBook, queries
from repeaterbook.models import ExportQuery, Status, Use
from repeaterbook.queries import Bands
from repeaterbook.services import RepeaterBookAPI
from sqlmodel import col, or_

from ogdrb.converters import BANDWIDTH, repeater_to_channels

if TYPE_CHECKING:  # pragma: no cover
    from typing import Self

    from opengd77.models import AnalogChannel, DigitalChannel
    from repeaterbook.utils import Radius
    from sqlalchemy.sql.elements import BinaryExpression, ColumnElement


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
        return [export]

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


async def get_repeaters(
    export: ExportQuery,
    zones: dict[str, Radius],
    *,
    us_state_ids: frozenset[str] = frozenset(),
) -> dict[str, list[UniRepeater]]:
    """Get repeaters from RepeaterBook API."""
    await prepare_local_repeaters(export, us_state_ids=us_state_ids)

    rb = RepeaterBook(
        working_dir=Path(),
    )

    return {
        name: [
            UniRepeater.from_rb(r)
            for r in queries.filter_radius(
                rb.query(
                    queries.square(radius),
                    Repeater.dmr_capable | Repeater.analog_capable,
                    Repeater.operational_status == Status.ON_AIR,
                    Repeater.use_membership == Use.OPEN,
                    queries.band(Bands.M_2, Bands.CM_70),
                    or_(*(Repeater.fm_bandwidth == bw for bw in BANDWIDTH)),
                ),
                radius,
            )
        ]
        for name, radius in zones.items()
    }


async def prepare_local_repeaters(
    export: ExportQuery,
    *,
    us_state_ids: frozenset[str] = frozenset(),
) -> list[Repeater]:
    """Download repeaters and populate local database for the selected filters."""
    rb_api = RepeaterBookAPI(
        app_name="ogdrb",
        app_email="micael@jarniac.dev",
        working_dir=Path(),
    )

    all_repeaters: list[Repeater] = []
    for query in build_export_queries(export, us_state_ids=us_state_ids):
        all_repeaters.extend(await rb_api.download(query=query))

    unique_repeaters = {
        (repeater.country or "", repeater.state_id, repeater.repeater_id): repeater
        for repeater in all_repeaters
    }

    rb = RepeaterBook(
        working_dir=Path(),
    )
    rb.populate(unique_repeaters.values())

    country_names = {country.name for country in export.countries}
    where: list[BinaryExpression[bool] | ColumnElement[bool]] = []
    if country_names:
        where.append(col(Repeater.country).in_(country_names))
    if us_state_ids:
        where.append(
            or_(
                Repeater.country != "United States",
                col(Repeater.state_id).in_(us_state_ids),
            )
        )

    return list(rb.query(*where))
