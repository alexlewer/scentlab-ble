"""ScentLab BLE Diffuser integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_PASSWORD
from .controller import ScentLabBleController

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.NUMBER, Platform.SWITCH, Platform.TIME]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a ScentLab BLE diffuser from a config entry."""
    controller = entry.runtime_data = ScentLabBleController(
        hass,
        entry.data[CONF_ADDRESS],
        entry.data[CONF_NAME],
        entry.data.get(CONF_PASSWORD, ""),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    try:
        await controller.async_refresh_schedules()
    except HomeAssistantError as err:
        # Power control remains usable and the user can retry with the refresh button.
        _LOGGER.debug("Initial schedule refresh failed: %s", err)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a ScentLab BLE config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
