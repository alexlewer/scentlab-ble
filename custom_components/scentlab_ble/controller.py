"""BLE controller for ScentLab diffusers."""

from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CHARACTERISTIC_UUID, POWER_OFF_FRAME, POWER_ON_FRAME

_LOGGER = logging.getLogger(__name__)


def _build_frame(command: int, data: bytes = b"") -> bytes:
    """Build a standard ScentLab 55 AA packet."""
    body = bytes((0x55, 0xAA, len(data) + 1, command)) + data
    checksum = (-sum(body)) & 0xFF
    return body + bytes((checksum, 0x5A))


def _password_frame(password: str) -> bytes:
    """Build the four-character application-password frame."""
    encoded = password.encode("ascii")
    if len(encoded) != 4:
        raise HomeAssistantError(
            "The ScentLab application password must be exactly four ASCII characters"
        )
    return _build_frame(0x48, bytes((4,)) + encoded)


class ScentLabBleController:
    """Connect, authenticate when configured, write, and disconnect."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        password: str = "",
    ) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self.password = password
        self._lock = asyncio.Lock()

    async def async_set_power(self, enabled: bool) -> None:
        """Set diffuser power."""
        async with self._lock:
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                raise HomeAssistantError(
                    f"{self.name} ({self.address}) is not currently reachable by a "
                    "connectable Home Assistant Bluetooth adapter"
                )

            client: BleakClientWithServiceCache | None = None
            try:
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self.name,
                    max_attempts=3,
                )

                # ScentLab's application password is separate from BLE pairing.
                # If configured, submit it once for this connection before control.
                if self.password:
                    await client.write_gatt_char(
                        CHARACTERISTIC_UUID,
                        _password_frame(self.password),
                        response=False,
                    )
                    await asyncio.sleep(0.15)

                await client.write_gatt_char(
                    CHARACTERISTIC_UUID,
                    POWER_ON_FRAME if enabled else POWER_OFF_FRAME,
                    response=False,
                )
                _LOGGER.debug(
                    "Sent power %s to %s", "on" if enabled else "off", self.address
                )
            except (BleakError, TimeoutError) as err:
                raise HomeAssistantError(
                    f"Failed to control {self.name} over Bluetooth: {err}"
                ) from err
            finally:
                if client is not None and client.is_connected:
                    try:
                        await client.disconnect()
                    except BleakError as err:
                        _LOGGER.debug("Error disconnecting from %s: %s", self.address, err)
