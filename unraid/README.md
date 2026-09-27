# Unraid (`10.0.3.11`)

Copy files with `scp <file> root@10.0.3.11:<path>`. `/boot` is the USB flash and survives reboots; `/root`, `/etc`, `/var/log` are RAM and do not.

## Required plugins
| Plugin | Needed for |
|---|---|
| User Scripts | `scripts/` |
| NUT (nut-dw) — Settings → NUT → **Manual Config: Yes** | `nut/` |
| Compose Manager | `docker/` |
| Appdata Backup | Creates the daily flash + appdata archives the backup scripts copy |
| Unassigned Devices | SMB mounts `/mnt/remotes/synology_backup_point` (`//10.0.3.13/Backup`) and `truenas_backup_point` |

## Where files go
| Repo | Server path | Apply |
|---|---|---|
| `go` | `/boot/config/go` | Runs at boot |
| `logrotate/userscripts` | `/boot/config/logrotate.d/userscripts` | `go` copies it to `/etc/logrotate.d/` at boot; copy manually to apply now |
| `nut/*` | `/boot/config/plugins/nut-dw/ups/` | Settings → NUT → restart, or `/etc/rc.d/rc.nut restart` |
| `scripts/<x>.sh` | `/boot/config/plugins/user.scripts/scripts/<folder>/script` | See table below |
| `docker/<project>/` | `/boot/config/plugins/compose.manager/projects/<project>/` | Docker tab → Compose → project → Compose Up |
| `docker/grafana/prometheus.yml` | `/mnt/user/appdata/prometheus/prometheus.yml` | `docker restart prometheus` |

### User scripts
Create in Settings → User Scripts with the folder name, paste the file, set the schedule. Schedules live in `/boot/config/plugins/user.scripts/schedule.json`, not in this repo.

| File | Folder name | Schedule |
|---|---|---|
| `delete_ds_store.sh` | `delete.ds_store` | Hourly |
| `restic_daily_backup.sh` | `restic_daily_backup` | **Disabled** (see Known issues) |
| `synology_weekly_backup.sh` | `synology_weekly_backup` | Weekly (Sun 04:30) |

### Backups
| When | What | Where |
|---|---|---|
| Daily 00:00 | Appdata Backup plugin: stops containers, archives appdata + flash | `/mnt/user/docker-data/ab_*` (7 days), `/mnt/user/unraid-usb/` |
| Sun 04:30 | `synology_weekly_backup.sh` | Synology — layout and retention in [`synology/README.md`](../synology/README.md) |

- `/mnt/user/docker-data/immich` is Immich's **live photo library**, not a backup.
- `synology_weekly_backup.sh` alerts if the NAS is not mounted, a copy fails, there is no room for the appdata archive, or the NAS is over 85% full. Tune `KEEP_APPDATA` / `WARN_PCT` at the top of the script.
| `truenas_weekly_backup.sh` | `truenas_weekly_backup` | Weekly (Sun 04:30) |

### NUT
- UPS: CyberPower PR1500ERT2U on USB.
- Not in repo: `upsd.users`, `upsmon.conf` (see `upsmon.conf.example`). Passwords are in Bitwarden Secrets Manager.
- **Passwords must not contain `#`** — NUT treats it as a comment and upsmon won't start.
- Check: `upsc -c ups@127.0.0.1` should list `127.0.0.1`.

### Docker
- Every container runs from a Compose Manager project. `name`, `autostart`, `description`, `envpath` are Compose Manager's own files.
- Secrets: stacks load `env_file: /mnt/user/system/secrets/<stack>.env`. **`bws-render` creates these from Bitwarden Secrets Manager** — run it first on a fresh server. Its access token is at `/mnt/user/appdata/bws/access-token` (not in repo).
- Grafana's Prometheus datasource and the Node Exporter Full dashboard (ID 1860) were set up in the Grafana UI — not in repo.

## Not in repo
| What | Where |
|---|---|
| Stack `.env` files | `/mnt/user/system/secrets/` (rendered by `bws-render`) |
| BWS access token | `/mnt/user/appdata/bws/access-token` |
| NUT passwords | Bitwarden Secrets Manager |
| Container data | Appdata Backup → `/mnt/user/docker-data` |

## Known issues
- **restic is disabled.** It last completed on 2026-04-12: it reads `/root/restic-password.txt`, which is in RAM and gone after every reboot. The Synology backup now covers what it did. To bring it back (e.g. for TrueNAS): render `RESTIC_PASSWORD` via `bws-render`, pass that `.env` to the restic container, and point it at `/mnt/user/appdata` + `/mnt/user/docker-data/immich` rather than the compressed `ab_*` archives (they don't dedupe).
- **TrueNAS share is not mounted**, so `truenas_weekly_backup.sh` fails.
