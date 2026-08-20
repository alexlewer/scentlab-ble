"""Config flow for ScentLab BLE Diffuser."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import CONF_PASSWORD, DOMAIN


def _normalise_address(address: str) -> str:
    """Normalise the usual colon- or dash-separated MAC representation."""
    return address.strip().replace("-", ":").upper()


def _valid_password(password: str) -> bool:
    """Return whether an optional application password is valid."""
    if not password:
        return True
    try:
        return len(password) == 4 and len(password.encode("ascii")) == 4
    except UnicodeEncodeError:
        return False


class ScentLabBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure a ScentLab BLE diffuser."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = _normalise_address(user_input[CONF_ADDRESS])
            password = user_input.get(CONF_PASSWORD, "")
            if re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address) is None:
                errors[CONF_ADDRESS] = "invalid_address"
            elif not _valid_password(password):
                errors[CONF_PASSWORD] = "invalid_password"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_ADDRESS: address,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="Scent Diffuser"): str,
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        self._discovery_info = discovery_info
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered diffuser."""
        assert self._discovery_info is not None
        name = self._discovery_info.name or "Scent Diffuser"
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD, "")
            if not _valid_password(password):
                return self.async_show_form(
                    step_id="bluetooth_confirm",
                    data_schema=vol.Schema(
                        {vol.Optional(CONF_PASSWORD, default=password): str}
                    ),
                    errors={CONF_PASSWORD: "invalid_password"},
                    description_placeholders={"name": name},
                )
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_NAME: name,
                    CONF_PASSWORD: password,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD, default=""): str}),
            description_placeholders={"name": name},
        )
