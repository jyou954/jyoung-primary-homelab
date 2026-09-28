# TODO

Started 2026-09-27. Tick things off as they're done.

## Waiting on the Synology backup run
The weekly backup started 2026-09-27 ~17:05 and re-copies everything (~6 TB), so it takes many hours. A watcher on Unraid (`/root/install_waiter.sh`) swaps in the new backup script when it finishes.

- [x] Backup finished 2026-09-28 19:34 (NAS 67% used). New script installed 20:28; `CANARY: file times KEPT` (mirror mode will work).
- [x] Commit the already-edited `unraid/scripts/synology_weekly_backup.sh`, `synology/README.md`, `unraid/README.md`.
- [x] Fix `unraid/README.md`: `/root/.ssh` is on the flash drive (`/boot/config/ssh/root`), not RAM.
- [ ] 2026-10-04 run: copy-only, sets `.state/adopted.*` markers on the NAS.
- [ ] 2026-10-11 run: first mirror run. `.deleted/` should be small, no alerts.

## Network #1: take Unraid off the IoT and Camera VLANs
Unraid has its own address on VLAN 40 (`10.0.40.5`) and 60 (`10.0.60.5`), serving SSH, web UI, SMB and NFS to IoT devices and cameras, bypassing the router firewall.

- [x] HA trusted proxies: added `10.0.3.11` (pending until HA restarts)
- [x] Unraid telnet off
- [x] 2026-09-28: VLAN 40, 50, 51, 60 set to "IPv4 address assignment: None" (VLANs kept for the VM bridges). Verified from HA: Unraid unreachable from IoT; `haos.int` works via Traefik (HA trusts `10.0.3.11`); WUD → MQTT works via the router
- [x] VNC passwords set on all three VMs (done while they were stopped)
- [x] Blue Iris: editing the VM dropped its Windows disk (`vdisk1.img`); re-added as disk 1 (VirtIO, boot 1), WD Purple as disk 2. Recording again (~6 Mbit/s in, ~0.8 MB/s to the WD Purple). VM definition backups: `/mnt/user/vms/<vm>/<vm>.xml.bak-20260928`. Disk path set back to the direct pool path `/mnt/vm-pool/vms/hl-bi-01/vdisk1.img` (via virsh, not the form); recording verified
- [x] Blue Iris disk monitoring: `windows_exporter` 0.31.8 in the VM (firewall: only `10.0.3.11`), Prometheus job `blue-iris`, Homepage card (D: free / % used)
- [ ] You: Grafana → Dashboards → New → Import → ID `14694` → Prometheus → Import (auto-import failed)
- [ ] You: change the Grafana admin password (it was in a helper script and is in the chat transcript); save it in Bitwarden
- [ ] Tablet: check it still loads the dashboard
- [ ] Remove `10.0.40.5` from HA trusted proxies, restart HA
- Also set VLAN 50 (`10.0.50.5`) and 51 (`10.0.51.5`) to None unless something needs them (security audit 2026-09-28).
- No router rule needed for WUD → HA MQTT (`10.0.40.7:1883`): LAN → IoT is allowed and replies pass `BLOCK_IN` rule 30. Verified from the PC through the router, 2026-09-28. No HA integration uses Unraid's VLAN IPs.

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
    - [ ] CyberPower UPS card `10.0.3.14` → Management VLAN 50 (optional; update `dynamic/ups.yml` if its IP changes)
    - [ ] Camera `10.0.40.10` → camera VLAN 60: reserve a `10.0.60.x`, update IP in Blue Iris, delete `security_vlan_in` "Blue Iris to IoT camera"
- [x] #6 `10.0.3.5` is a Meross device (MAC `c4:e7:ae…`). Leftover NAT rule 1 `dns-redirect-VLAN50` that pointed at it is deleted.
- [ ] Remove router user `claude` when network work is done: `configure ; delete system login user claude ; commit ; save`. Its key has **no `from=` limit** (EdgeOS rejects quotes), so don't leave it longer than needed.
- [ ] Optional: let IoT resolve `*.int.jyoung-primary.com` (`set service dns forwarding options server=/int.jyoung-primary.com/10.0.3.11`)

## Switches (see `network/switch-ports.md`)
- [x] Port names set and saved on `jy-nw-es16` and `jy-nw-es48` (2026-09-28)
- [ ] es48 **0/35 ↔ 0/39 loop**: find what connects them (cable, small switch or bridged PC) and remove it; then name 0/35/0/39
- [ ] es48 **0/43 "PC - Intel i9" at 10 Mbps** and **0/8 "Proxmox 03" at 100 Mbps**: reseat or replace cables
- [ ] Remove switch user `claude` when done (password-only account): `configure`, `no username claude`, `exit`, `write memory` on both

