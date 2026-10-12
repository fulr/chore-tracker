"""Integration tests for Chore Tracker."""

from datetime import datetime

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chore_tracker import DOMAIN


async def test_user_config_flow_creates_entry_and_services(
    hass: HomeAssistant,
) -> None:
    """The UI flow creates a working config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Chore Tracker"
    assert result["data"] == {}
    assert hass.services.has_service(DOMAIN, "add_entry")
    assert hass.services.has_service(DOMAIN, "reset_child")

    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert duplicate["type"] == FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


async def test_add_entry_persists_data_and_fires_update_event(
    hass: HomeAssistant,
) -> None:
    """Adding a chore entry updates data, persistence, and listeners."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    events: list[dict[str, str]] = []
    hass.bus.async_listen(
        f"{DOMAIN}_updated", lambda event: events.append(event.data)
    )

    await hass.services.async_call(
        DOMAIN,
        "add_entry",
        {"child": "  Sofia  ", "minutes": "12", "note": "Tisch gedeckt"},
        blocking=True,
    )

    child = hass.data[DOMAIN]["data"]["children"]["Sofia"]
    assert child["total_minutes"] == 12
    assert child["entries"][0]["minutes"] == 12
    assert child["entries"][0]["note"] == "Tisch gedeckt"
    datetime.fromisoformat(child["entries"][0]["timestamp"])
    stored_data = await hass.data[DOMAIN]["store"].async_load()
    assert stored_data == hass.data[DOMAIN]["data"]

    await hass.async_block_till_done()
    assert events == [{"child": "Sofia"}]


async def test_reset_child_clears_entries_and_persists(
    hass: HomeAssistant,
) -> None:
    """Resetting a child clears its history and total in Home Assistant storage."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "add_entry",
        {"child": "Sofia", "minutes": 12},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "reset_child",
        {"child": " Sofia "},
        blocking=True,
    )

    child = hass.data[DOMAIN]["data"]["children"]["Sofia"]
    assert child == {"entries": [], "total_minutes": 0}
    stored_data = await hass.data[DOMAIN]["store"].async_load()
    assert stored_data == hass.data[DOMAIN]["data"]


async def test_get_data_websocket_returns_stored_data(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """The card's WebSocket command returns the persisted child data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "add_entry",
        {"child": "Sofia", "minutes": 12, "note": "Tisch gedeckt"},
        blocking=True,
    )

    client = await hass_ws_client()
    await client.send_json({"id": 1, "type": f"{DOMAIN}/get_data"})
    response = await client.receive_json()

    assert response["success"] is True
    child = response["result"]["children"]["Sofia"]
    assert child["total_minutes"] == 12
    assert child["entries"][0]["note"] == "Tisch gedeckt"
