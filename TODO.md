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

- [x] #2 Camera VLAN: `security_vlan_in` (default drop; Blue Iris `10.0.60.2` may reach IoT camera `10.0.40.10` 80/554 and internet; cameras nothing) + `security_vlan_local` (DNS/DHCP/NTP/ping). Verified 2026-09-27.
- [x] #3 Guest VLAN: `guest_in` (home networks rejected) + `guest_local` (DNS/DHCP/NTP/ping)
- [x] #4 Router admin: `admin_protect_local` drops TCP 22/80/443 to the router from VLANs 51–54, 70, 100; older ciphers off
- [x] Deleted `WAN_IN` rules 10/20 ("Block Web"); `WAN_IN` keeps established/related, drop invalid, default drop
- `eth1`/`eth2` deliberately left out of `admin_protect_local` (physical-only access)
- [ ] If Blue Iris loses the IoT camera: check `security_vlan_in` rule "Blue Iris to IoT camera" counter (unused until Blue Iris reconnects)
- [ ] #5 Move IoT gear off the main LAN. One device at a time; check it works in its app before the next.
  - [x] mDNS repeater `eth3` ↔ `eth3.40` (phones on main LAN can still discover casts/Hue on IoT)
  - Wi-Fi devices → reconnect to the IoT Wi-Fi (2.4 GHz):
    - [ ] Meross plug `10.0.3.5` (reset: hold button ~5 s, re-add in Meross app)
    - [ ] Meross garage opener `10.0.3.17` (same; may fix HA's broken garage entities)
    - [ ] FoxESS inverter dongle `10.0.3.201` (FoxCloud app → Wi-Fi configuration; HA uses the cloud, unaffected)
    - [ ] Chromecast `10.0.3.16`, Chromecast Ultra `10.0.3.252` (Google Home app → Wi-Fi → Forget → set up again)
    - [ ] Unknown HF-LPT230 Wi-Fi module `10.0.3.226` (MAC `e8:fd:f8…`): identify via http://10.0.3.226 (often admin/admin)
  - Wired devices → EdgeSwitch port VLAN untagged + PVID:
    - [ ] Hue bridge `10.0.3.60` → VLAN 40. First reserve `10.0.40.60` (router DHCP IoT static mapping, MAC `00:17:88:2d:7b:2e`). After: check HA Hue integration, delete `BLOCK_IN` "Allow Hue Hub".
    - [ ] CyberPower UPS card `10.0.3.15` → Management VLAN 50 (optional)
    - [ ] Camera `10.0.40.10` → camera VLAN 60: reserve a `10.0.60.x`, update IP in Blue Iris, delete `security_vlan_in` "Blue Iris to IoT camera"
- [x] #6 `10.0.3.5` is a Meross device (MAC `c4:e7:ae…`). Leftover NAT rule 1 `dns-redirect-VLAN50` that pointed at it is deleted.
- [ ] Remove router user `claude` when network work is done: `configure ; delete system login user claude ; commit ; save`. Its key has **no `from=` limit** (EdgeOS rejects quotes), so don't leave it longer than needed.
- [ ] Optional: let IoT resolve `*.int.jyoung-primary.com` (`set service dns forwarding options server=/int.jyoung-primary.com/10.0.3.11`)

## Home Assistant
- [ ] Re-pair Zigbee devices in Zigbee2MQTT (the ZBT-2 formed a new network on 2026-09-27)
- [ ] Unplug the ConBee II if unused
- [x] Save the dashboard / rename / update-flow scripts into this repo (`home-assistant/`)

- [ ] Tablet: kiosk start page by IP (`http://10.0.40.7:8123/tablet-home/home`) so it survives Technitium outages
- [ ] Tablet: hide Overview in the `younghome` sidebar; kiosk app "reload start URL on idle" (optional: HACS `kiosk-mode` to hide the header)
- [ ] Save the HA backup encryption key in Vaultwarden (Settings → System → Backups → Settings → Encryption key)

## Housekeeping
- [ ] After the next Unraid reboot: check NUT came up (`upsc -c ups@127.0.0.1` lists `127.0.0.1`)
- [ ] After the watcher finishes: delete `/root/install_waiter.sh` on Unraid
- [ ] Set git identity on the PC: `git config --global user.name "jyoung"` and `user.email`
- Note: git on this PC uses Windows OpenSSH (`git config --global core.sshCommand`), needed for the `overlord_ed25519` key
- [ ] `claude_ed25519` key expires on Unraid, Synology and HA on **2026-12-31** (`expiry-time`). Renew or remove the `authorized_keys` lines before then.

## Parked
- TrueNAS backup (share not mounted) and restic (disabled)
- Unraid disk balance, second parity drive
