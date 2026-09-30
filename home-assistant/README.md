# Home Assistant (`10.0.40.7`, HAOS VM `hl-haos-01` on Unraid)

The scripts run **inside HA** through the Advanced SSH & Web Terminal app. They read HA's API token from the app's environment at runtime, so no token is stored here. Run them from a PC that has the SSH key:

```
ssh overlord@10.0.40.7 python3 - [args] < <script>.py
```

On Windows PowerShell use `cmd /c "ssh ... python3 - < script.py"` (PowerShell has no `<` redirect).

## Requirements
- Advanced SSH & Web Terminal app, user `overlord`, key in the app's `authorized_keys`. Turn off `compatibility_mode`.
- HACS cards: Mushroom, button-card
- HACS integration: Meross LAN (`krahabb/meross_lan`), for local control of the Meross plugs and garage opener
- iPhone companion app (`notify.mobile_app_jareds_iphone`) for update pushes

## Files
| File | What it does | Run |
|---|---|---|
| `ha_tablet_dashboard.py` | Builds the **Tablet** dashboard (`/tablet-home`) and the **Overview** dashboard (plus admin-only Admin page). Pages: Home, Rooms (lights, scenes, bedroom curtain), Music, Solar, Sensors (doors, garage, plugs, motion, temperature, light level, batteries). Checks every entity is working before saving, so it refuses to save while a device is offline. | `--force` (tablet) or `--target=overview` |
| `ha_update_notify.py` | iPhone push for HA updates with **Install all / Later**; installs in a safe order (apps → Core → OS) and resumes after restarts; weekly Sunday 10:00 reminder. Also a separate push for Unraid container updates (`update.wud_*`), which "Install all" never touches. | no args; `--send-now` to push immediately |
| `wud_entity_names.py` | Readable names for the What's Up Docker entities and devices. WUD is report-only, so their Install buttons do nothing. Rerun after adding containers. | no args |
| `ha_doorbell.py` | Doorbell automation: all speakers to 100%, announce on each speaker, restore volumes (50% for speakers that were off). Saves and validates only; never rings. | no args |
| `ha_rename.py` | Readable display names for 86 entities (entity IDs unchanged). **Already applied 2026-09-27.** | dry run by default; `--apply` |
| `entity_names_before_2026-09-27.json` | Names before `ha_rename.py`, for undoing individual renames. | — |
| `automations.yaml`, `scripts.yaml` | Snapshot of HA's automations and scripts (doorbell announcement, update flow, container update push, door-sensor lights, seed light schedule). HA is the source of truth; re-export after editing in the UI. | — |

## Notes
- **Doorbell announcement** speaks on each speaker individually. Cast *groups* cut short clips off after the first syllable.
- **Zigbee2MQTT** with the ZBT-2 needs `baudrate: 460800`, `adapter: ember`, `rtscts: true` (config: `/homeassistant/zigbee2mqtt/configuration.yaml`). Channel 25. The network key lives in that file and in `coordinator_backup.json`: never print them (regenerated 2026-09-29 after a leak; backup of the empty old network in `backup-20260929-rekey/`).
- **Door sensors** (Aqara MCCGQ11LM on Z2M; `on` = open): `binary_sensor.front_door_sensor_contact` (`0x00158d0006c3bed2`) and `binary_sensor.back_door_sensor_contact` (`0x00158d0006c39cf1`). Renaming a device in Z2M with "update HA entity ID" changes the entity ID, so fix the automation triggers afterwards.
  - **Front door at night:** downstairs hallway lights on; after 2 min they go off once the Hue hallway motion sensor (`binary_sensor.downstairs_hallway_motion_sensor_motion`) has been clear for 1 min, or 15 min after the door opened at the latest. The Hue app may run its own motion rule for these lights, which HA can't see.
  - **Back door at night:** dining room lights (`light.dining_room_lights`, all four) on for 2 min.
  - Both: "night" = `sun.sun` below the horizon (follows Sydney sunset and daylight saving), nothing on close, lights left alone if already on, reopening restarts the timer.
  - Aqara pairing: hold the button about 5 s until the blue light blinks, then tap every 2 s for about 30 s. Holding it again after joining makes it leave the network.
- **Other Zigbee devices** (Z2M):
  - **Bedroom Curtain** `cover.bedroom_curtain`: Zemismart BCM500DS-TYZ (`TS0601_cover_1`, `0x04cd15fffe396919`), area Bedroom, mains powered (acts as a router). Pairing: press **Learn 3 times quickly** until the light flashes; holding Learn only jogs the motor, and more than 3 presses starts other functions. Named "Bedroom Curtain" so Google voice commands are short.
  - **Second Bedroom** (no lights, double curtain): `cover.second_bedroom_blackout_curtain` (`0xa4c1384dcbe978de`, heavier blackout) and `cover.second_bedroom_privacy_curtain` (`0xa4c138a81d4de6d9`, privacy screen), both `TS0601_cover_1`. Group helper `cover.second_bedroom_curtains` moves both. Names follow pairing order (blackout first); not yet checked against the physical curtains.
  - **Zigbee Repeater Upstairs Hallway**: IKEA TRADFRI E1746 (`0x842e14fffe768988`).
  - **Zigbee Repeater Living Room**: IKEA TRADFRI E1746 (`0x842e14fffe779592`).
- **Meross** (HACS Meross LAN, local HTTP): Seed Light Plug `switch.seed_light`, Study Air Purifier Plug `switch.study_air_purifier`, Spare Plug `switch.spare_plug` (all MSS305 with power and energy sensors), garage opener `cover.garage_door` (MSG100). The Meross cloud profile only supplies the device keys (password not saved, cloud MQTT publish off). To add a device: power-cycle it, then Discovered → Add (the key fills itself in). Adding by IP asks for the Meross login again. Addresses: see `network/wifi-and-iot.md`.
- **Seed light** automation: on 08:00 to midnight, and re-applies the right state after an HA restart or when the plug comes back online.
- **LG TV** `media_player.study_lg_tv` (LG webOS integration, local). Shows unavailable while the TV is off.
- **ConBee II** is Zigbee-only (not Z-Wave): unplugged spare, for ZHA only if Z2M can't handle a device. To use it again, add it to the VM with `startupPolicy='optional'` (never as a required device or a serial passthrough: a missing stick then stops HA from booting, as on 2026-09-29).
- **USB passthrough:** the VM has one USB entry, the ZBT-2 matched by vendor/product (`303a:831a`), `startupPolicy='optional'`. Keep exactly one entry per stick; a duplicate attach made QEMU crash.
- **`http:`** settings (Traefik proxy) live in HA's own storage, not `configuration.yaml`. Trusted proxies: Settings → System → Network, and they apply only after an HA restart. Currently only `10.0.3.11` (Traefik on Unraid).
- **Backups:** daily, kept 3, to HA's disk and the Synology share `HABackup` (network storage `synology_haos_backup`). Needs EdgeRouter rule `BLOCK_IN` "Allow HA backups to Synology SMB". Keep the backup encryption key in Bitwarden.
- **SSH app is key-only** (no password, since 2026-09-28). Allowed keys: `overlord@workstation` (the PC's `overlord_ed25519`) and `claude@workstation` (expires 2026-12-31). Changing keys needs an app restart.
