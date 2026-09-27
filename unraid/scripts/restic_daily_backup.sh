#!/bin/bash
set -uo pipefail
REPO=/mnt/user/restic-offsite-backups
PASS=/root/restic-password.txt
SRC=/mnt/user/docker-data
LOG=/var/log/restic_daily_backup.log
IMG=restic/restic:latest

echo [$(date)] Starting restic backup >> $LOG

[ -f $PASS ] || { echo ERROR: password file missing; exit 1; }
docker info &>/dev/null || { echo ERROR: docker not running; exit 1; }

run_restic() {
  docker run --rm \
    -v $REPO:/repo:rw \
    -v $PASS:/pass:ro \
    -v $SRC:/docker-data:ro \
    $IMG $@ --repo /repo --password-file /pass >> $LOG 2>&1
}

run_restic backup /docker-data || { /usr/local/emhttp/plugins/dynamix/scripts/notify -e Restic -d Backup failed -i alert; exit 1; }
run_restic forget --keep-last 7 --prune || { /usr/local/emhttp/plugins/dynamix/scripts/notify -e Restic -d Prune failed -i alert; exit 1; }
run_restic check || { /usr/local/emhttp/plugins/dynamix/scripts/notify -e Restic -d Check failed -i alert; exit 1; }

echo [$(date)] Done >> $LOG
/usr/local/emhttp/plugins/dynamix/scripts/notify -e Restic -d Backup completed -i normal
