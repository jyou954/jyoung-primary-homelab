# Unraid (`10.0.3.11`)

Copy files with `scp <file> root@10.0.3.11:<path>`. `/boot` is the USB flash and survives reboots; `/etc`, `/var/log` and most of `/root` are RAM and do not. Exception: `/root/.ssh` is kept on the flash (`/boot/config/ssh/root`).

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
| `docker/homepage/config/*.yaml` | `/mnt/user/appdata/homepage/` | Homepage reloads on save. Up/down dots are checked from inside the container (container names, internal ports); API keys come from `homepage.env` as `{{HOMEPAGE_VAR_*}}` |
| `docker/Traefik/dynamic/*.yml` | `/mnt/user/appdata/traefik/dynamic/` | Traefik reloads on save. Routes for non-Docker hosts: HA, router, switches, UPS card, Unraid UI. Each needs a Technitium A record `<name>.int.jyoung-primary.com` → `10.0.3.11` |

### User scripts
Create in Settings → User Scripts with the folder name, paste the file, set the schedule. Schedules live in `/boot/config/plugins/user.scripts/schedule.json`, not in this repo.

| File | Folder name | Schedule |
|---|---|---|
| `delete_ds_store.sh` | `delete.ds_store` | Hourly |
| `restic_daily_backup.sh` | `restic_daily_backup` | **Disabled** (see Known issues) |
| `synology_weekly_backup.sh` | `synology_weekly_backup` | Weekly (Sun 04:30) |
| `truenas_weekly_backup.sh` | `truenas_weekly_backup` | Weekly (Sun 04:30); fails while TrueNAS is offline |

### Backups
| When | What | Where |
|---|---|---|
| Daily 00:00 | Appdata Backup plugin: stops containers, archives appdata + flash | `/mnt/user/docker-data/ab_*` (7 days), `/mnt/user/unraid-usb/` |
| Sun 04:30 | `synology_weekly_backup.sh` | Synology — layout and retention in [`synology/README.md`](../synology/README.md) |

- `/mnt/user/docker-data/immich` is Immich's **live photo library**, not a backup.
- `synology_weekly_backup.sh` mirrors to the NAS with a 30-day recycle bin — how it works and its safety rails are in [`synology/README.md`](../synology/README.md). Settings (`KEEP_APPDATA`, `TRASH_DAYS`, `MAX_DELETE`, `WARN_PCT`, `STOP_PCT`) are at the top of the script.
- It alerts if the NAS is not mounted, the array is stopped, a copy fails, too many deletions are attempted, or the NAS is filling up.

### NUT
- UPS: CyberPower PR1500ERT2U on USB.
- Not in repo: `upsd.users`, `upsmon.conf` (see `upsmon.conf.example`). Passwords are in Bitwarden Secrets Manager.
- **Passwords must not contain `#`** — NUT treats it as a comment and upsmon won't start.
- Check: `upsc -c ups@127.0.0.1` should list `127.0.0.1`.

### Docker
- Every container runs from a Compose Manager project. `name`, `autostart`, `description`, `envpath` are Compose Manager's own files.
- Secrets: stacks load `env_file: /mnt/user/system/secrets/<stack>.env`. **`bws-render` creates these from Bitwarden Secrets Manager** — run it first on a fresh server. Its access token is at `/mnt/user/appdata/bws/access-token` (not in repo).
- Grafana's Prometheus datasource and the Node Exporter Full dashboard (ID 1860) were set up in the Grafana UI — not in repo.
- **Running compose by hand:** always pass the project name from the `name` file, or Compose uses the `name:` inside the file and clashes with the running containers:
  `P=/boot/config/plugins/compose.manager/projects/<project>; docker compose -p "$(cat $P/name)" -f $P/docker-compose.yml -f $P/docker-compose.override.yml --project-directory $P up -d <service>`

### Container updates (What's Up Docker)
`docker/wud/` runs WUD at `https://wud.int.jyoung-primary.com` (login `jyoung`). It checks every container every 6 hours and **only reports**: it has no update trigger, and its socket proxy is read-only (`POST=0`), so it can't change any container.

**Where to see updates:** the WUD web UI (full list, current → available, patch/minor/major), the iPhone push when new updates appear, and HA → Settings → Updates. HA's Install buttons do nothing.

**How to update (you approve each one):**
1. Judge the jump: a new build of `latest` or a patch is safe; a minor, skim the release notes; a major, or anything with a database or Authentik, read the release notes and dump the database first.
2. Tag bump (e.g. `v3.6` → `v3.7`): change the tag in the stack's compose file, here and on Unraid.
3. Unraid → Docker → Compose → the stack → **Update Stack** (pulls and recreates from the compose file, so compose stays the source of truth).
4. Safety net: Appdata Backup archives all appdata nightly at 00:00 (keeps 3); Immich also dumps its DB nightly.
5. **Authentik: one release at a time** (e.g. 2026.2 → 2026.5 → 2026.8, latest patch of each); its release notes say skipping is not allowed. `authentik-server` and `authentik-worker` must always have the same tag.

| Label on a service | Effect |
|---|---|
| `wud.display.name=...` | Readable name in WUD and HA. |
| `wud.tag.include=<regex>` | Only offer tags matching the pin (use `$$` for `$` in compose). |
| `wud.trigger.include=docker.autoupdate,mqtt.ha` | Leftover from when WUD auto-updated five containers; now just reporting. Remove next time the stack is edited. |

- **Pinned databases** (a new major can't start on old data): Semaphore `postgres:18` (`^18$$`, digest updates only), Authentik `postgres:16-alpine` (`^16-alpine$$`) and BookStack `mariadb:11.4.x` (`^11\.4\.\d+$$`). Upgrading a major is a manual job: dump, upgrade, restore.
- **Why report-only:** on 2026-09-28 installing everything from HA moved Authentik to Postgres 18 (refused to start, data safe) and Authentik 2026.2 → 2026.8, and left compose files naming old versions (a later `compose up` would have downgraded them). All rolled back / synced. WUD's rebuild of Traefik also copied its old MAC address, which Semaphore later received too, so Traefik couldn't reach Semaphore (502) until Traefik was recreated from compose.
- WUD only rescans at startup if its store is empty. To refresh the list after updating, use the refresh button on the watcher in the WUD UI, or wait for the 6-hourly check.
- Secrets `WUD_AUTH_ADMIN_HASH` (bcrypt, `htpasswd -nB`) and `WUD_TRIGGER_MQTT_HA_PASSWORD` (HA user `wud`) come from `bws-render`. BWS secrets must be in the **Infrastructure** project; the access token can't see others.

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
