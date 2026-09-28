#!/bin/bash
# Weekly push of Unraid data to the Synology NAS. Layout and retention: synology/README.md
set -uo pipefail
LOG=/var/log/synology_weekly_backup.log
DEST=/mnt/remotes/synology_backup_point
STATE="$DEST/.state"
TRASH="$DEST/.deleted"
APPDATA_DEST="$DEST/docker-data/appdata"
KEEP_APPDATA=4      # appdata archives kept on the NAS
TRASH_DAYS=30       # days deleted/overwritten files stay in .deleted
MAX_DELETE=5000     # per folder per run; beyond this rsync stops deleting and we alert
WARN_PCT=85         # warn when the NAS is fuller than this
STOP_PCT=95         # skip the backup entirely above this
NOTIFY=/usr/local/emhttp/plugins/dynamix/scripts/notify
STAMP=$(date +%Y-%m-%d_%H%M%S)
FAILED=0
MTIMES_OK=0

log()   { echo "[$(date)] $*" >> "$LOG"; }
alert() { log "ERROR: $1"; "$NOTIFY" -e "Synology Backup" -d "$1" -i "alert"; FAILED=1; }
warn()  { log "WARN: $1"; "$NOTIFY" -e "Synology Backup" -d "$1" -i "warning"; }
avail() { df -B1 --output=avail "$DEST" | tail -1; }
pct()   { df --output=pcent "$DEST" | tail -1 | tr -dc '0-9'; }

# Unassigned Devices mounts SMB with closetimeo=30: the delayed close resets file times after rsync
# sets them, so rsync sees every file as changed. closetimeo=0 fixes that; this proves it each run.
check_mtimes() {
  local f="$STATE/canary" want
  want=$(date -d '2001-02-03 04:05:06' +%s)
  mkdir -p "$STATE" || return 1
  echo "$STAMP" > "$f" && touch -d '2001-02-03 04:05:06' "$f" || return 1
  sleep 35
  [ "$(stat -c %Y "$f")" = "$want" ]
}

# sync_folder SRC NAME copy|mirror [rsync args...]
# mirror: $DEST/NAME matches SRC; deleted or overwritten files move to $TRASH/$STAMP/NAME.
# Mirror mode only runs once NAS file times are proven correct for NAME (the adopted marker);
# until then it copies without deleting, exactly like a plain rsync.
sync_folder() {
  local src=$1 name=$2 mode=$3 key rc
  shift 3
  key=${name//\//_}
  if [ ! -d "$src" ]; then
    alert "$name: source $src missing, skipped"
    return
  fi
  mkdir -p "$DEST/$name" "$STATE"
  local opts=(-ah --stats --exclude='@eaDir' --exclude='#recycle')
  if [ "$mode" = mirror ] && [ "$MTIMES_OK" = 1 ] && [ -f "$STATE/adopted.$key" ]; then
    opts+=(--delete --max-delete="$MAX_DELETE" --backup --backup-dir="$TRASH/$STAMP/$name")
    log "$name: mirror"
  else
    rm -f "$STATE/adopted.$key"
    log "$name: copy only"
  fi
  rsync "${opts[@]}" "$@" "$src/" "$DEST/$name/" --log-file="$LOG"
  rc=$?
  case $rc in
    0|24) [ "$MTIMES_OK" = 1 ] && touch "$STATE/adopted.$key" ;;
    25)   alert "$name: more than $MAX_DELETE deletions, stopped deleting. Removed files are in .deleted/$STAMP/$name" ;;
    *)    alert "$name: rsync failed (exit $rc)" ;;
  esac
}

