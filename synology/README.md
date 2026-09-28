# Synology (`jySynNAS`, `10.0.3.13`)

Backup target for Unraid. Unraid mounts `//10.0.3.13/Backup` at `/mnt/remotes/synology_backup_point` and pushes to it every Sunday 04:30 (`unraid/scripts/synology_weekly_backup.sh`).

SFTP is off on the NAS, so `scp` to it fails. Copy files through Unraid's mount instead: `scp <file> root@10.0.3.11:/mnt/remotes/synology_backup_point/`.

## Where files go
| Repo | NAS path | Apply |
|---|---|---|
| `unraid-usb-rotate.sh` | `/volume1/Backup/unraid-usb-rotate.sh` | Control Panel → Task Scheduler → task running `bash /volume1/Backup/unraid-usb-rotate.sh` as `root`, weekly Sun 05:00 |

## What's in `/volume1/Backup`
| Folder | From | Retention |
|---|---|---|
| `backups-family`, `backups-friends`, `personal`, `editing` | Unraid shares | Mirror + recycle bin |
| `docker-data/immich/` | Immich library (`upload`, `library`, `profile`, `backups`; not `thumbs`/`encoded-video`) | Mirror + recycle bin |
| `docker-data/paperless-ngx/` | Paperless media | Mirror + recycle bin |
| `vms/` | Unraid VM disks | Copy only, never deletes (mirroring would bin a full disk copy every week) |
| `unraid-usb/` | Unraid flash backup zips | Newest 26 (6 months), pruned by `unraid-usb-rotate.sh` |
| `docker-data/appdata/ab_*` | Newest Appdata Backup archive | Newest 4. Oldest pruned early if space is short |
| `.deleted/<date>/` | Recycle bin: files deleted or overwritten on Unraid | Emptied after 30 days (`TRASH_DAYS`) |
| `.state/` | Script markers | See below |

## Mirror + recycle bin
Mirror folders match Unraid. Anything deleted or changed on Unraid is moved to `.deleted/<run date>/<folder>/` rather than lost, and kept 30 days. To restore, copy it back from there.

Safety rails in `synology_weekly_backup.sh`:
- A run deletes at most 5000 items per folder (`MAX_DELETE`). Beyond that it stops deleting and alerts — check the source share before re-running.
- Nothing is deleted unless the NAS is proven to keep file times (see below). Otherwise the run copies only.
- Missing source folder, array stopped, or NAS over 95% full → that folder / the run is skipped with an alert.
- Synology's `@eaDir` and `#recycle` folders are never touched.

## File times (important)
Unassigned Devices mounts this share with `closetimeo=30`, which makes the NAS reset file times after rsync sets them. rsync then thinks every file changed and re-copies everything each week. The script remounts with `closetimeo=0` and writes a canary file each run to prove times stick.

`.state/adopted.<folder>` means that folder's NAS times are correct, so it can be mirrored. The first run after a folder's times were wrong copies everything once, then sets the marker. Delete a marker to force a copy-only run for that folder.
