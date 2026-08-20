# ScentLab BLE Diffuser for Home Assistant

This custom integration controls a `Scent-B04P...` diffuser through Home Assistant's own connectable Bluetooth adapter. It writes the reverse-engineered ScentLab protocol to characteristic `FFE1` and disconnects after each operation.

## Install

1. Copy `custom_components/scentlab_ble` into the `custom_components` directory under your Home Assistant configuration directory.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**.
4. Search for **ScentLab BLE Diffuser**.
5. Enter the diffuser's Bluetooth MAC address. Leave the application password blank unless you explicitly enabled a four-character password in ScentLab.

The phone app should be closed while Home Assistant controls the diffuser because many inexpensive BLE peripherals accept only one active connection.

## Current behavior

- Local Bluetooth control; no cloud dependency.
- Short-lived connection for each ON/OFF command.
- Optimistic power and `Nightlight` switches because their exact status
  notifications have not yet been validated on this hardware.
- Experimental nightlight control using APK action `0x15`: alternate mode `2`
  for on and mode `0` for off. Mode `1` was accepted over GATT but produced no
  visible effect on the tested B04P.
- Optional four-character application-password submission before each command.
- Enables FFE1 notifications and reproduces ScentLab's connection initialization.
- Uses acknowledged GATT writes, matching the Android app.
- Recovers once from stale local BlueZ connection-slot state by disconnecting any
  phantom diffuser session, clearing its cached device record, and rediscovering it.
- Uses a bounded disconnect after every operation, including half-disconnected clients.
- Rejects overlapping operations immediately instead of replaying queued commands
  after Bluetooth connectivity returns.
- Debug logging includes transmitted packets and received notifications.

## Schedule entities

The integration reads all timer records on startup and exposes five independent schedule groups:

- `Schedule N` enable switch
- `Schedule N Start Time`
- `Schedule N End Time`
- `Schedule N Spray` in seconds
- `Schedule N Pause` in seconds
- `Refresh schedules` button

Before each schedule write, the integration reads the current 16-byte record and changes only the requested field. This preserves its weekday mask, serial number, timer ID, and all other settings. It reads the schedules again after the write to publish the state actually stored by the diffuser.

Use the refresh button after changing schedules in ScentLab. The device does not accept schedules that cross midnight; use two schedule groups for a period spanning midnight.

## Troubleshooting

- Confirm Home Assistant's Bluetooth integration can see `Scent-B04P...` as connectable.
- Keep the diffuser close to the Home Assistant Bluetooth adapter.
- Close ScentLab and disconnect other BLE clients.
- Enable debug logging if needed:

```yaml
logger:
  logs:
    custom_components.scentlab_ble: debug
    bleak_retry_connector: debug
```