# Empty recycle bin folders older than TRASH_DAYS. Only touches folders named like a run stamp.
prune_trash() {
  local cutoff d name
  [ -d "$TRASH" ] || return 0
  cutoff=$(date -d "-$TRASH_DAYS days" +%Y-%m-%d)
  for d in "$TRASH"/*/; do
    [ -d "$d" ] || continue
    name=$(basename "$d")
    [[ $name =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{6}$ ]] || continue
    if [[ ${name:0:10} < $cutoff ]]; then
      rm -rf -- "$d" && log "Emptied recycle bin folder $name"
    fi
  done
}

prune_appdata() {
  ls -1d "$APPDATA_DEST"/ab_* 2>/dev/null | sort -r | tail -n +$(( $1 + 1 )) | while read -r d; do
    rm -rf -- "$d" && log "Pruned appdata archive $(basename "$d")"
  done
}

backup_appdata() {
  local src name need
  mkdir -p "$APPDATA_DEST"
  # Newest archive at least 60 min old, so one still being written is never copied.
  src=$(find /mnt/user/docker-data -maxdepth 1 -type d -name 'ab_*' -mmin +60 | sort | tail -1)
  if [ -z "$src" ]; then
    alert "No appdata archive found in /mnt/user/docker-data"
    return
  fi
  name=$(basename "$src")
  if [ -d "$APPDATA_DEST/$name" ]; then
    log "Appdata archive $name already on NAS"
    return
  fi
  need=$(du -sb "$src" | cut -f1)
  need=$(( need + need / 10 ))
  if [ "$(avail)" -lt "$need" ]; then
    log "Low space on NAS, pruning to $(( KEEP_APPDATA - 1 )) appdata archives first"
    prune_appdata $(( KEEP_APPDATA - 1 ))
  fi
  if [ "$(avail)" -lt "$need" ]; then
    alert "Not enough space on NAS for appdata archive $name"
  elif rsync -ah --stats "$src/" "$APPDATA_DEST/.partial-$name/" --log-file="$LOG" \
       && mv "$APPDATA_DEST/.partial-$name" "$APPDATA_DEST/$name"; then
    prune_appdata "$KEEP_APPDATA"
  else
    alert "Copy of appdata archive $name failed"
  fi
}

main() {
  log "Starting"
  if ! mountpoint -q "$DEST"; then
    alert "$DEST not mounted"
    exit 1
  fi
  if ! mdcmd status 2>/dev/null | grep -q '^mdState=STARTED'; then
    alert "Array not started"
    exit 1
  fi

  prune_trash
  if [ "$(pct)" -ge "$STOP_PCT" ]; then
    alert "NAS is $(pct)% full, backup skipped"
    exit 1
  fi

  grep " $DEST " /proc/mounts | grep -q 'closetimeo=0' \
    || mount -o remount,closetimeo=0 "$DEST" >> "$LOG" 2>&1
  if check_mtimes; then
    MTIMES_OK=1
  else
    warn "NAS is not keeping file times; copying without deletions this run"
  fi

  # Flash backups: Unraid keeps only the newest zip, the Synology task keeps 26 on the NAS,
  # so this folder is copied, never mirrored.
  ls -t /mnt/user/unraid-usb/*.zip 2>/dev/null | tail -n +2 | xargs -r rm -f
  sync_folder /mnt/user/unraid-usb unraid-usb copy
  # VM disks change every week; mirroring would put a full copy in .deleted each run.
  sync_folder /mnt/user/vms vms copy

  for s in backups-family backups-friends personal editing; do
    sync_folder "/mnt/user/$s" "$s" mirror
  done
  # thumbs/ and encoded-video/ are regenerated by Immich.
  sync_folder /mnt/user/docker-data/immich docker-data/immich mirror \
    --exclude='/thumbs/' --exclude='/encoded-video/'
  sync_folder /mnt/user/docker-data/paperless-ngx docker-data/paperless-ngx mirror

  backup_appdata

  local p
  p=$(pct)
  log "Recycle bin: $(du -sh "$TRASH" 2>/dev/null | cut -f1)"
  [ "$p" -lt "$WARN_PCT" ] || warn "NAS is ${p}% full"
  [ "$FAILED" -eq 0 ] || exit 1
  log "Done (NAS ${p}% used)"
  "$NOTIFY" -e "Synology Backup" -d "Completed successfully (NAS ${p}% used)" -i "normal"
}

[[ "${BASH_SOURCE[0]}" == "$0" ]] && main "$@"
