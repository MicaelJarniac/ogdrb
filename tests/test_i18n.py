"""Tests for i18n module."""
# ruff: noqa: D102

from __future__ import annotations

from ogdrb.i18n import (
    DEFAULT_LANGUAGE,
    Language,
    LanguageManager,
    _current_lang_code,
    _discover_languages,
    _flag_emoji,
    language_manager,
    t,
    territory_name,
)


class TestFlagEmoji:
    """Tests for _flag_emoji()."""

    def test_valid_country_code(self) -> None:
        result = _flag_emoji("US")
        assert result is not None
        assert result == "🇺🇸"

    def test_valid_country_code_lowercase(self) -> None:
        result = _flag_emoji("br")
        assert result is not None
        assert result == "🇧🇷"

    def test_empty_string(self) -> None:
        assert _flag_emoji("") is None

    def test_single_char(self) -> None:
        assert _flag_emoji("A") is None

    def test_three_chars(self) -> None:
        assert _flag_emoji("USA") is None

    def test_numeric(self) -> None:
        assert _flag_emoji("12") is None

    def test_non_ascii(self) -> None:
        assert _flag_emoji("ÁÉ") is None


class TestDiscoverLanguages:
    """Tests for _discover_languages()."""

    def test_discovers_pt_br(self) -> None:
        languages = _discover_languages()
        codes = {lang.code for lang in languages}
        assert "pt-BR" in codes

    def test_returns_language_tuples(self) -> None:
        languages = _discover_languages()
        assert len(languages) >= 1
        for lang in languages:
            assert isinstance(lang, Language)
            assert lang.code
            assert lang.name


class TestCurrentLangCode:
    """Tests for _current_lang_code()."""

    def test_fallback_outside_nicegui(self) -> None:
        """Without NiceGUI context, falls back to default."""
        result = _current_lang_code()
        assert result == DEFAULT_LANGUAGE.code


class TestTranslate:
    """Tests for t()."""

    def test_english_passthrough(self) -> None:
        """English strings pass through unchanged."""
        assert t("Hello") == "Hello"

    def test_unknown_string_passthrough(self) -> None:
        """Strings without translations return the source string."""
        assert t("this string has no translation") == "this string has no translation"


class TestTerritoryName:
    """Tests for territory_name()."""

    def test_english_fallback(self) -> None:
        """Outside NiceGUI context, returns English territory name."""
        name = territory_name("US")
        assert name == "United States"

    def test_known_fallback_code(self) -> None:
        """Babel-recognized codes return their English name."""
        assert territory_name("ZZ") == "Unknown Region"

    def test_brazil(self) -> None:
        name = territory_name("BR")
        assert name == "Brazil"


class TestLanguageManager:
    """Tests for LanguageManager."""

    def test_default_language(self) -> None:
        assert language_manager.default == DEFAULT_LANGUAGE
        assert language_manager.default.code == "en-US"

    def test_supported_includes_default(self) -> None:
        supported = language_manager.supported
        assert DEFAULT_LANGUAGE in supported

    def test_supported_includes_pt_br(self) -> None:
        supported = language_manager.supported
        codes = {lang.code for lang in supported}
        assert "pt-BR" in codes

    def test_supported_is_frozenset(self) -> None:
        assert isinstance(language_manager.supported, frozenset)

    def test_singleton(self) -> None:
        """language_manager is a module-level singleton."""
        assert isinstance(language_manager, LanguageManager)
