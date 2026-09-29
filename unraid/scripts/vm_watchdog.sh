#!/bin/bash
# Restart VMs that crashed. Runs every 5 minutes (User Scripts, custom schedule).
# Only acts when libvirt's log says the VM's last stop was a crash, so VMs shut down
# on purpose (Unraid UI, virsh shutdown, maintenance) are left alone.
# At most MAX restarts per VM per day; after that it only alerts.
# Test without changing anything: DRYRUN=1 bash vm_watchdog.sh

VMS="hl-haos-01 hl-bi-01 unraid-int-ca"
MAX=3
STATE=/tmp/vm_watchdog
DRYRUN=${DRYRUN:-0}

mkdir -p "$STATE"
notify() { [ "$DRYRUN" = 1 ] && { echo "would notify [$3]: $1 - $2"; return; }
  /usr/local/emhttp/webGui/scripts/notify -e "VM watchdog" -s "$1" -d "$2" -i "$3"; }

# VM service off (array stopped, VM Manager disabled): nothing to do
virsh version >/dev/null 2>&1 || { [ "$DRYRUN" = 1 ] && echo "VM service not running"; exit 0; }

for vm in $VMS; do
  virsh dominfo "$vm" >/dev/null 2>&1 || { [ "$DRYRUN" = 1 ] && echo "$vm: not defined"; continue; }
  state=$(virsh domstate "$vm")
  last=$(grep -E 'shutting down, reason=' "/var/log/libvirt/qemu/$vm.log" 2>/dev/null | tail -1)
  [ "$DRYRUN" = 1 ] && echo "$vm: $state | last stop: ${last:-none}"
  [ "$state" = "shut off" ] || continue
  case "$last" in *reason=crashed*) ;; *) continue ;; esac

  crash=$(echo "$last" | cut -c1-19)
  [ "$(cat "$STATE/$vm.handled" 2>/dev/null)" = "$crash" ] && continue   # this crash was already handled

  today=$(date +%F)
  n=$(grep -c "^$today" "$STATE/$vm.restarts" 2>/dev/null); n=${n:-0}
  if [ "$n" -ge "$MAX" ]; then
    echo "$crash" > "$STATE/$vm.handled"
    notify "$vm crashed again, NOT restarting" "Crashed $((n + 1)) times today (last at $crash UTC). Left off: check Unraid > VMs." alert
    continue
  fi

  if [ "$DRYRUN" = 1 ]; then echo "would start $vm"; continue; fi
  if out=$(virsh start "$vm" 2>&1); then
    echo "$today $(date +%T)" >> "$STATE/$vm.restarts"
    echo "$crash" > "$STATE/$vm.handled"
    notify "$vm crashed and was restarted" "Crash at $crash UTC. Restart $((n + 1)) of $MAX today." warning
  else
    echo "$crash" > "$STATE/$vm.handled"
    notify "$vm crashed and could NOT be restarted" "$(echo "$out" | tail -1)" alert
  fi
done
