"""Converters."""

from __future__ import annotations

__all__: tuple[str, ...] = ()


import unicodedata
from decimal import Decimal
from typing import Final

from opengd77.constants import Max
from opengd77.models import (
    AnalogChannel,
    Bandwidth,
    Codeplug,
    DigitalChannel,
    TalkerAlias,
    Zone,
)
from repeaterbook.models import Repeater

from ogdrb.utils import MakeUnique

BANDWIDTH: Final[dict[Decimal, Bandwidth]] = {
    Decimal("12.5"): Bandwidth.BW_12_5KHZ,
    Decimal("25.0"): Bandwidth.BW_25KHZ,
}


def normalize_string(input_str: str) -> str:
    return (
        unicodedata.normalize("NFKD", input_str)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def make_name(*, callsign: str | None, city: str, digital: bool) -> str:
    """Create a name for the channel."""
    return (
        f"{callsign or ''}"
        f"{'_' if digital else '~'}"
        f"{''.join(c.capitalize() for c in normalize_string(city).split(' '))}"
    )[: Max.CHARS_CHANNEL_NAME]


def rb_to_ogd(repeater: Repeater) -> tuple[AnalogChannel | None, DigitalChannel | None]:
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


def repeaters_to_codeplug(repeaters: list[Repeater]) -> Codeplug:
    """Convert a list of Repeaters to a Codeplug."""
    channels: list[AnalogChannel | DigitalChannel] = []

    for repeater in repeaters:
        analog, digital = rb_to_ogd(repeater)
        if analog:
            channels.append(analog)
        if digital:
            channels.append(digital)

    # If there are multiple channels with the exact same name, append a number
    # to all of them to make them unique
    make_unique = MakeUnique(
        (channel.name for channel in channels), max_length=Max.CHARS_CHANNEL_NAME
    )
    for channel in channels:
        channel.name = make_unique(channel.name)

    zone_digital = Zone(
        name="Digital",
        channels=[
            channel for channel in channels if isinstance(channel, DigitalChannel)
        ][: Max.CHANNELS_PER_ZONE],
    )
    zone_analog = Zone(
        name="Analog",
        channels=[
            channel for channel in channels if isinstance(channel, AnalogChannel)
        ][: Max.CHANNELS_PER_ZONE],
    )

    return Codeplug(
        channels=channels[: Max.CHANNELS],
        zones=[zone_digital, zone_analog],
    )
