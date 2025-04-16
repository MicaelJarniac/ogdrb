"""Utils."""

from __future__ import annotations

__all__: tuple[str, ...] = (
    "MakeUnique",
    "normalize_string",
)

import unicodedata
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable


def normalize_string(input_str: str) -> str:
    """Normalize a string by removing accents and converting to ASCII."""
    return (
        unicodedata.normalize("NFKD", input_str)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


class MakeUnique:
    """Make unique names."""

    def __init__(self, existing_names: Iterable[str], max_length: int) -> None:
        """Initialize with an iterable of existing names and a maximum allowed length.

        This sets up the frequency counter, a set of taken names, and counters for each
        base name.
        """
        # Convert iterable to a list (in case it's a generator)
        self.existing_names = list(existing_names)
        # Count how many times each name appears
        self.freq = Counter(self.existing_names)
        # Track names already in use to avoid clashes
        self.taken = set(self.existing_names)
        # For each base name, track the next numeric suffix to try
        self.counters: defaultdict[str, int] = defaultdict(int)
        # Track how many times a name is processed so that unique names are kept as is
        # on first occurrence
        self.occurrence_counter: defaultdict[str, int] = defaultdict(int)
        # Maximum length for any candidate name (base + suffix)
        self.max_length = max_length

    def __call__(self, name: str) -> str:
        """Given a name, return a unique version.

        - If the name is unique in the original set and it's the first time it appears,
          it's returned unchanged.
        - Otherwise, a numeric suffix is appended.
          If the base plus suffix would exceed max_length, the base is truncated from
          the end to make room.
        """
        self.occurrence_counter[name] += 1

        # For a unique name (appearing only once) on its first occurrence,
        # return it as is.
        if self.freq[name] == 1 and self.occurrence_counter[name] == 1:
            return name

        # Generate a candidate with a numeric suffix.
        self.counters[name] += 1
        suffix = str(self.counters[name])
        # Determine how many characters of the original name can be kept so that
        # the candidate (base + suffix) does not exceed max_length.
        allowed_len = self.max_length - len(suffix)
        allowed_len = max(allowed_len, 0)
        truncated_base = name[:allowed_len]
        candidate = f"{truncated_base}{suffix}"

        # If the candidate already exists, keep incrementing the suffix
        # (and adjust truncation) until we find a free candidate.
        while candidate in self.taken:
            self.counters[name] += 1
            suffix = str(self.counters[name])
            allowed_len = self.max_length - len(suffix)
            allowed_len = max(allowed_len, 0)
            truncated_base = name[:allowed_len]
            candidate = f"{truncated_base}{suffix}"

        self.taken.add(candidate)
        return candidate
