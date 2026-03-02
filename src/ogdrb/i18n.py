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

translation = gettext.translation(
    domain="ogdrb",
    localedir=Path(__file__).parent / "locales",
    fallback=True,
)
t = translation.gettext


LANGUAGE_KEY: Final[str] = "language"


class Language(NamedTuple):
    """Represents a supported language."""

    code: str
    name: str
    emoji: str | None = None


EN_US_CODE = "en-US"

EN_US = Language(
    code=EN_US_CODE,
    name=Locale.parse(EN_US_CODE, sep="-").display_name,
    emoji="🇺🇸",
)


class LanguageManager:
    """Manages supported languages and user preferences."""

    @property
    def supported(self) -> set[Language]:
        """Return the set of supported languages."""
        return {
            EN_US,
        }

    @property
    def default(self) -> Language:
        """Return the default language."""
        return EN_US

    @property
    def browser_language(self) -> str | None:
        """Detect the user's preferred language from the browser settings."""
        if ui.context.client.request:
            for lang in ui.context.client.request.headers.get(
                "accept-language", ""
            ).split(","):
                supported_codes = {lang.code for lang in self.supported}
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
        return ui.select(
            label=t("Language"),
            options={
                lang.code: f"{lang.emoji} {lang.name}" if lang.emoji else lang.name
                for lang in language_manager.supported
            },
            value=language_manager.browser_language or language_manager.default.code,
            on_change=self.reload_if_changed,
        ).bind_value(app.storage.user, LANGUAGE_KEY)


language_manager = LanguageManager()
