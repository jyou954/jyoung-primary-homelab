#!/bin/bash
set -uo pipefail
LOG=/var/log/synology_weekly_backup.log
DEST=/mnt/remotes/synology_backup_point

echo "[$(date)] Starting" >> "$LOG"

if ! mountpoint -q "$DEST"; then
  echo "[$(date)] ERROR: $DEST not mounted" >> "$LOG"
  /usr/local/emhttp/plugins/dynamix/scripts/notify -e "Synology Backup" -d "Mount not available" -i "alert"
  exit 1
fi

ls -t /mnt/user/unraid-usb/*.zip 2>/dev/null | tail -n +2 | xargs rm -f

rsync -ah --stats \
  /mnt/user/restic-offsite-backups \
  /mnt/user/backups-family \
  /mnt/user/backups-friends \
  /mnt/user/personal \
  /mnt/user/unraid-usb \
  /mnt/user/vms \
  /mnt/user/editing \
  "$DEST/" \
  --log-file="$LOG"

RC=$?
if [ $RC -ne 0 ]; then
  /usr/local/emhttp/plugins/dynamix/scripts/notify -e "Synology Backup" -d "rsync failed (exit $RC)" -i "alert"
  exit $RC
fi

echo "[$(date)] Done" >> "$LOG"
/usr/local/emhttp/plugins/dynamix/scripts/notify -e "Synology Backup" -d "Completed successfully" -i "normal"
