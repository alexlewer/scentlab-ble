"""Constants for the ScentLab BLE integration."""

from typing import Final

DOMAIN: Final = "scentlab_ble"

CONF_PASSWORD: Final = "password"

SERVICE_UUID: Final = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID: Final = "0000ffe1-0000-1000-8000-00805f9b34fb"

POWER_ON_FRAME: Final = bytes.fromhex("55 AA 04 07 12 01 00 E3 5A")
POWER_OFF_FRAME: Final = bytes.fromhex("55 AA 04 07 12 00 00 E4 5A")

# Standard-protocol action 0x15. Mode 0 is off; mode 2 is the APK's alternate
# light mode used by its newer-device path. This remains hardware-experimental.
NIGHTLIGHT_ON_FRAME: Final = bytes.fromhex("55 AA 04 07 15 02 00 DF 5A")
NIGHTLIGHT_OFF_FRAME: Final = bytes.fromhex("55 AA 04 07 15 00 00 E1 5A")
