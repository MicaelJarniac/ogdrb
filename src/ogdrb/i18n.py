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


class Language(NamedTuple):
    """Represents a supported language."""

    code: str
    name: str
    emoji: str | None = None


EN_US_CODE = "en-US"
PT_BR_CODE = "pt-BR"

EN_US = Language(
    code=EN_US_CODE,
    name=Locale.parse(EN_US_CODE, sep="-").language_name,
    emoji="\U0001f1fa\U0001f1f8",
)

PT_BR = Language(
    code=PT_BR_CODE,
    name=Locale.parse(PT_BR_CODE, sep="-").language_name,
    emoji="\U0001f1e7\U0001f1f7",
)


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
            app.storage.user.get(LANGUAGE_KEY, EN_US_CODE),  # type: ignore[type-unknown]
        )
    except Exception:  # noqa: BLE001
        lang_code = EN_US_CODE
    return _get_translation(lang_code).gettext(message)


class LanguageManager:
    """Manages supported languages and user preferences."""

    @property
    def supported(self) -> set[Language]:
        """Return the set of supported languages."""
        return {
            EN_US,
            PT_BR,
        }

    @property
    def default(self) -> Language:
        """Return the default language."""
        return EN_US

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

    @property
    def current(self) -> str:
        """Return the current language code for the user."""
        return cast("str", app.storage.user.get(LANGUAGE_KEY, EN_US.code))  # type: ignore[type-unknown]

    @current.setter
    def current(self, code: str) -> None:
        """Set the current language code for the user."""
        app.storage.user[LANGUAGE_KEY] = code

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
