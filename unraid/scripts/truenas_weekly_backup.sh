#!/bin/bash

BACKUP_DOCKER=/mnt/user/restic-offsite-backups
BACKUP_FAMILY=/mnt/user/backups-family
BACKUP_FRIENDS=/mnt/user/backups-friends
BACKUP_JARED=/mnt/user/personal
BACKUP_UNRAID_OS=/mnt/user/unraid-usb
BACKUP_UNRAID_VM=/mnt/user/vms

rsync -avh \
  "$BACKUP_FAMILY" \
  "$BACKUP_FRIENDS" \
  "$BACKUP_JARED" \
  "$BACKUP_DOCKER" \
  "$BACKUP_UNRAID_OS" \
  "$BACKUP_UNRAID_VM" \
  /mnt/remotes/truenas_backup_point/ \
  --log-file=/var/log/truenas_weekly_backup.log