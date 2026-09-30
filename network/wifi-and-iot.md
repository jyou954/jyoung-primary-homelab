# Wi-Fi and IoT network

Set up 2026-09-30. Firewall and VLAN basics are in `TODO.md` (Network sections) and `switch-ports.md`.

## UniFi (Wi-Fi only)
- Controller: container `unifi` on Unraid, UniFi Network 10.0.162, `https://unifi.int.jyoung-primary.com` or `https://10.0.3.11:9443`. Inform URL `http://10.0.3.11:8080/inform`. Auto-backups in `/mnt/user/appdata/unifi/data/data/backup/autobackup/`.
- The old controller was lost, so both APs were factory-reset and adopted on 2026-09-30 (firmware 5.43 → 6.8.2). The Wi-Fi networks were recreated by hand with the old names and passwords.
- Device SSH user is set in the controller (Settings → System → Advanced → Device Authentication); the password is in Bitwarden.
- Wireless Meshing is off (both APs are wired).

| AP | MAC | IP (router DHCP reservation) | Switch port |
|---|---|---|---|
| AP Downstairs (UAP-AC-Lite) | `fc:ec:da:37:88:dc` | `10.0.3.41` | es16 0/15 |
| AP Upstairs (UAP-AC-Lite) | `fc:ec:da:37:3c:a8` | `10.0.3.42` | es16 0/13 |

Keep the APs on DHCP with router reservations. The old ones had static `10.0.2.x` addresses that stranded them when the subnet changed.

## Wi-Fi networks
Only the Wi-Fi name is visible outside; the network names inside UniFi and the router can be descriptive.

