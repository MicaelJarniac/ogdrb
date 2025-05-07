"""Organizer."""

from __future__ import annotations

__all__: tuple[str, ...] = ("organize",)

from typing import TYPE_CHECKING

from opengd77.constants import Max
from opengd77.models import AnalogChannel, Codeplug, DigitalChannel, Zone

from ogdrb.utils import MakeUnique

if TYPE_CHECKING:  # pragma: no cover
    from ogdrb.services import UniRepeater


def organize(
    uni_repeaters_by_zone: dict[str, list[UniRepeater]],
) -> Codeplug:
    """Organize repeaters into a codeplug.

    This function takes a dictionary of repeaters organized by zone and creates a
    Codeplug object with the repeaters organized into channels and zones.
    """
    uni_repeaters = {
        uni_repeater.id: uni_repeater
        for zone in uni_repeaters_by_zone.values()
        for uni_repeater in zone
    }

    uni_repeaters_by_zone = {
        zone: [uni_repeaters[uni_repeater.id] for uni_repeater in repeaters]
        for zone, repeaters in uni_repeaters_by_zone.items()
    }

    channels: list[AnalogChannel | DigitalChannel] = []
    for uni_repeater in uni_repeaters.values():
        if uni_repeater.analog:
            channels.append(uni_repeater.analog)
        if uni_repeater.digital:
            channels.append(uni_repeater.digital)

    make_unique = MakeUnique(
        (channel.name for channel in channels),
        max_length=Max.CHARS_CHANNEL_NAME,
    )

    for channel in channels:
        channel.name = make_unique(channel.name)

    codeplug_zones: list[Zone] = []
    for zone, repeaters in uni_repeaters_by_zone.items():
        digital_zone = Zone(
            name=f"{zone} [D]",
            channels=[
                uni_repeater.digital
                for uni_repeater in repeaters
                if uni_repeater.digital
            ][: Max.CHANNELS_PER_ZONE],
        )
        analog_zone = Zone(
            name=f"{zone} [A]",
            channels=[
                uni_repeater.analog for uni_repeater in repeaters if uni_repeater.analog
            ][: Max.CHANNELS_PER_ZONE],
        )
        codeplug_zones.extend([digital_zone, analog_zone])

    return Codeplug(
        channels=channels,  # No trimming, let it error if too many
        zones=codeplug_zones[: Max.ZONES],
    )
