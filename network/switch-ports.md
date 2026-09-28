# Switch port map

Surveyed 2026-09-28 from MAC tables, LLDP and router DHCP/ARP. Port names below are set on the switches (`description`). Re-survey after moving cables.

## `jy-nw-es16`: EdgeSwitch 16 150W, `10.0.3.3`, fw 1.10.4
| Port | Name | What's there |
|---|---|---|
| 0/1 | Uplink - MikroTik CRS309 | MikroTik CRS309 (`10.0.10.2`, 10GbE VLAN 10) |
| 0/2 | Spare | — |
| 0/9 | Camera - Front .60.10 | IPC-CAM-FRONT-01, camera VLAN 60 |
| 0/11 | Camera - Back .60.20 | IPC-CAM-BACK-01, camera VLAN 60 |
| 0/13 | AP - AC Lite Upstairs | UAP-AC-Lite |
| 0/15 | AP - AC Lite Downstairs | UAP-AC-Lite |
| 0/16 | Pi4 - ADS-B .3.30 | Raspberry Pi 4 |
| 0/17 | Uplink - es48 0/52 | to `jy-nw-es48` 0/52 |

## `jy-nw-es48`: EdgeSwitch 48 Lite, `10.0.3.2`, fw 1.10.4
| Port | Name | What's there |
|---|---|---|
| 0/2 | UPS - CyberPower .3.14 | UPS network card (`https://ups.int.jyoung-primary.com`) |
| 0/4 | Server - Unraid (trunk) | Unraid + VMs (HA `10.0.40.7`, Technitium `10.0.3.254`), VLANs 1/40/50/51/60 |
| 0/6 | Server - TrueNAS | |
| 0/8 | Server - Proxmox 03 | **links at 100 Mbps**: check cable |
| 0/10 | Server - Proxmox 02 | down |
| 0/12 | Server - Proxmox 01 | down |
| 0/33 | Hue Bridge .3.60 | |
| 0/35 | Workstation 10GbE | **looped with 0/39** (see below) |
| 0/37 | PC - Workstation 1GbE | Workstation (LLDP) |
| 0/39 | *(blank)* | **looped with 0/35**; spanning tree blocks it |
| 0/41 | NAS - Synology .3.13 | |
| 0/43 | PC - Intel i9 | **links at 10 Mbps**: check cable |
| 0/45 | Server - Proxmox 04 vPro | down |
| 0/47 | TV - LG OLED | |
| 0/49 | Uplink - CRS309 SFP+3 | down |
| 0/51 | Uplink - ER4 eth3 (trunk) | EdgeRouter 4, all VLANs |
| 0/52 | Uplink - es16 0/17 | to `jy-nw-es16` 0/17 |

## Known issues
- **0/35 ↔ 0/39 loop:** each port's LLDP neighbour is this switch's other port, and 0/39 receives this switch's own MSTP BPDUs. Spanning tree (MSTP) keeps 0/39 blocked (it learns no MACs), so no storm, but one cable/path should be removed.
- **0/8** (100 Mbps) and **0/43** (10 Mbps): expected 1 Gbps, likely cable or port faults.

## Access
User `claude` (level 15) on both switches, password auth only (EdgeSwitch 1.10.4 has no SSH user keys). The password is in Vaultwarden. `enable` uses the same password. Remove when done: `configure`, then `no username claude`, then `exit`, then `write memory`.