| Wi-Fi name | UniFi network | VLAN | Settings | Used by |
|---|---|---|---|---|
| Aries | Aries (Default) | untagged (main LAN `10.0.3.0/24`) | WPA2, PMF optional | family phones, PCs |
| Indus IoT | Indus | 40 | WPA2, PMF off, band steering off, BSS transition off | the IoT devices that were joined before 2026-09-30 (old password, kept so they didn't all need re-joining) |
| Indus | Indus | 40 | same as Indus IoT, new password | where IoT devices go from now on |
| Gemini | Gemini | 80 (guests) | WPA2, client isolation on | guests: internet only |
| Fornax (not broadcast yet) | Fornax | 20 (`10.0.20.0/24`) | router, DHCP, firewall and switches ready (2026-09-30); create the Wi-Fi once Indus IoT is gone | parents: internet plus HA, cameras, casting, printer |

- **Indus IoT** is being phased out: move devices to **Indus** when they are re-paired anyway. Delete it once UniFi shows 0 clients on it.
- **Wi-Fi names are case- and space-sensitive.** The IoT network was first recreated as "Indus" instead of "Indus IoT" and no IoT device reconnected until the exact name was restored.
- UAP-AC-Lite broadcasts at most about 4 networks per band. Finish the Indus IoT migration before adding Fornax, or limit Indus IoT to 2.4 GHz.
- Never give out the Indus password (every IoT device shares it). Guests who want to cast use Gemini with a casting rule (see `TODO.md`).

## IoT VLAN 40 addresses
DHCP pool is `10.0.40.100`–`.254` (since 2026-09-30). `.2`–`.99` is for reservations only, in blocks. The router runs DHCP with dnsmasq, which never hands a reserved address to another device.

| Block | Address | Device | MAC |
|---|---|---|---|
| Hubs and servers `.2`–`.9` | `.3` | Xiaomi gateway | `54:ef:44:cc:ee:e5` |
| | `.4` | LG TV (wired, es48 0/47) | `a8:23:fe:8c:11:20` |
| | `.6` | Mosquitto | `02:42:0a:00:28:06` |
| | `.7` | Home Assistant | `52:54:00:71:84:c9` |
| Cameras `.10`–`.19` | `.10` | Front doorbell (Amcrest AD410) | `9c:8e:cd:37:cb:ee` |
| TVs and media `.20`–`.29` | `.20` | Chromecast Ultra "Study TV" | `90:0c:c8:dd:20:71` |
| | `.21`, `.22` | kept for the Sony and Changhong TVs | |
| Plugs `.30`–`.39` | `.30` | Meross Seed Light Plug | `c4:e7:ae:25:6c:6b` |
| | `.32` | Meross Study Air Purifier Plug | `c4:e7:ae:25:66:9f` |
| | `.33` | Meross Spare Plug | `c4:e7:ae:25:ab:b6` |
| | `.34` | kept for the Hydro Tower plug (offline) | |
| Garage and doors `.40`–`.49` | `.40` | Meross garage opener (MSG100) | `c4:e7:ae:23:63:61` |
| Legacy | `.150` | Shelly 2.5 garage opener (offline) | `4c:75:25:32:fb:23` |

Devices found by name (Google Homes, Nest Hubs, phones) stay on the automatic pool. Reserve an address only when something points at the IP (a firewall rule, an integration, a bookmark).

## Fornax VLAN 20 (family)
- Router `eth3.20` `10.0.20.1/24`, DHCP `.100`–`.254` (DNS = router, so `*.int` resolves), in the mDNS repeater.
- `family_in` (default accept = internet): related/established; HA `10.0.40.7:8123`; Traefik `10.0.3.11:443` (HA, Blue Iris, Immich via `*.int`); casting to `10.0.40.0/24` TCP `8008-8009,8443,32000-32999`; printer `10.0.3.15` TCP `631,9100`; reject `PROTECT_NETWORKS`.
- `family_local` (default drop): related/established, DNS, DHCP, NTP, ping, mDNS.
- Switches: VLAN 20 "Fornax Family VLAN" in the VLAN database on both; trunk ports carry it (es48 0/51, 0/52, es16 0/17, 0/13, 0/15).
- Traefik also serves the admin sites (Unraid, Grafana, ...), which still ask for their own logins. Optional: a Traefik IP allow-list to hide them from `10.0.20.0/24`.
- To switch on: create the Fornax Wi-Fi in UniFi (network Fornax, WPA2), install the internal root CA on the parents' phones, test HA/Blue Iris work and Unraid/NAS/router are blocked.

## EdgeRouter scripting limits (learned 2026-09-30)
- Scripted commits that create or change firewall rule sets fail (`iptables-restore: line 2 failed`, "Unexpected static status", or `group [...] is of type [Invalid]`), also with `sg vyattacfg`. Do firewall rule sets in the web UI. Attaching an existing rule set to an interface by script works.
- A failed commit is **not all-or-nothing**: the parts that succeed stay applied, and `save` then writes them. A half-created VLAN left an orphaned kernel device (`RTNETLINK answers: File exists` on the next try); `sudo ip link delete eth3.<vlan>` cleared it. Check with `show configuration commands` after any failure.

## Router rules added 2026-09-30
- **`iot_vlan_local` rule 4 "Accept mDNS"**: UDP 5353 to `224.0.0.251`. Without it the mDNS repeater (`eth3` ↔ `eth3.40`) never heard IoT devices, so phones on Aries couldn't find Chromecasts on IoT. Added in the web UI, because scripted firewall commits fail on this router.
- **LG TV tracking block** (`service dns forwarding options`, network-wide): `address=/<domain>/0.0.0.0` for `alphonso.tv` (ACR, "Live Plus"), `ngfts.lge.com`, `gfts.lge.com`, `lgsmartad.com`, `cdpbeacon.lgtvcommon.com`, `cdpsvc.lgtvcommon.com`, `lgrecommends.lgappstv.com`. Chosen from a capture of what the TV actually looked up. Left alone because the apps need them: `lgtvsdp.com`, `lgeapi.com`, `lgtvonline.lge.com`, `snu.lge.com` (firmware), all Netflix/YouTube/Spotify.
- **NAT rule 4010** (destination NAT): DNS from the LG TV (`10.0.40.4`) to anything other than the router is answered by the router. The TV sends about a third of its lookups straight to `8.8.8.8`, which would otherwise bypass the block. It is tied to `.4`, so keep the TV on its cable (on Wi-Fi it gets another address).
- On the TV itself: Live Plus off, User Agreements (viewing information, voice, interest-based ads) unticked, Home Promotion and Content Recommendation off, Limit Ad Tracking on.
- To undo a block: `delete service dns forwarding options "address=/<domain>/0.0.0.0"`, commit, save. The router already logs DNS queries (`/var/log/dnsmasq.log`), which shows what a device looks up.
