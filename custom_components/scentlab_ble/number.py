"""Editable spray and pause durations for ScentLab BLE."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .controller import ScentLabBleController
from .entity import ScentLabScheduleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up spray and pause duration entities for five schedule slots."""
    controller = entry.runtime_data
    async_add_entities(
        entity
        for slot in range(1, 6)
        for entity in (
            ScentLabScheduleDuration(controller, slot, "spray"),
            ScentLabScheduleDuration(controller, slot, "pause"),
        )
    )


class ScentLabScheduleDuration(ScentLabScheduleEntity, NumberEntity):
    """Spray or pause duration for one schedule."""

    _attr_native_min_value = 0
    _attr_native_max_value = 65535
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.BOX

    def __init__(
        self, controller: ScentLabBleController, slot: int, kind: str
    ) -> None:
        super().__init__(controller, slot)
        self.kind = kind
        self._attr_icon = "mdi:spray" if kind == "spray" else "mdi:timer-pause"
        self._attr_name = f"Schedule {slot} {kind} duration"
        self._attr_unique_id = f"{controller.address}_schedule_{slot}_{kind}"

    @property
    def native_value(self) -> float | None:
        """Return the cached duration in seconds."""
        if self.record is None:
            return None
        value = (
            self.record.run_seconds
            if self.kind == "spray"
            else self.record.pause_seconds
        )
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Update one duration while preserving the rest of the record."""
        field = "run_seconds" if self.kind == "spray" else "pause_seconds"
        await self.controller.async_update_schedule(
            self.slot, **{field: int(value)}
        )
