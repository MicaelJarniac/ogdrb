"""Tests for the OGDRB app."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from nicegui import ui

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from nicegui.testing import User


SELECT_COUNTRIES_LABEL = "Select countries"
SELECT_US_STATES_LABEL = "Select US states"
UNITED_STATES_LABEL = "United States"
CANADA_LABEL = "Canada"
LOAD_REPEATERS_LABEL = "Load Repeaters"
EXPORT_LABEL = "Export"


@pytest.fixture(autouse=True)
async def _mock_run_javascript() -> AsyncGenerator[None]:
    """Mock ``ui.run_javascript`` so the page renders fully without a JS engine."""
    with patch("nicegui.ui.run_javascript", new_callable=AsyncMock, return_value=None):
        yield


async def test_initial_page_elements(user: User) -> None:
    """Test that the page loads with expected elements visible."""
    await user.open("/")
    await user.should_see("OGDRB")
    await user.should_see(SELECT_COUNTRIES_LABEL)
    await user.should_not_see(SELECT_US_STATES_LABEL)
    await user.should_see(LOAD_REPEATERS_LABEL)
    await user.should_see(EXPORT_LABEL)
    await user.should_see("New zone")
    await user.should_see("Delete selected zones")


async def test_us_country_selection(user: User) -> None:
    """Test that selecting USA shows the state selection.

    Test that selecting USA shows the state selection and that it is hidden when USA is
    deselected.
    """
    await user.open("/")
    await user.should_see(SELECT_COUNTRIES_LABEL)
    await user.should_not_see(SELECT_US_STATES_LABEL)
    user.find(SELECT_COUNTRIES_LABEL).click()
    await user.should_see(UNITED_STATES_LABEL)
    user.find(UNITED_STATES_LABEL).click()
    await user.should_see(SELECT_US_STATES_LABEL)


async def test_us_states_hidden_on_deselect(user: User) -> None:
    """Test that deselecting USA hides the state selection."""
    await user.open("/")
    # Select US
    user.find(SELECT_COUNTRIES_LABEL).click()
    await user.should_see(UNITED_STATES_LABEL)
    user.find(UNITED_STATES_LABEL).click()
    await user.should_see(SELECT_US_STATES_LABEL)
    # Deselect US
    user.find(UNITED_STATES_LABEL).click()
    await user.should_not_see(SELECT_US_STATES_LABEL)


async def test_validation_no_country_load_repeaters(user: User) -> None:
    """Test that loading repeaters without selecting a country shows a warning."""
    await user.open("/")
    user.find(LOAD_REPEATERS_LABEL).click()
    await asyncio.sleep(0.1)
    assert user.notify.contains("Please select at least one country")


async def test_validation_no_country_export(user: User) -> None:
    """Test that exporting without selecting a country shows a warning."""
    await user.open("/")
    user.find(EXPORT_LABEL).click()
    await asyncio.sleep(0.1)
    assert user.notify.contains("Please select at least one country")


async def test_validation_us_no_states_export(user: User) -> None:
    """Test that exporting with US selected but no states shows a warning."""
    await user.open("/")
    # Select US
    user.find(SELECT_COUNTRIES_LABEL).click()
    await user.should_see(UNITED_STATES_LABEL)
    user.find(UNITED_STATES_LABEL).click()
    await user.should_see(SELECT_US_STATES_LABEL)
    # Export without selecting states
    user.find(EXPORT_LABEL).click()
    await asyncio.sleep(0.1)
    assert user.notify.contains("Please select at least one US state")


async def test_validation_no_zones_export(user: User) -> None:
    """Test that exporting without zones shows a warning."""
    await user.open("/")
    # Select Canada (non-US, no state selection needed)
    user.find(SELECT_COUNTRIES_LABEL).click()
    await user.should_see(CANADA_LABEL)
    user.find(CANADA_LABEL).click()
    # Export without any zones
    user.find(EXPORT_LABEL).click()
    await asyncio.sleep(0.1)
    assert user.notify.contains("Please add at least one zone")


async def test_help_dialog_opens_and_closes(user: User) -> None:
    """Test that the help dialog opens and closes via its value property."""
    await user.open("/")
    # Dialog starts closed
    dialog = next(iter(user.find(kind=ui.dialog).elements))
    assert not dialog.value
    # Open dialog via help FAB
    user.find(marker="help-btn").click()
    assert dialog.value
    # Close dialog
    user.find("Close").click()
    assert not dialog.value


async def test_footer_content(user: User) -> None:
    """Test that footer contains expected links and text."""
    await user.open("/")
    await user.should_see("OGDRB by MicaelJarniac")
