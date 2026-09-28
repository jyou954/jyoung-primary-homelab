# Home Assistant (`10.0.40.7`, HAOS VM `hl-haos-01` on Unraid)

The scripts run **inside HA** through the Advanced SSH & Web Terminal app. They read HA's API token from the app's environment at runtime, so no token is stored here. Run them from a PC that has the SSH key:

```
ssh overlord@10.0.40.7 python3 - [args] < <script>.py
```

On Windows PowerShell use `cmd /c "ssh ... python3 - < script.py"` (PowerShell has no `<` redirect).

## Requirements
- Advanced SSH & Web Terminal app, user `overlord`, key in the app's `authorized_keys`. Turn off `compatibility_mode`.
- HACS cards: Mushroom, button-card
- iPhone companion app (`notify.mobile_app_jareds_iphone`) for update pushes

## Files
| File | What it does | Run |
|---|---|---|
| `ha_tablet_dashboard.py` | Builds the **Tablet** dashboard (`/tablet-home`) and the **Overview** dashboard (plus admin-only Admin page). Checks every entity is working before saving. | `--force` (tablet) or `--target=overview` |
| `ha_update_notify.py` | iPhone push for HA updates with **Install all / Later**; installs in a safe order (apps → Core → OS) and resumes after restarts; weekly Sunday 10:00 reminder. Also a separate push for Unraid container updates (`update.wud_*`), which "Install all" never touches. | no args; `--send-now` to push immediately |
| `wud_entity_names.py` | Readable names for the What's Up Docker entities and devices, and disables the database containers' update entities (`DATABASES`) so they can't be installed from HA. Rerun after adding containers. | no args |
| `ha_doorbell.py` | Doorbell automation: all speakers to 100%, announce on each speaker, restore volumes (50% for speakers that were off). Saves and validates only; never rings. | no args |
| `ha_rename.py` | Readable display names for 86 entities (entity IDs unchanged). **Already applied 2026-09-27.** | dry run by default; `--apply` |
| `entity_names_before_2026-09-27.json` | Names before `ha_rename.py`, for undoing individual renames. | — |
| `automations.yaml`, `scripts.yaml` | Snapshot of HA's automations and scripts (doorbell announcement, update flow). HA is the source of truth; re-export after editing in the UI. | — |

## Notes
- **Doorbell announcement** speaks on each speaker individually. Cast *groups* cut short clips off after the first syllable.
- **Zigbee2MQTT** with the ZBT-2 needs `baudrate: 460800`, `adapter: ember`, `rtscts: true` (config: `/homeassistant/zigbee2mqtt/configuration.yaml`).
- **`http:`** settings (Traefik proxy) live in HA's own storage, not `configuration.yaml`. Trusted proxies: Settings → System → Network, and they apply only after an HA restart.
- **Backups:** daily, kept 3, to HA's disk and the Synology share `HABackup` (network storage `synology_haos_backup`). Needs EdgeRouter rule `BLOCK_IN` "Allow HA backups to Synology SMB". Keep the backup encryption key in Bitwarden.
- **SSH app is key-only** (no password, since 2026-09-28). Allowed keys: `overlord@workstation` (the PC's `overlord_ed25519`) and `claude@workstation` (expires 2026-12-31). Changing keys needs an app restart.
