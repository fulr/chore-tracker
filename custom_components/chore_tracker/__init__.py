"""Chore Tracker - track household chore minutes for children."""
from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

DOMAIN = "chore_tracker"
STORAGE_KEY = "chore_tracker.data"
STORAGE_VERSION = 1

JS_FILENAME = "chore-tracker-card.js"
JS_VERSION = "7"
JS_URL = f"/local/{JS_FILENAME}?v={JS_VERSION}"

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
    """Copy the Lovelace card JS into config/www."""
    src = Path(__file__).parent / JS_FILENAME
    www_dir = Path(hass.config.config_dir) / "www"
    www_dir.mkdir(exist_ok=True)
    dst = www_dir / JS_FILENAME
    shutil.copy2(src, dst)
    _LOGGER.debug("Installed %s -> %s", src, dst)


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    """Register the card JS via the live Lovelace resource collection."""
    try:
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is None:
            _LOGGER.warning("Lovelace not loaded, cannot register resource")
            return

        resource_collection = lovelace_data.resources

        # Only ResourceStorageCollection supports mutations
        from homeassistant.components.lovelace.resources import ResourceStorageCollection
        if not isinstance(resource_collection, ResourceStorageCollection):
            _LOGGER.debug("Lovelace in YAML mode, skipping resource registration")
            return

        await resource_collection._async_ensure_loaded()

        # Remove outdated entries for this JS file
        for item in list(resource_collection.async_items()):
            if JS_FILENAME in item.get("url", ""):
                if item["url"] == JS_URL:
                    _LOGGER.debug("Resource already registered: %s", JS_URL)
                    return
                await resource_collection.async_delete_item(item["id"])
                _LOGGER.debug("Removed outdated resource: %s", item["url"])

        # Register the current version
        await resource_collection.async_create_item(
            {"res_type": "module", "url": JS_URL}
        )
        _LOGGER.info("Lovelace resource registered: %s", JS_URL)

    except Exception as err:
        _LOGGER.error("Failed to register Lovelace resource: %s", err)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Chore Tracker component."""

    # Copy the JS file into www/
    await hass.async_add_executor_job(_install_card, hass)

    # Register resource once Lovelace has finished setting up
    @callback
    def _on_lovelace_loaded(_now=None):
        hass.async_create_task(_register_lovelace_resource(hass))

    if hass.is_running:
        _on_lovelace_loaded()
    else:
        hass.bus.async_listen_once("homeassistant_started", _on_lovelace_loaded)

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
