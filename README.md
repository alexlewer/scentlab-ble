# ScentLab BLE Diffuser for Home Assistant

[![Validate with hassfest](https://github.com/alexlewer/scentlab-ble/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexlewer/scentlab-ble/actions/workflows/hassfest.yaml)
[![HACS Validate](https://github.com/alexlewer/scentlab-ble/actions/workflows/validate.yaml/badge.svg)](https://github.com/alexlewer/scentlab-ble/actions/workflows/validate.yaml)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-blue.svg)](https://github.com/custom-components/hacs)

This custom integration was built to control a [Magnifiscent ZenPlug](https://magnifiscentonline.com/products/zenplug), a re-badged version of the [Grasse Aroma GAH-04P(S)](https://grassearoma.com/product/gah-04p-s/), controlled using the Scent Lab app.

## Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alexlewer&repository=scentlab-ble&category=integration)

1. Click the button above, or in Home Assistant go to **HACS > Integrations > three dots > Custom repositories**
2. Add `https://github.com/alexlewer/scentlab_ble` as **Integration**
3. Search for **Scent Assistant** and click **Download**
4. Restart Home Assistant

## Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=scentlab_ble)

Click the button above to start setup.

The phone app should be closed while Home Assistant controls the diffuser as the device will only accept one active connection. Also ensure that your bluetooth adaptor in Home Assistant is set to **Scanning Mode → Active** under **Settings → Bluetooth**.

## Current behavior

- Local Bluetooth control; no cloud dependency.
- Short-lived connection for each ON/OFF command.
- Optimistic switch state because the exact power-status notification has not yet been validated on this hardware.
- Optional four-character application-password submission before each command.
- Enables FFE1 notifications and reproduces ScentLab's connection initialization.
- Uses acknowledged GATT writes, matching the Android app.
- Recovers once from stale local BlueZ connection-slot state by disconnecting any
  phantom diffuser session, clearing its cached device record, and rediscovering it.
- Uses a bounded disconnect after every operation, including half-disconnected clients.
- Rejects overlapping operations immediately instead of replaying queued commands
  after Bluetooth connectivity returns.
- Debug logging includes transmitted packets and received notifications.
- When a command is sent from HA, you will hear either two or three sets of two beeps; the first set is the connection starting, the second is the command being sent (on update) and the third is the connection ending.

## Schedule entities

The integration reads all timer records on startup and exposes five independent schedule groups:

- `Schedule N` enable switch
- `Schedule N Start Time`
- `Schedule N End Time`
- `Schedule N Spray` in seconds
- `Schedule N Pause` in seconds
- `Schedule N Days` to select the relevant schedule day(s)-of-week
- `Refresh schedules` button

Before each schedule write, the integration reads the current 16-byte record and changes only the requested field. This preserves its serial number, timer ID, and all other settings. It reads the schedules again after the write to publish the state actually stored by the diffuser.

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
