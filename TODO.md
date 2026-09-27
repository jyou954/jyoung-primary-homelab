# TODO

Started 2026-09-27. Tick things off as they're done.

## Waiting on the Synology backup run
The weekly backup started 2026-09-27 ~17:05 and re-copies everything (~6 TB), so it takes many hours. A watcher on Unraid (`/root/install_waiter.sh`) swaps in the new backup script when it finishes.

- [ ] Check `/var/log/synology_backup_install.log` on Unraid: expect `new script installed` and a `CANARY:` line (`KEPT` = mirror mode will work).
- [ ] Commit the already-edited `unraid/scripts/synology_weekly_backup.sh`, `synology/README.md`, `unraid/README.md`.
- [ ] Fix `unraid/README.md`: `/root/.ssh` is on the flash drive (`/boot/config/ssh/root`), not RAM.
- [ ] 2026-10-04 run: copy-only, sets `.state/adopted.*` markers on the NAS.
- [ ] 2026-10-11 run: first mirror run. `.deleted/` should be small, no alerts.

## Network #1: take Unraid off the IoT and Camera VLANs
Unraid has its own address on VLAN 40 (`10.0.40.5`) and 60 (`10.0.60.5`), serving SSH, web UI, SMB and NFS to IoT devices and cameras, bypassing the router firewall.

- [x] HA trusted proxies: added `10.0.3.11` (pending until HA restarts)
- [x] Unraid telnet off
- [ ] After the backup finishes: restart HA (applies the pending proxy) → stop Docker and VM Manager → Settings → Network: VLAN 40 and 60 "IPv4 address assignment: None" (keep the VLANs) → Apply → start Docker and VMs
- [ ] Verify: `10.0.40.5` / `10.0.60.5` unreachable from IoT; `haos.int…` works via Traefik; tablet works; VMs `hl-haos-01` and `hl-bi-01` (Blue Iris) up
- [ ] Remove `10.0.40.5` from HA trusted proxies, restart HA

## Network: next
Make firewall changes in the EdgeRouter **web UI**: scripted CLI commits fail on this router ("Cannot delete rule set ... still in use").

- [ ] #2 Camera VLAN (`security_vlan_in`): allow established, drop to `PROTECT_NETWORKS`, router DNS/DHCP only. Decide: do cameras need internet? Blue Iris VM is on VLAN 60.
- [ ] #3 Guest VLAN (`eth3.80`): internet only
- [ ] #4 Router admin: GUI/SSH listen on `10.0.3.1` (+ management), disable older ciphers
- [ ] #5 Move IoT gear off the main LAN: Meross plug, HF-LPT230, FoxESS inverter, 2 Chromecasts, Hue bridge, UPS card (+ mDNS repeater for casting)
- [ ] #6 Identify `10.0.3.5`: NAT rule 1 redirects main-LAN DNS to it
- [ ] Remove router user `claude` when network work is done: `configure ; delete system login user claude ; commit ; save`
- [ ] Optional: let IoT resolve `*.int.jyoung-primary.com` (`set service dns forwarding options server=/int.jyoung-primary.com/10.0.3.11`)

## Home Assistant
- [ ] Re-pair Zigbee devices in Zigbee2MQTT (the ZBT-2 formed a new network on 2026-09-27)
- [ ] Unplug the ConBee II if unused
- [x] Save the dashboard / rename / update-flow scripts into this repo (`home-assistant/`)

## Parked
- TrueNAS backup (share not mounted) and restic (disabled)
- Unraid disk balance, second parity drive
