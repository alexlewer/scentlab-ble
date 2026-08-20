"""Shared schedule entity support for ScentLab BLE."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import ScheduleRecord, ScentLabBleController


def device_info(controller: ScentLabBleController) -> DeviceInfo:
    """Return the shared Home Assistant device information."""
    return DeviceInfo(
        identifiers={(DOMAIN, controller.address)},
        connections={(CONNECTION_BLUETOOTH, controller.address)},
        manufacturer="ScentLab / YooAI",
        model="B04P BLE diffuser",
        name=controller.name,
    )


class ScentLabScheduleEntity(Entity):
    """Base for one property of one cached schedule record."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: ScentLabBleController, slot: int) -> None:
        self.controller = controller
        self.slot = slot
        self._attr_device_info = device_info(controller)

    @property
    def record(self) -> ScheduleRecord | None:
        """Return the cached record without performing Bluetooth I/O."""
        return self.controller.schedules.get(self.slot)

    @property
    def available(self) -> bool:
        """Return whether the record is loaded and the diffuser is present."""
        return self.record is not None and bluetooth.async_address_present(
            self.hass, self.controller.address, connectable=True
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to shared schedule-cache changes."""
        await super().async_added_to_hass()
        self.async_on_remove(self.controller.add_listener(self._schedule_updated))

    def _schedule_updated(self) -> None:
        """Publish a state calculated from the refreshed cache."""
        self.async_write_ha_state()
