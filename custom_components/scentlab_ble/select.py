"""Editable weekday selections for ScentLab BLE schedules."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .controller import ScentLabBleController
from .entity import ScentLabScheduleEntity

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
SPECIAL_DAY_LABELS = {
    0x00: "No days",
    0x1F: "Weekdays (Mon–Fri)",
    0x60: "Weekends (Sat, Sun)",
    0x7F: "Every day",
}


def _day_label(mask: int) -> str:
    """Return a concise label for one seven-bit weekday mask."""
    if mask in SPECIAL_DAY_LABELS:
        return SPECIAL_DAY_LABELS[mask]
    return ", ".join(
        name for bit, name in enumerate(DAY_NAMES) if mask & (1 << bit)
    )


_COMMON_MASKS = (0x7F, 0x1F, 0x60, 0x00)
_OTHER_MASKS = tuple(
    sorted(
        (mask for mask in range(0x80) if mask not in _COMMON_MASKS),
        key=lambda mask: (mask.bit_count(), mask),
    )
)
DAY_MASKS = _COMMON_MASKS + _OTHER_MASKS
DAY_OPTIONS = [_day_label(mask) for mask in DAY_MASKS]
OPTION_TO_MASK = dict(zip(DAY_OPTIONS, DAY_MASKS))
MASK_TO_OPTION = dict(zip(DAY_MASKS, DAY_OPTIONS))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up weekday selectors for five schedule slots."""
    controller = entry.runtime_data
    async_add_entities(
        ScentLabScheduleDaysSelect(controller, slot) for slot in range(1, 6)
    )


class ScentLabScheduleDaysSelect(ScentLabScheduleEntity, SelectEntity):
    """Select the active weekdays for one schedule."""

    _attr_icon = "mdi:calendar-week"
    _attr_options = DAY_OPTIONS

    def __init__(self, controller: ScentLabBleController, slot: int) -> None:
        super().__init__(controller, slot)
        self._attr_name = f"Schedule {slot} Days"
        self._attr_unique_id = f"{controller.address}_schedule_{slot}_days"

    @property
    def current_option(self) -> str | None:
        """Return the selected days from the cached protocol record."""
        if self.record is None:
            return None
        return MASK_TO_OPTION[self.record.weekdays & 0x7F]

    async def async_select_option(self, option: str) -> None:
        """Update the weekday mask while preserving every other timer field."""
        if option not in OPTION_TO_MASK:
            raise HomeAssistantError(f"Unknown schedule day selection: {option}")
        mask = OPTION_TO_MASK[option]
        # Bit 7 is the APK's marker that at least one weekday is selected.
        weekdays = mask | (0x80 if mask else 0)
        await self.controller.async_update_schedule(self.slot, weekdays=weekdays)
