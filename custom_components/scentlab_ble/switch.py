"""Switch platform for ScentLab BLE Diffuser."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .controller import ScentLabBleController
from .entity import ScentLabScheduleEntity, device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ScentLab BLE switch."""
    controller = entry.runtime_data
    async_add_entities(
        [ScentLabPowerSwitch(controller), ScentLabNightlightSwitch(controller)]
        + [ScentLabScheduleSwitch(controller, slot) for slot in range(1, 6)]
    )


class ScentLabPowerSwitch(SwitchEntity, RestoreEntity):
    """Optimistic power switch for a ScentLab diffuser."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_assumed_state = True
    _attr_icon = "mdi:scent"

    def __init__(self, controller: ScentLabBleController) -> None:
        self._controller = controller
        self._attr_unique_id = f"{controller.address}_power"
        self._attr_device_info = device_info(controller)

    @property
    def available(self) -> bool:
        """Return whether a connectable adapter can currently see the diffuser."""
        return bluetooth.async_address_present(
            self.hass, self._controller.address, connectable=True
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last optimistic state after restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs: object) -> None:
        """Turn the diffuser on."""
        await self._controller.async_set_power(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn the diffuser off."""
        await self._controller.async_set_power(False)
        self._attr_is_on = False
        self.async_write_ha_state()


class ScentLabNightlightSwitch(SwitchEntity, RestoreEntity):
    """Optimistic switch for APK light mode 2."""

    _attr_has_entity_name = True
    _attr_name = "Nightlight"
    _attr_assumed_state = True
    _attr_icon = "mdi:lightbulb-night"

    def __init__(self, controller: ScentLabBleController) -> None:
        self._controller = controller
        self._attr_unique_id = f"{controller.address}_nightlight"
        self._attr_device_info = device_info(controller)

    @property
    def available(self) -> bool:
        """Return whether a connectable adapter can currently see the diffuser."""
        return bluetooth.async_address_present(
            self.hass, self._controller.address, connectable=True
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last optimistic state after restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable APK light mode 2."""
        await self._controller.async_set_nightlight(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn the light off."""
        await self._controller.async_set_nightlight(False)
        self._attr_is_on = False
        self.async_write_ha_state()


class ScentLabScheduleSwitch(ScentLabScheduleEntity, SwitchEntity):
    """Enable or disable one independent diffuser schedule slot."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, controller: ScentLabBleController, slot: int) -> None:
        super().__init__(controller, slot)
        self._attr_name = f"Schedule {slot}"
        self._attr_unique_id = f"{controller.address}_schedule_{slot}_enabled"

    @property
    def is_on(self) -> bool | None:
        """Return the cached enable flag."""
        return self.record.enabled if self.record is not None else None

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable this schedule without changing its other fields."""
        await self.controller.async_update_schedule(self.slot, enabled=True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable this schedule without changing its other fields."""
        await self.controller.async_update_schedule(self.slot, enabled=False)
