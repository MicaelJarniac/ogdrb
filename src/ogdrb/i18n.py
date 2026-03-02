"""i18n utilities for OGDRB."""

from __future__ import annotations

__all__: tuple[str, ...] = (
    "Language",
    "LanguageManager",
    "language_manager",
    "t",
)

import gettext
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple, cast

from babel import Locale
from nicegui import app, ui

if TYPE_CHECKING:
    from nicegui.elements.select import Select
    from nicegui.events import ValueChangeEventArguments


LOCALE_DIR: Final[Path] = Path(__file__).parent / "locales"
DOMAIN: Final[str] = "ogdrb"
LANGUAGE_KEY: Final[str] = "language"

# Override auto-detected emoji for locales whose country code doesn't map to a
# flag (e.g. language-only codes like "pt" or "en").  Keys are POSIX locale
# codes (the directory names under ``locales/``).
EMOJI_OVERRIDES: dict[str, str | None] = {}


class Language(NamedTuple):
    """Represents a supported language."""

    code: str
    name: str
    emoji: str | None = None


def _flag_emoji(country_code: str) -> str | None:
    """Convert an ISO 3166-1 alpha-2 country code to a flag emoji.

    Returns ``None`` when *country_code* is empty or not exactly two ASCII
    letters.
    """
    if (
        len(country_code) != 2  # noqa: PLR2004
        or not country_code.isascii()
        or not country_code.isalpha()
    ):
        return None
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country_code.upper())


def _discover_languages() -> tuple[Language, ...]:
    """Scan *LOCALE_DIR* and build :class:`Language` objects for each locale.

    A locale directory is recognised when it contains
    ``LC_MESSAGES/{DOMAIN}.mo``.  The BCP-47 code, display name, and flag
    emoji are derived automatically from the directory name via
    :mod:`babel`.
    """
    languages: list[Language] = []
    for path in sorted(LOCALE_DIR.iterdir()):
        if not path.is_dir():
            continue
        mo_file = path / "LC_MESSAGES" / f"{DOMAIN}.mo"
        if not mo_file.exists():
            continue
        posix_code = path.name  # e.g. "pt_BR"
        locale = Locale.parse(posix_code)
        bcp47 = str(locale).replace("_", "-")  # e.g. "pt-BR"
        emoji = EMOJI_OVERRIDES.get(posix_code, _flag_emoji(locale.territory or ""))
        languages.append(
            Language(code=bcp47, name=locale.language_name, emoji=emoji),
        )
    return tuple(languages)


# English is the source language (no .mo file), so it is always present.
_EN_US_LOCALE: Final[Locale] = Locale.parse("en_US")
DEFAULT_LANGUAGE: Final[Language] = Language(
    code="en-US",
    name=_EN_US_LOCALE.language_name,
    emoji=_flag_emoji(_EN_US_LOCALE.territory or ""),
)

# Discovered at import time; add new languages by creating locale directories.
_DISCOVERED: Final[tuple[Language, ...]] = _discover_languages()


# Translation cache keyed by language code.
_translations: dict[str, gettext.GNUTranslations | gettext.NullTranslations] = {}


def _get_translation(
    lang_code: str,
) -> gettext.GNUTranslations | gettext.NullTranslations:
    """Return a cached gettext translation for *lang_code*."""
    if lang_code not in _translations:
        # BCP-47 (en-US) -> POSIX locale (en_US)
        locale_code = lang_code.replace("-", "_")
        _translations[lang_code] = gettext.translation(
            domain=DOMAIN,
            localedir=LOCALE_DIR,
            languages=[locale_code],
            fallback=True,
        )
    return _translations[lang_code]


def t(message: str) -> str:
    """Translate *message* using the current user's language.

    Falls back to the source string (English) when no translation is found or
    when called outside a NiceGUI request context.
    """
    try:
        lang_code: str = cast(
            "str",
            app.storage.user.get(LANGUAGE_KEY, DEFAULT_LANGUAGE.code),  # type: ignore[type-unknown]
        )
    except Exception:  # noqa: BLE001
        lang_code = DEFAULT_LANGUAGE.code
    return _get_translation(lang_code).gettext(message)


class LanguageManager:
    """Manages supported languages and user preferences."""

    @property
    def supported(self) -> frozenset[Language]:
        """Return the set of supported languages.

        Languages are auto-detected from locale directories under
        :data:`LOCALE_DIR`.  The default language is always included.
        """
        return frozenset((*_DISCOVERED, DEFAULT_LANGUAGE))

    @property
    def default(self) -> Language:
        """Return the default language."""
        return DEFAULT_LANGUAGE

    @property
    def browser_language(self) -> str | None:
        """Detect the user's preferred language from the browser settings."""
        if ui.context.client.request:
            supported_codes = {lang.code for lang in self.supported}
            for lang in ui.context.client.request.headers.get(
                "accept-language", ""
            ).split(","):
                if lang in supported_codes:
                    return lang
        return None

    @staticmethod
    def reload_if_changed(e: ValueChangeEventArguments) -> None:
        """Reload the page if the language has changed."""
        if e.value != e.previous_value:
            ui.notify(t("Language changed. Reloading."), type="info")
            ui.navigate.reload()

    def selector(self) -> Select:
        """Create a UI selector for choosing the language."""
        # Seed storage before creating the select so that bind_value does
        # not trigger a spurious on_change → reload on first page load.
        if LANGUAGE_KEY not in app.storage.user:  # type: ignore[operator]
            app.storage.user[LANGUAGE_KEY] = self.browser_language or self.default.code
        options = {
            lang.code: f"{lang.emoji} {lang.name}" if lang.emoji else lang.name
            for lang in sorted(self.supported, key=lambda lng: lng.code)
        }
        return ui.select(
            label=t("Language"),
            options=options,
            value=app.storage.user.get(LANGUAGE_KEY, self.default.code),  # type: ignore[type-unknown]
            on_change=self.reload_if_changed,
        ).bind_value(app.storage.user, LANGUAGE_KEY)


language_manager = LanguageManager()
