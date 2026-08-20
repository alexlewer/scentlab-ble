"""BLE controller for ScentLab diffusers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
import logging

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakOutOfConnectionSlotsError,
    clear_cache,
    close_stale_connections_by_address,
    establish_connection,
    wait_for_device_to_reappear,
)

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CHARACTERISTIC_UUID,
    NIGHTLIGHT_OFF_FRAME,
    NIGHTLIGHT_ON_FRAME,
    POWER_OFF_FRAME,
    POWER_ON_FRAME,
)

_LOGGER = logging.getLogger(__name__)

TIMER_RECORD_SIZE = 16
TIMER_RESPONSE = 0x88
TIMER_UPDATE_RESPONSE = 0x94
DISCONNECT_TIMEOUT = 5.0
RECOVERY_REAPPEAR_TIMEOUT = 6.0


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


@dataclass(frozen=True, slots=True)
class ScheduleRecord:
    """One complete 16-byte ScentLab schedule record."""

    enabled: bool
    serial: int
    weekdays: int
    start_minute: int
    stop_minute: int
    run_seconds: int
    pause_seconds: int
    timer_id: int

    @classmethod
    def from_bytes(cls, data: bytes) -> ScheduleRecord:
        """Decode one record without discarding firmware-owned fields."""
        if len(data) != TIMER_RECORD_SIZE:
            raise ValueError(f"Expected 16 timer bytes, received {len(data)}")
        return cls(
            enabled=data[0] != 0,
            serial=data[1],
            weekdays=int.from_bytes(data[2:4], "little"),
            start_minute=int.from_bytes(data[4:6], "little"),
            stop_minute=int.from_bytes(data[6:8], "little"),
            run_seconds=int.from_bytes(data[8:10], "little"),
            pause_seconds=int.from_bytes(data[10:12], "little"),
            timer_id=int.from_bytes(data[12:16], "little"),
        )

    def to_bytes(self) -> bytes:
        """Encode the complete record for command 0x14."""
        return b"".join(
            (
                bytes((int(self.enabled), self.serial)),
                self.weekdays.to_bytes(2, "little"),
                self.start_minute.to_bytes(2, "little"),
                self.stop_minute.to_bytes(2, "little"),
                self.run_seconds.to_bytes(2, "little"),
                self.pause_seconds.to_bytes(2, "little"),
                self.timer_id.to_bytes(4, "little"),
            )
        )


class _FrameAssembler:
    """Assemble complete 55 AA frames from fragmented notifications."""

    def __init__(self, callback: Callable[[bytes], None]) -> None:
        self._buffer = bytearray()
        self._callback = callback

    def feed(self, data: bytes) -> None:
        """Append notification bytes and emit every complete valid frame."""
        self._buffer.extend(data)
        while True:
            marker = self._buffer.find(b"\x55\xAA")
            if marker < 0:
                # Preserve a possible first header byte split across notifications.
                if self._buffer.endswith(b"\x55"):
                    self._buffer[:] = b"\x55"
                else:
                    self._buffer.clear()
                return
            if marker:
                del self._buffer[:marker]
            if len(self._buffer) < 3:
                return
            frame_size = self._buffer[2] + 5
            if len(self._buffer) < frame_size:
                return
            frame = bytes(self._buffer[:frame_size])
            del self._buffer[:frame_size]
            if frame[-1] != 0x5A or sum(frame[:-1]) & 0xFF:
                _LOGGER.debug("Discarding invalid frame: %s", frame.hex(" ").upper())
                continue
            self._callback(frame)


class _ScentLabSession:
    """One connected and notification-enabled GATT session."""

    def __init__(self, client: BleakClientWithServiceCache, address: str) -> None:
        self.client = client
        self.address = address
        self._pending: dict[int, asyncio.Future[bytes]] = {}
        self._assembler = _FrameAssembler(self._handle_frame)

    async def async_start(self) -> None:
        """Enable the notification channel used for all replies."""

        def _notification_handler(_sender: object, data: bytearray) -> None:
            raw = bytes(data)
            _LOGGER.debug(
                "Notification from %s: %s",
                self.address,
                raw.hex(" ").upper(),
            )
            self._assembler.feed(raw)

        await self.client.start_notify(CHARACTERISTIC_UUID, _notification_handler)
        await asyncio.sleep(0.15)

    def _handle_frame(self, frame: bytes) -> None:
        """Deliver a frame to the request waiting for its response command."""
        command = frame[3]
        if (future := self._pending.get(command)) is not None and not future.done():
            future.set_result(frame)

    async def async_write(self, frame: bytes, label: str) -> None:
        """Write using the acknowledged GATT mode used by ScentLab."""
        _LOGGER.debug(
            "Writing %s to %s: %s",
            label,
            self.address,
            frame.hex(" ").upper(),
        )
        await self.client.write_gatt_char(
            CHARACTERISTIC_UUID, frame, response=True
        )

    async def async_request(
        self,
        frame: bytes,
        response_command: int,
        label: str,
        timeout: float = 4.0,
    ) -> bytes:
        """Write a request and wait for its framed notification response."""
        if response_command in self._pending:
            raise RuntimeError(f"A request for 0x{response_command:02X} is already pending")
        future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
        self._pending[response_command] = future
        try:
            await self.async_write(frame, label)
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(response_command, None)


class ScentLabBleController:
    """Connect to and control one ScentLab diffuser."""

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
        self.schedules: dict[int, ScheduleRecord] = {}
        self._listeners: set[Callable[[], None]] = set()
        self._lock = asyncio.Lock()

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity to cached schedule changes."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def _publish_schedules(self, schedules: dict[int, ScheduleRecord]) -> None:
        """Replace the cache and notify entities without doing I/O in properties."""
        self.schedules = schedules
        for listener in self._listeners:
            listener()

    def _ble_device(self) -> BLEDevice | None:
        """Return the freshest connectable BLE device known to Home Assistant."""
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

    async def _async_recover_stale_bluez_state(self, ble_device: BLEDevice) -> None:
        """Clear a stale local BlueZ connection and wait for rediscovery."""
        _LOGGER.warning(
            "%s (%s) has no available Bluetooth connection slot; "
            "clearing stale BlueZ state before one retry",
            self.name,
            self.address,
        )

        try:
            async with asyncio.timeout(DISCONNECT_TIMEOUT):
                await close_stale_connections_by_address(self.address)
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug(
                "Could not close a stale connection for %s: %s",
                self.address,
                err,
            )

        cache_cleared = False
        try:
            async with asyncio.timeout(DISCONNECT_TIMEOUT):
                cache_cleared = await clear_cache(self.address)
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug(
                "Could not clear the BlueZ cache for %s: %s",
                self.address,
                err,
            )

        # Re-run discovery matching immediately and give BlueZ time to recreate
        # the device after RemoveDevice. Advertisements normally arrive quickly.
        bluetooth.async_rediscover_address(self.hass, self.address)
        if cache_cleared:
            try:
                await wait_for_device_to_reappear(
                    ble_device, RECOVERY_REAPPEAR_TIMEOUT
                )
            except (BleakError, TimeoutError) as err:
                _LOGGER.debug(
                    "Error waiting for %s to reappear after cache cleanup: %s",
                    self.address,
                    err,
                )
        else:
            await asyncio.sleep(1.0)

    async def _async_connect(self) -> BleakClientWithServiceCache:
        """Connect, recovering once from stale local BlueZ slot state."""
        for attempt in range(2):
            ble_device = self._ble_device()
            if ble_device is None:
                raise HomeAssistantError(
                    f"{self.name} ({self.address}) is not currently reachable by a "
                    "connectable Home Assistant Bluetooth adapter"
                )
            try:
                return await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self.name,
                    max_attempts=3,
                )
            except BleakOutOfConnectionSlotsError:
                if attempt:
                    raise
                await self._async_recover_stale_bluez_state(ble_device)

        raise RuntimeError("Bluetooth recovery loop exited unexpectedly")

    @asynccontextmanager
    async def _async_operation(self) -> AsyncIterator[None]:
        """Run one BLE operation without allowing delayed commands to queue."""
        if self._lock.locked():
            raise HomeAssistantError(
                f"A Bluetooth operation for {self.name} is already in progress; "
                "this command was not queued"
            )
        await self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()

    @asynccontextmanager
    async def _async_session(self) -> AsyncIterator[_ScentLabSession]:
        """Connect, initialize like ScentLab, yield, and always disconnect."""
        client: BleakClientWithServiceCache | None = None
        try:
            client = await self._async_connect()
            session = _ScentLabSession(client, self.address)
            await session.async_start()

            await session.async_write(_build_frame(0x47), "password-status query")
            await asyncio.sleep(0.25)
            if self.password:
                await session.async_write(_password_frame(self.password), "password")
                await asyncio.sleep(0.25)
            await session.async_write(
                _build_frame(0x09, b"\x01\x00"), "device enquiry"
            )
            await asyncio.sleep(0.5)
            await session.async_write(_build_frame(0x51), "capability query")
            await asyncio.sleep(0.5)

            yield session
        except HomeAssistantError:
            raise
        except (BleakError, TimeoutError, ValueError) as err:
            raise HomeAssistantError(
                f"Failed to communicate with {self.name} over Bluetooth: {err}"
            ) from err
        finally:
            if client is not None:
                try:
                    async with asyncio.timeout(DISCONNECT_TIMEOUT):
                        await client.disconnect()
                except (BleakError, TimeoutError) as err:
                    _LOGGER.debug("Error disconnecting from %s: %s", self.address, err)

    async def async_set_power(self, enabled: bool) -> None:
        """Set diffuser power."""
        async with self._async_operation(), self._async_session() as session:
            await session.async_write(
                POWER_ON_FRAME if enabled else POWER_OFF_FRAME,
                "power on" if enabled else "power off",
            )
            await asyncio.sleep(0.35)

    async def async_set_nightlight(self, enabled: bool) -> None:
        """Set APK light mode 2 or explicitly turn the light off."""
        async with self._async_operation(), self._async_session() as session:
            await session.async_write(
                NIGHTLIGHT_ON_FRAME if enabled else NIGHTLIGHT_OFF_FRAME,
                "nightlight on" if enabled else "nightlight off",
            )
            await asyncio.sleep(0.35)

    async def _async_query_schedules(
        self, session: _ScentLabSession
    ) -> dict[int, ScheduleRecord]:
        """Read and parse every schedule record."""
        frame = await session.async_request(
            _build_frame(0x08), TIMER_RESPONSE, "schedule query"
        )
        if len(frame) < 8:
            raise ValueError("Schedule response was too short")
        count = int.from_bytes(frame[4:6], "little")
        required_size = 6 + count * TIMER_RECORD_SIZE + 2
        if len(frame) < required_size:
            raise ValueError(
                f"Schedule response declares {count} records but is only {len(frame)} bytes"
            )
        return {
            index + 1: ScheduleRecord.from_bytes(
                frame[
                    6 + index * TIMER_RECORD_SIZE : 6
                    + (index + 1) * TIMER_RECORD_SIZE
                ]
            )
            for index in range(count)
        }

    async def async_refresh_schedules(self) -> dict[int, ScheduleRecord]:
        """Refresh the schedule cache from the diffuser."""
        async with self._async_operation(), self._async_session() as session:
            schedules = await self._async_query_schedules(session)
        self._publish_schedules(schedules)
        return schedules

    async def async_update_schedule(self, slot: int, **changes: object) -> None:
        """Read, modify and write one complete schedule record safely."""
        async with self._async_operation(), self._async_session() as session:
            schedules = await self._async_query_schedules(session)
            if slot not in schedules:
                raise HomeAssistantError(f"Schedule slot {slot} is not present")

            updated = replace(schedules[slot], **changes)
            if not 0 <= updated.start_minute <= 1439:
                raise HomeAssistantError("Start time must be within one day")
            if not 0 <= updated.stop_minute <= 1439:
                raise HomeAssistantError("End time must be within one day")
            if not 0 <= updated.run_seconds <= 65535:
                raise HomeAssistantError("Spray duration is outside the protocol range")
            if not 0 <= updated.pause_seconds <= 65535:
                raise HomeAssistantError("Pause duration is outside the protocol range")

            try:
                await session.async_request(
                    _build_frame(0x14, updated.to_bytes()),
                    TIMER_UPDATE_RESPONSE,
                    f"schedule {slot} update",
                )
            except TimeoutError:
                _LOGGER.debug("No 0x94 acknowledgement for schedule %s", slot)
            await asyncio.sleep(0.25)
            schedules = await self._async_query_schedules(session)

        self._publish_schedules(schedules)
