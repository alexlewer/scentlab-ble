"""Editable schedule times for ScentLab BLE."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
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
    """Set up start and end time entities for five schedule slots."""
    controller = entry.runtime_data
    async_add_entities(
        entity
        for slot in range(1, 6)
        for entity in (
            ScentLabScheduleTime(controller, slot, "start"),
            ScentLabScheduleTime(controller, slot, "end"),
        )
    )


class ScentLabScheduleTime(ScentLabScheduleEntity, TimeEntity):
    """Start or end time for one schedule."""

    _attr_icon = "mdi:clock-outline"

    def __init__(
        self, controller: ScentLabBleController, slot: int, kind: str
    ) -> None:
        super().__init__(controller, slot)
        self.kind = kind
        label = "Start Time" if kind == "start" else "End Time"
        self._attr_name = f"Schedule {slot} {label}"
        self._attr_unique_id = f"{controller.address}_schedule_{slot}_{kind}"

    @property
    def native_value(self) -> time | None:
        """Return the cached minute-of-day as a Home Assistant time."""
        if self.record is None:
            return None
        minutes = (
            self.record.start_minute
            if self.kind == "start"
            else self.record.stop_minute
        )
        return time(hour=minutes // 60, minute=minutes % 60)

    async def async_set_value(self, value: time) -> None:
        """Update one time while preserving the rest of the record."""
        minutes = value.hour * 60 + value.minute
        field = "start_minute" if self.kind == "start" else "stop_minute"
        await self.controller.async_update_schedule(self.slot, **{field: minutes})
