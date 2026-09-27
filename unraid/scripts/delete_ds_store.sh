#!/bin/bash
set -uo pipefail
LOG=/var/log/delete_ds_store.log
echo "[$(date)] Starting" >> "$LOG"
for path in /mnt/user /mnt/remotes; do
  if [ -d "$path" ]; then
    find "$path" -maxdepth 9999 -noleaf -type f -name ".DS_Store" -delete 2>> "$LOG"
  else
    echo "[$(date)] WARN: $path not available, skipping" >> "$LOG"
  fi
done
echo "[$(date)] Done" >> "$LOG"
