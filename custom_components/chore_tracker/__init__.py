"""Chore Tracker - track household chore minutes for children."""
from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

DOMAIN = "chore_tracker"
STORAGE_KEY = "chore_tracker.data"
STORAGE_VERSION = 1

JS_FILENAME = "chore-tracker-card.js"
JS_VERSION = "5"

SERVICE_ADD_ENTRY = "add_entry"
SERVICE_RESET_CHILD = "reset_child"

ATTR_CHILD = "child"
ATTR_MINUTES = "minutes"
ATTR_NOTE = "note"

ADD_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CHILD): cv.string,
        vol.Required(ATTR_MINUTES): vol.Coerce(int),
        vol.Optional(ATTR_NOTE, default=""): cv.string,
    }
)

RESET_CHILD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CHILD): cv.string,
    }
)


def _install_card(hass: HomeAssistant) -> None:
    """Copy the Lovelace card JS into config/www and register it as a resource."""
    src = Path(__file__).parent / JS_FILENAME
    www_dir = Path(hass.config.config_dir) / "www"
    www_dir.mkdir(exist_ok=True)
    dst = www_dir / JS_FILENAME
    shutil.copy2(src, dst)
    _LOGGER.debug("Installed %s -> %s", src, dst)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Chore Tracker component."""

    # Install / update the card JS file
    await hass.async_add_executor_job(_install_card, hass)

    # Auto-register the Lovelace resource so users don't have to do it manually
    await _ensure_lovelace_resource(hass)

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {"children": {}}
    hass.data[DOMAIN] = {"store": store, "data": data}

    async def _save():
        await store.async_save(hass.data[DOMAIN]["data"])

    async def handle_add_entry(call: ServiceCall) -> None:
        child = call.data[ATTR_CHILD].strip()
        minutes = call.data[ATTR_MINUTES]
        note = call.data.get(ATTR_NOTE, "")

        children = hass.data[DOMAIN]["data"].setdefault("children", {})
        if child not in children:
            children[child] = {"entries": [], "total_minutes": 0}

        entry = {
            "minutes": minutes,
            "note": note,
            "timestamp": datetime.now().isoformat(),
        }
        children[child]["entries"].append(entry)
        children[child]["total_minutes"] = sum(
            e["minutes"] for e in children[child]["entries"]
        )
        await _save()
        hass.bus.async_fire(f"{DOMAIN}_updated", {"child": child})
        _LOGGER.info("Added %d min for %s (%s)", minutes, child, note)

    async def handle_reset_child(call: ServiceCall) -> None:
        child = call.data[ATTR_CHILD].strip()
        children = hass.data[DOMAIN]["data"].setdefault("children", {})
        if child in children:
            children[child] = {"entries": [], "total_minutes": 0}
            await _save()
            hass.bus.async_fire(f"{DOMAIN}_updated", {"child": child})
            _LOGGER.info("Reset entries for %s", child)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_ENTRY, handle_add_entry, schema=ADD_ENTRY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_CHILD, handle_reset_child, schema=RESET_CHILD_SCHEMA
    )

    # Register WebSocket command so the Lovelace card can fetch data
    @websocket_api.websocket_command({"type": f"{DOMAIN}/get_data"})
    @websocket_api.async_response
    async def ws_get_data(hass, connection, msg):
        data = hass.data.get(DOMAIN, {}).get("data", {"children": {}})
        connection.send_result(msg["id"], data)

    websocket_api.async_register_command(hass, ws_get_data)

    return True


async def _ensure_lovelace_resource(hass: HomeAssistant) -> None:
    """Add the card JS as a Lovelace resource if not already registered."""
    url = f"/local/{JS_FILENAME}?v={JS_VERSION}"
    resources_store = Store(hass, 1, "lovelace_resources")
    data = await resources_store.async_load() or {"items": []}
    items = data.setdefault("items", [])

    # Remove any outdated entry for this file, then add the current versioned one
    items[:] = [i for i in items if JS_FILENAME not in i.get("url", "")]
    items.append({"id": DOMAIN, "type": "module", "url": url})

    await resources_store.async_save(data)
    _LOGGER.debug("Lovelace resource registered: %s", url)
