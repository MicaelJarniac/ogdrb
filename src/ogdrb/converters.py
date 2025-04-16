"""Converters."""

from __future__ import annotations

__all__: tuple[str, ...] = (
    "make_name",
    "repeater_to_channels",
)


from decimal import Decimal
from typing import TYPE_CHECKING, Final

from opengd77.constants import Max
from opengd77.models import (
    AnalogChannel,
    Bandwidth,
    DigitalChannel,
    TalkerAlias,
)

from ogdrb.utils import normalize_string

if TYPE_CHECKING:  # pragma: no cover
    from repeaterbook.models import Repeater

BANDWIDTH: Final[dict[Decimal, Bandwidth]] = {
    Decimal("12.5"): Bandwidth.BW_12_5KHZ,
    Decimal("25.0"): Bandwidth.BW_25KHZ,
}


def make_name(*, callsign: str | None, city: str, digital: bool) -> str:
    """Create a name for the channel."""
    return (
        f"{callsign or ''}"
        f"{'_' if digital else '~'}"
        f"{''.join(c.capitalize() for c in normalize_string(city).split(' '))}"
    )[: Max.CHARS_CHANNEL_NAME]


def repeater_to_channels(
    repeater: Repeater,
) -> tuple[AnalogChannel | None, DigitalChannel | None]:
    """Convert a RepeaterBook repeater to OpenGD77 channels."""
    analog: AnalogChannel | None = None
    digital: DigitalChannel | None = None

    if repeater.analog_capable:
        analog = AnalogChannel(
            name=make_name(
                callsign=repeater.callsign,
                city=repeater.location_nearest_city,
                digital=False,
            ),
            rx_frequency=repeater.frequency,
            tx_frequency=repeater.input_frequency,
            latitude=repeater.latitude,
            longitude=repeater.longitude,
            use_location=True,
            bandwidth=BANDWIDTH[repeater.fm_bandwidth]
            if repeater.fm_bandwidth
            else Bandwidth.BW_25KHZ,
            tx_tone=repeater.pl_ctcss_uplink,
            rx_tone=repeater.pl_ctcss_tsq_downlink,
        )

    if repeater.dmr_capable:
        digital = DigitalChannel(
            name=make_name(
                callsign=repeater.callsign,
                city=repeater.location_nearest_city,
                digital=True,
            ),
            rx_frequency=repeater.frequency,
            tx_frequency=repeater.input_frequency,
            latitude=repeater.latitude,
            longitude=repeater.longitude,
            use_location=True,
            color_code=int(repeater.dmr_color_code) if repeater.dmr_color_code else 0,  # type: ignore[arg-type]
            repeater_timeslot=1,
            timeslot_1_talker_alias=TalkerAlias.APRS | TalkerAlias.TEXT,
            timeslot_2_talker_alias=TalkerAlias.APRS | TalkerAlias.TEXT,
        )

    return analog, digital
