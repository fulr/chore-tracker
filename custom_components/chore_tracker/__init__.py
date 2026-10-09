"""Chore Tracker - track household chore minutes for children."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

DOMAIN = "chore_tracker"
STORAGE_KEY = "chore_tracker.data"
STORAGE_VERSION = 1

JS_FILENAME = "chore-tracker-card.js"
JS_VERSION = "10"
JS_URL = f"/{DOMAIN}/{JS_FILENAME}"
JS_URL_VERSIONED = f"{JS_URL}?v={JS_VERSION}"

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


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Chore Tracker component."""

    # Serve the JS file directly from the integration folder
    js_path = str(Path(__file__).parent / JS_FILENAME)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(JS_URL, js_path, cache_headers=False)]
    )

    async def _register_frontend(_=None) -> None:
        """Register JS with the frontend and Lovelace once frontend is ready."""

        # add_extra_js_url injects it on every page load (works in YAML mode + Cast)
        add_extra_js_url(hass, JS_URL_VERSIONED)

        # Also register as a persisted Lovelace resource (shows in add-card picker)
        try:
            lovelace = hass.data.get("lovelace")
            if lovelace is None:
                _LOGGER.warning("Lovelace not in hass.data, skipping resource registration")
                return

            resources = (
                lovelace.resources
                if hasattr(lovelace, "resources")
                else lovelace.get("resources")
            )
            if resources is None:
                return

            # Load storage before reading or writing to avoid overwriting other
            # integrations' resources with an empty in-memory collection
            if not resources.loaded:
                await resources.async_load()
                resources.loaded = True

            all_items = list(resources.async_items())

            # Remove stale entries from old installation paths (e.g. /local/)
            if isinstance(resources, ResourceStorageCollection):
                for item in all_items:
                    url = item.get("url", "")
                    if JS_FILENAME in url and JS_URL not in url:
                        await resources.async_delete_item(item["id"])
                        _LOGGER.debug("Removed stale resource: %s", url)

            # Find current-path entry
            current = next(
                (i for i in all_items if JS_URL in i.get("url", "")), None
            )

            if current is None:
                if isinstance(resources, ResourceStorageCollection):
                    await resources.async_create_item(
                        {"res_type": "module", "url": JS_URL_VERSIONED}
                    )
                    _LOGGER.info("Registered Lovelace resource: %s", JS_URL_VERSIONED)
                else:
                    _LOGGER.info(
                        "YAML mode: add manually — url: %s, type: module",
                        JS_URL_VERSIONED,
                    )
            elif current["url"] == JS_URL_VERSIONED:
                _LOGGER.debug("Resource already current: %s", JS_URL_VERSIONED)
            else:
                if isinstance(resources, ResourceStorageCollection):
                    await resources.async_update_item(
                        current["id"],
                        {"res_type": "module", "url": JS_URL_VERSIONED},
                    )
                    _LOGGER.info("Updated Lovelace resource: %s", JS_URL_VERSIONED)
                else:
                    current["url"] = JS_URL_VERSIONED

        except Exception as err:
            _LOGGER.error("Failed to register Lovelace resource: %s", err)

    if hass.is_running:
        hass.async_create_task(_register_frontend())
    else:
        hass.bus.async_listen_once("homeassistant_started", _register_frontend)

    # Data store
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

    @websocket_api.websocket_command({"type": f"{DOMAIN}/get_data"})
    @websocket_api.async_response
    async def ws_get_data(hass, connection, msg):
        data = hass.data.get(DOMAIN, {}).get("data", {"children": {}})
        connection.send_result(msg["id"], data)

    websocket_api.async_register_command(hass, ws_get_data)

    return True
