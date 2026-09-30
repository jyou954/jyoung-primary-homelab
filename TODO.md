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
- [x] CA VM `unraid-int-ca` had also lost its disk in the same VNC-password edit (sat at the UEFI shell; all `*.int` certs would have expired within 24 h). Disk re-added via virsh (`/mnt/vm-pool/vms/unraid-int-ca/vdisk1.img`, VirtIO, boot 1); step-ca up
- [x] Blue Iris behind Traefik: `https://blueiris.int.jyoung-primary.com` (`dynamic/blueiris.yml`, Technitium A record)
- [x] Blue Iris disk monitoring: `windows_exporter` 0.31.8 in the VM (firewall: only `10.0.3.11`), Prometheus job `blue-iris`, Homepage card (D: free / % used)
- [x] Grafana: "Windows Exporter Dashboard 2025 (v0.31+ compatible)", ID `23942` (the older 14694 doesn't match current metric names)
- [x] Grafana admin password changed (old one was in a helper script / chat transcript)
- [x] Tablet: check it still loads the dashboard
- [x] Removed `10.0.40.5` from HA trusted proxies, restarted HA (2026-09-29)
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
  - [x] mDNS repeater `eth3` ↔ `eth3.40` (phones on main LAN can still discover casts/Hue on IoT). Only worked after `iot_vlan_local` rule 4 "Accept mDNS" (2026-09-30)
  - Wi-Fi devices → join **`Indus`** (see `network/wifi-and-iot.md` for the address plan):
    - [x] Meross Seed Light Plug, Study Air Purifier Plug, Spare Plug and garage opener → Indus, all in HA via Meross LAN (2026-09-30). Reservations `.30`/`.32`/`.33`/`.40`; they move there at their next renewal
    - [ ] Meross "Hydro Tower Plug" (`…6b:aa`): offline in the Meross account. When it's back: Indus, add to HA, reserve `.34`
    - [ ] FoxESS inverter dongle `10.0.3.201` (FoxCloud app → Wi-Fi configuration; HA uses the cloud, unaffected)
    - [x] Chromecast Ultra "Study TV" → `Indus`, reserved `10.0.40.20` (2026-09-30). Casting from Aries works; HA sees it again
    - [ ] Sony XR-83A90J TV `10.0.3.224` (Google TV): TV settings → Network → Wi-Fi → Indus. Then reserve `10.0.40.21`
    - [ ] Chromecast `10.0.3.16` "Changhong TV": belongs to someone else's Google Home (shows as a local device, "Request invite"). Find the owner and have them move it to `Indus`, or factory-reset it (hold button ~25 s) and set it up in our home. Skipped for now; reserve `.22` when it moves
    - [ ] Wall tablet: rejoined the old `Indus IoT`; move it to `Indus`
    - [ ] Then let friends on Gemini (guest Wi-Fi, VLAN 80) cast: router rule Gemini → the Chromecast/TV reservations only on TCP 8008, 8009, 8443, add `eth3.80` to the mDNS repeater (and allow mDNS in `guest_local`). Don't give out the Indus password
    - [ ] Unknown HF-LPT230 Wi-Fi module `10.0.3.226` (MAC `e8:fd:f8…`): identify via http://10.0.3.226 (often admin/admin)
  - Wired devices → EdgeSwitch port VLAN untagged + PVID:
    - [ ] Hue bridge `10.0.3.60` → VLAN 40. First reserve `10.0.40.60` (router DHCP IoT static mapping, MAC `00:17:88:2d:7b:2e`). After: check HA Hue integration, delete `BLOCK_IN` "Allow Hue Hub".
    - [ ] CyberPower UPS card `10.0.3.14` → Management VLAN 50 (optional; update `dynamic/ups.yml` if its IP changes)
    - [ ] Camera `10.0.40.10` → camera VLAN 60: reserve a `10.0.60.x`, update IP in Blue Iris, delete `security_vlan_in` "Blue Iris to IoT camera"
- [x] #6 `10.0.3.5` is a Meross device (MAC `c4:e7:ae…`). Leftover NAT rule 1 `dns-redirect-VLAN50` that pointed at it is deleted.
- [ ] Remove router user `claude` when network work is done: `configure ; delete system login user claude ; commit ; save`. Its key has **no `from=` limit** (EdgeOS rejects quotes), so don't leave it longer than needed.
- [x] Router forwards `*.int.jyoung-primary.com` to Technitium; removed its wrong `unraid-int-ca → 10.0.3.11` host entry (2026-09-29)
- [x] Unraid: Tailscale DNS takeover off; host + containers resolve internet names again (had been broken since the VLAN change)

## Wi-Fi and IoT (see `network/wifi-and-iot.md`)
- [x] UniFi: old controller lost; both AC Lites reset and adopted on the Unraid controller, firmware 6.8.2, reserved `10.0.3.41`/`.42`. Aries, Indus IoT, Indus, Gemini recreated (2026-09-30)
- [x] IoT DHCP pool moved to `.100`–`.254`; `.2`–`.99` reservations only, in blocks
- [x] LG TV: tracking domains blocked on the router + its DNS forced through the router (NAT 4010); Live Plus etc. off on the TV
- [ ] In a few days: check `/var/log/dnsmasq.log` for new LG tracking domains, and that the TV's apps still work
- [ ] Fornax (parents, VLAN 20): router VLAN + DHCP + firewall (internet; HA, Blue Iris via Traefik, casting, printer; nothing else), VLAN 20 tagged on es48 0/51, 0/52, es16 0/17, 0/13, 0/15, then enable the Fornax Wi-Fi. The UniFi network exists already. Mind the ~4 networks per band limit
- [ ] Delete the `Indus IoT` Wi-Fi once UniFi shows 0 clients on it
- [ ] Xiaomi gateway `10.0.40.3` renews its DHCP lease every 1–2 minutes: find out why
- [ ] Main LAN: same pool split as IoT (reservations below `.100`, automatic above)

## Switches (see `network/switch-ports.md`)
- [x] Port names set and saved on `jy-nw-es16` and `jy-nw-es48` (2026-09-28)
- [ ] es48 **0/35 ↔ 0/39 loop**: find what connects them (cable, small switch or bridged PC) and remove it; then name 0/35/0/39
- [ ] es48 **0/43 "PC - Intel i9" at 10 Mbps** and **0/8 "Proxmox 03" at 100 Mbps**: reseat or replace cables
- [ ] Remove switch user `claude` when done (password-only account): `configure`, `no username claude`, `exit`, `write memory` on both

## Docker updates (WUD, set up 2026-09-28)
Pending updates show in HA (Settings → Updates) and in WUD. Read release notes before pressing Install on anything below.
- [x] Immich v2 → v3.2.2 (2026-09-28). Migrations OK, 12983 assets unchanged. Pre-upgrade dump: `/mnt/user/appdata/immich/immich-db-before-v3-20260928.sql.gz`; old `.env` at `.env.bak-20260928`
- [x] iPhone (`10.0.3.236`, "Jareds-iPhone") trusts the internal root CA (`root-ca-01 Root CA`, SHA-256 `BF:35:1A:72…00:2F:34:B5`); Immich app uses `https://immich.int.jyoung-primary.com`
- [x] Tailscale (2026-09-29): Unraid advertises only `10.0.3.11/32` (approved; was 10.0.10–70.0/24), Tailscale SSH off, stale devices removed (truenas-scale, workstation, jareds-macbook-pro). Split DNS `int.jyoung-primary.com → 10.0.3.11` gives every `*.int` site from away
- [x] iPhone: Tailscale connected and Immich tested away from home (2026-09-30)
- [x] Immich iPhone app works (at home)
- [ ] Immich: optionally optionally re-run Metadata Extraction (Administration → Jobs) so older videos get the new streaming
- [x] Traefik v3.7, Semaphore v2.19.14, Gotenberg 8.37, BookStack DB 11.4.12 (installed from HA 2026-09-28; compose files updated to match)
- [x] Authentik 2026.2.2 → 2026.5.7 → 2026.8.3 (2026-09-28, one release at a time as Authentik requires). Migrations 692 → 777, no errors. Pre-upgrade dump: `authentik-db-before-2026.5-20260928.sql.gz`
- [x] Authentik Redis removed (2026-09-29; unused since 2025.10: no connections, no keys). Leftover folder `/mnt/user/appdata/authentik/redis` can be deleted
- [x] Git identity set on the PC (`jyoung <young.aze+claude@hotmail.com>`); 6 unused Docker networks deleted
- [x] WUD made report-only (no update trigger, read-only socket proxy). Updates are approved by hand via Compose Manager → Update Stack
- [x] Leftover `wud.trigger.include=docker.autoupdate,mqtt.ha` labels removed
- [x] Authentik: had been stopped since 2026-08-08. Started again with autostart on (2026-09-28)
- [x] Every container has a `wud.display.name` label
- [ ] After 2026-10-05, on Unraid: delete the `docker-compose.yml.bak-20260928` copies, `render.sh.bak-20260928`, Immich's `.env.bak-20260928` and `/mnt/user/system/secrets.bak-20260928`; remove Semaphore's old anonymous volume `961b72e7…` (confirm first)

## Security audit (2026-09-28)
- [ ] Work through the findings, most urgent first. The report is kept outside the repo because it maps the weak spots.
- [x] HA SSH add-on: password removed, key-only (keys: `overlord@docker-01`, `claude@workstation`)
- [x] Unraid share `unraid-usb` (flash backups): Secure → Private (overlord, jyoung RW; jaredyoung read). Guests can no longer read it
- [x] Unbalanced plugin uninstalled (unused; web UI had no login)
- [x] Vaultwarden stopped, autostart off (unused; data kept in `/mnt/user/appdata/vaultwarden`)
- [x] UPS card `10.0.3.14`: Telnet and FTP off (verified closed 2026-09-28)
- [x] Technitium A record `ups.int.jyoung-primary.com` → `10.0.3.11` (added via API). Traefik route `dynamic/ups.yml` is live (502 until the card has HTTPS)
- [x] Printer/UPS mix-up fixed: router DHCP `cbups` (had the printer's MAC) replaced by `Brother-Printer` 10.0.3.15 (Wi-Fi) and `CyberPower-UPS` 10.0.3.14; es48 0/2 renamed `UPS - CyberPower .3.14`
- [x] HA SSH keys: removed `overlord@docker-01`, added the PC's `overlord_ed25519` (labelled `overlord@workstation`; same key as GitHub). Needs an SSH add-on restart to apply
- [x] UPS card: SNMPv1 off, HTTPS on; `https://ups.int.jyoung-primary.com` works with a trusted cert. Optional: turn off its HTTP (port 80). Change its login password if it's still the default
- [x] Prometheus: removed the two dead lab `node_exporter` targets (`10.0.51.102`, `10.0.51.254`); add them back when the lab returns
- [x] HA TOTP on for `overlord`
- [x] Key-only SSH on Unraid, NAS, router and HA (2026-09-29); `overlord_ed25519` key in the Bitwarden vault. Router: `set service ssh disable-password-authentication`, key on user `overlord`
- [ ] MacBook: use the same key via Bitwarden Desktop's SSH agent (or copy it to `~/.ssh`, `chmod 600`)
- [x] Hardening 2026-09-29: switches HTTP off (HTTPS only, saved) · router: DNS no longer listens on WAN, No-IP DDNS removed, dead name server removed, Management/K8s DHCP ranges start at .2, stale 192.168.0.0/16 pool deleted · Unraid SMB `ntlm auth = ntlmv2-only` (`/boot/config/smb-extra.conf`) · `isoShare` NFS private, `10.0.50.0/24` only · HA trusted proxies = `10.0.3.11` only (restarted)
- [x] `jyou954.ddns.net` deleted in No-IP (verified: no longer resolves, 2026-09-30)
- Decided 2026-09-29, not doing: HA login banning (TOTP covers it; bans would lock out family devices) and Unraid web UI HTTPS (use `https://unraid.int…`; plain `http://10.0.3.11:8180` stays as the way in when Docker/Traefik is down)

## Home Assistant
- [x] HA VM crashed 2026-09-29 22:47 (QEMU USB assertion while the ZBT-2 reset; the ZBT-2 was attached twice via a leftover ConBee entry) and couldn't restart because the unplugged ConBee was required. Fixed 2026-09-30: ConBee entries removed from the VM and USB Manager, ZBT-2 matched by ID only and optional, so a missing stick never blocks HA. Backups `/mnt/user/vms/hl-haos-01/*.bak-20260930*`
- [x] Appdata Backup: `immich-machine-learning` set to Skip (only re-downloadable ML models), stops the nightly "does NOT exist" email (2026-09-30)
- [x] VM watchdog user script (every 5 min): restarts HA, Blue Iris or the CA VM after a crash, never after a normal shutdown; max 3/day; notifies
- [x] Zigbee2MQTT on the ZBT-2: fresh network with a regenerated key (2026-09-29; old key had been printed in chat). No devices were ever paired, so nothing to re-pair. Pair new devices via Z2M → Permit join
- ConBee II: Zigbee-only, **can't do Z-Wave**. Keep as a spare; only set up ZHA on it if a device Z2M doesn't support turns up (use a different channel, e.g. 15 or 20; Z2M is on 25)
- [ ] Z-Wave (if wanted): buy a Z-Wave stick, e.g. Home Assistant Connect ZWA-2, **ANZ 921.4 MHz version**
- [x] Save the dashboard / rename / update-flow scripts into this repo (`home-assistant/`)

- [x] Tablet: kiosk start page by IP, Overview hidden for `younghome`, reload on idle (done by you, 2026-09-30)
- [x] HA backup encryption key saved in Bitwarden
- [x] Meross LAN (HACS): plugs and garage opener local in HA; Seed Light schedule (08:00–midnight); Sensors page on both dashboards (2026-09-30)
- [x] Zigbee: Bedroom Curtain (Zemismart) and IKEA repeater (upstairs hallway) paired (2026-09-30)
- [ ] Seed Light plug went offline 2026-09-30 ~17:00 (not answering on `.226` or `.30`): check it has power. Then rerun `ha_tablet_dashboard.py` (both targets) so the Bedroom curtain card uses `cover.bedroom_curtain`
- [ ] Replace batteries: dining dimmer (0%), upstairs hallway switch (0%), front study switch (4%), front yard motion (10%), backyard motion (13%). The Sensors page lists anything under 20%
- [ ] Garage: the Home page Garage card still uses the old Shelly (`binary_sensor.garage_status`; Shelly integration fails setup). Point it at `cover.garage_door` (Meross) and remove the Shelly
- [ ] Google voice ("close the bedroom curtain"): HA isn't linked to Google Home. Needs Nabu Casa or a manual Google Assistant setup
- [ ] Curtains: any other Zemismart motors → pair to Z2M (Learn 3 quick presses)

## Housekeeping
- [ ] After the next Unraid reboot: check NUT came up (`upsc -c ups@127.0.0.1` lists `127.0.0.1`)
- [x] Deleted `/root/install_waiter.sh` on Unraid (watcher done)
- Note: git on this PC uses Windows OpenSSH (`git config --global core.sshCommand`), needed for the `overlord_ed25519` key
- [ ] `claude_ed25519` key expires on Unraid, Synology and HA on **2026-12-31** (`expiry-time`). Renew or remove the `authorized_keys` lines before then.

## Offsite backup (parked until the TrueNAS version is known)
Target: your TrueNAS at the other house (not the old `truenas-scale` Tailscale device; that one can be removed). ~2 TB free. Scope: irreplaceable only (~1.1 TB): Immich photos, `personal`, `backups-family`, `backups-friends`, appdata/HA/flash backups.
- [ ] Reset the TrueNAS share user's password (Credentials → Users → Edit) and save it in Bitwarden
- [ ] Check the TrueNAS version (Dashboard → System Information: SCALE or CORE + release)
- [ ] Then: dedicated dataset + user (SSH key only, no SMB) · daily ZFS snapshots kept 30 days (Unraid can't delete them) · Tailscale on the TrueNAS with ACLs: only Unraid → TrueNAS SSH · restic (encrypted, key in Bitwarden) nightly from Unraid · first copy over the network or via USB seed
- If the TrueNAS admin is ever locked out: local console menu → "Change local administrator password" (data untouched). Encrypted pool + lost key = data lost

## Parked
- TrueNAS backup (share not mounted) and restic (disabled)
- Unraid disk balance, second parity drive
