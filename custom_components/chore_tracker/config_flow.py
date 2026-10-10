"""Config flow for Chore Tracker."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from . import DOMAIN


class ChoreTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Chore Tracker."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Add the integration through the Home Assistant UI."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Chore Tracker", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )
