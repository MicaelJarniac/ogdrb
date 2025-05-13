"""Services."""

from __future__ import annotations

__all__: tuple[str, ...] = (
    "UniRepeater",
    "get_repeaters",
)

from typing import TYPE_CHECKING

from anyio import Path
from attrs import field, frozen
from repeaterbook import Repeater, RepeaterBook, queries
from repeaterbook.models import ExportQuery, Status, Use
from repeaterbook.queries import Bands
from repeaterbook.services import RepeaterBookAPI
from sqlmodel import or_

from ogdrb.converters import BANDWIDTH, repeater_to_channels

if TYPE_CHECKING:  # pragma: no cover
    from typing import Self

    from opengd77.models import AnalogChannel, DigitalChannel
    from repeaterbook.utils import Radius


@frozen
class UniRepeater:
    """Universal repeater model."""

    rb: Repeater = field(eq=False)
    id: tuple[str, int]
    analog: AnalogChannel | None = field(default=None, eq=False)
    digital: DigitalChannel | None = field(default=None, eq=False)

    @classmethod
    def from_rb(cls, rb: Repeater) -> Self:
        """Create a UniRepeater from a RepeaterBook repeater."""
        analog, digital = repeater_to_channels(rb)
        return cls(
            rb=rb,
            id=(rb.state_id, rb.repeater_id),
            analog=analog,
            digital=digital,
        )


async def get_repeaters(
    export: ExportQuery,
    zones: dict[str, Radius],
) -> dict[str, list[UniRepeater]]:
    """Get repeaters from RepeaterBook API."""
    rb_api = RepeaterBookAPI(
        app_name="ogdrb",
        app_email="micael@jarniac.dev",
        working_dir=Path(),
    )
    all_repeaters = await rb_api.download(query=export)

    rb = RepeaterBook(
        working_dir=Path(),
    )
    rb.populate(all_repeaters)

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
