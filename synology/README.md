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
| `backups-family`, `backups-friends`, `personal`, `editing`, `vms` | Unraid shares | Mirror. Files deleted on Unraid are **kept** here |
| `unraid-usb/` | Unraid flash backup zips | Newest 26 (6 months), pruned by `unraid-usb-rotate.sh` |
| `docker-data/immich/` | Immich library (`upload`, `library`, `profile`, `backups`) | Mirror. Deleted photos are **kept** here |
| `docker-data/paperless-ngx/` | Paperless media | Mirror |
| `docker-data/appdata/ab_*` | Newest Appdata Backup archive | Newest 4, pruned by the Unraid script. Oldest pruned early if space is short |
