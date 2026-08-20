# ScentLab BLE Diffuser for Home Assistant

This custom integration controls a `Scent-B04P...` diffuser through Home Assistant's own connectable Bluetooth adapter. It writes the reverse-engineered ScentLab ON/OFF packets to characteristic `FFE1` and disconnects after each command.

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
- Optimistic switch state because the exact power-status notification has not yet been validated on this hardware.
- Optional four-character application-password submission before each command.

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
