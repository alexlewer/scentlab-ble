"""Manual schedule refresh button for ScentLab BLE."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .controller import ScentLabBleController
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the schedule refresh button."""
    async_add_entities(
        [
            ScentLabRefreshSchedulesButton(entry.runtime_data),
            ScentLabSynchroniseTimeButton(entry.runtime_data),
        ]
    )


class ScentLabRefreshSchedulesButton(ButtonEntity):
    """Refresh all cached schedule records from the diffuser."""

    _attr_has_entity_name = True
    _attr_name = "Refresh schedules"
    _attr_icon = "mdi:calendar-sync"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: ScentLabBleController) -> None:
        self.controller = controller
        self._attr_unique_id = f"{controller.address}_refresh_schedules"
        self._attr_device_info = device_info(controller)

    @property
    def available(self) -> bool:
        """Return whether a connectable adapter can see the diffuser."""
        return bluetooth.async_address_present(
            self.hass, self.controller.address, connectable=True
        )

    async def async_press(self) -> None:
        """Read every schedule and update all schedule entities."""
        await self.controller.async_refresh_schedules()


class ScentLabSynchroniseTimeButton(ButtonEntity):
    """Synchronise the diffuser's internal clock."""

    _attr_has_entity_name = True
    _attr_name = "Synchronise time"
    _attr_icon = "mdi:clock-sync"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: ScentLabBleController) -> None:
        self.controller = controller
        self._attr_unique_id = f"{controller.address}_synchronise_time"
        self._attr_device_info = device_info(controller)

    @property
    def available(self) -> bool:
        """Return whether a connectable adapter can see the diffuser."""
        return bluetooth.async_address_present(
            self.hass, self.controller.address, connectable=True
        )

    async def async_press(self) -> None:
        """Set the diffuser clock to Home Assistant's local date and time."""
        await self.controller.async_sync_time()
