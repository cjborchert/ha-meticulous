"""Config flow for Meticulous Espresso integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from .connection import async_discover_api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def _validate_connection(
    hass, host: str, preferred_port: int | None = None
) -> dict[str, Any] | None:
    """Validate we can connect to the machine. Returns device info or None.

    The port is auto-detected: older firmware serves the API on 8080, newer
    firmware proxies it on port 80.
    """
    try:
        found = await async_discover_api(hass, host, preferred_port)
    except Exception:
        return None

    if not found:
        return None

    port, result = found

    return {
        "serial": getattr(result, "serial", "meticulous"),
        "name": getattr(result, "name", "Meticulous Espresso"),
        "model": getattr(result, "model", "Espresso"),
        "port": port,
    }


class MeticulousConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meticulous Espresso."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host: str | None = None
        self._port: int | None = None
        self._serial: str | None = None
        self._name: str = "Meticulous Espresso"

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery of _meticulous._tcp.local."""
        host = str(discovery_info.host)
        advertised_port = getattr(discovery_info, "port", None)
        _LOGGER.info("Discovered Meticulous machine at %s via Zeroconf", host)

        # Validate and get device info (port auto-detected, advertised port first)
        info = await _validate_connection(self.hass, host, advertised_port)
        if not info:
            return self.async_abort(reason="cannot_connect")

        serial = info["serial"]
        self._host = host
        self._port = info["port"]
        self._serial = serial
        self._name = info["name"]

        # Set unique ID and update host if already configured (handles DHCP changes)
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host, CONF_PORT: info["port"]}
        )

        # Show confirmation to user
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Zeroconf discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={CONF_HOST: self._host, CONF_PORT: self._port},
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._name, "host": self._host},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup via UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            info = await _validate_connection(self.hass, host)
            if info:
                serial = info["serial"]
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["name"],
                    data={CONF_HOST: host, CONF_PORT: info["port"]},
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration (e.g., IP change)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            info = await _validate_connection(self.hass, host)
            if info:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates={CONF_HOST: host, CONF_PORT: info["port"]},
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