## Docker updates (WUD, set up 2026-09-28)
Pending updates show in HA (Settings → Updates) and in WUD. Read release notes before pressing Install on anything below.
- [x] Immich v2 → v3.2.2 (2026-09-28). Migrations OK, 12983 assets unchanged. Pre-upgrade dump: `/mnt/user/appdata/immich/immich-db-before-v3-20260928.sql.gz`; old `.env` at `.env.bak-20260928`
- [ ] Immich: update the iPhone app; optionally re-run Metadata Extraction (Administration → Jobs) so older videos get the new streaming
- [x] Traefik v3.7, Semaphore v2.19.14, Gotenberg 8.37, BookStack DB 11.4.12 (installed from HA 2026-09-28; compose files updated to match)
- [x] Authentik 2026.2.2 → 2026.5.7 → 2026.8.3 (2026-09-28, one release at a time as Authentik requires). Migrations 692 → 777, no errors. Pre-upgrade dump: `authentik-db-before-2026.5-20260928.sql.gz`
- [ ] Authentik no longer uses Redis (no log mentions): consider removing `authentik-redis` and `AUTHENTIK_REDIS__HOST` next time the stack is edited (check the current compose.yml from goauthentik.io first)
- [x] WUD made report-only (no update trigger, read-only socket proxy). Updates are approved by hand via Compose Manager → Update Stack
- [ ] Remove the leftover `wud.trigger.include=docker.autoupdate,mqtt.ha` labels (homepage, grafana node_exporter, paperless tika, Traefik and Authentik socket proxies) next time each stack is edited
- [x] Authentik: had been stopped since 2026-08-08. Started again with autostart on (2026-09-28)
- [ ] Add `wud.display.name` labels to the unlabelled compose services the next time each stack is edited (HA names are already set by `home-assistant/wud_entity_names.py`)
- [ ] After 2026-10-05, on Unraid: delete the `docker-compose.yml.bak-20260928` copies, `render.sh.bak-20260928`, Immich's `.env.bak-20260928` and `/mnt/user/system/secrets.bak-20260928`; remove Semaphore's old anonymous volume `961b72e7…` (confirm first)
- [ ] Delete unused old Docker networks: `paperless_paperless_internal`, `monitoring_monitoring_internal`, `homepage_socket_proxy`, `technitium_default`, `bws-render_default`, `wg0`

## Security audit (2026-09-28)
- [ ] Work through the findings, most urgent first. The report is kept outside the repo because it maps the weak spots.
- [x] HA SSH add-on: password removed, key-only (keys: `overlord@docker-01`, `claude@workstation`)
- [x] Unraid share `unraid-usb` (flash backups): Secure → Private (overlord, jyoung RW; jaredyoung read). Guests can no longer read it
- [x] Unbalanced plugin uninstalled (unused; web UI had no login)
- [x] Vaultwarden stopped, autostart off (unused; data kept in `/mnt/user/appdata/vaultwarden`)
- [ ] Change the Unraid user passwords (their hashes were in the guest-readable flash backups)
- [x] UPS card `10.0.3.14`: Telnet and FTP off (verified closed 2026-09-28)
- [x] Technitium A record `ups.int.jyoung-primary.com` → `10.0.3.11` (added via API). Traefik route `dynamic/ups.yml` is live (502 until the card has HTTPS)
- [x] Printer/UPS mix-up fixed: router DHCP `cbups` (had the printer's MAC) replaced by `Brother-Printer` 10.0.3.15 (Wi-Fi) and `CyberPower-UPS` 10.0.3.14; es48 0/2 renamed `UPS - CyberPower .3.14`
- [x] HA SSH keys: removed `overlord@docker-01`, added the PC's `overlord_ed25519` (labelled `overlord@workstation`; same key as GitHub). Needs an SSH add-on restart to apply
- [x] UPS card: SNMPv1 off, HTTPS on; `https://ups.int.jyoung-primary.com` works with a trusted cert. Optional: turn off its HTTP (port 80). Change its login password if it's still the default
- [x] Prometheus: removed the two dead lab `node_exporter` targets (`10.0.51.102`, `10.0.51.254`); add them back when the lab returns
- [ ] You: HA → Profile → Security: turn on TOTP for `overlord`

## Home Assistant
- [ ] Re-pair Zigbee devices in Zigbee2MQTT (the ZBT-2 formed a new network on 2026-09-27)
- [ ] Unplug the ConBee II if unused
- [x] Save the dashboard / rename / update-flow scripts into this repo (`home-assistant/`)

- [ ] Tablet: kiosk start page by IP (`http://10.0.40.7:8123/tablet-home/home`) so it survives Technitium outages
- [ ] Tablet: hide Overview in the `younghome` sidebar; kiosk app "reload start URL on idle" (optional: HACS `kiosk-mode` to hide the header)
- [ ] Save the HA backup encryption key in your Bitwarden (cloud) vault (Settings → System → Backups → Settings → Encryption key). Vaultwarden is off.

## Housekeeping
- [ ] After the next Unraid reboot: check NUT came up (`upsc -c ups@127.0.0.1` lists `127.0.0.1`)
- [x] Deleted `/root/install_waiter.sh` on Unraid (watcher done)
- [ ] Set git identity on the PC: `git config --global user.name "jyoung"` and `user.email`
- Note: git on this PC uses Windows OpenSSH (`git config --global core.sshCommand`), needed for the `overlord_ed25519` key
- [ ] `claude_ed25519` key expires on Unraid, Synology and HA on **2026-12-31** (`expiry-time`). Renew or remove the `authorized_keys` lines before then.

## Parked
- TrueNAS backup (share not mounted) and restic (disabled)
- Unraid disk balance, second parity drive
