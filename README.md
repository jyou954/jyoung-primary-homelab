# jyoung-primary-homelab

Config for the homelab, versioned. **The servers are the source of truth** — this repo is a copy. If you change something on a server, copy it back here and commit.

| Folder | Host | What |
|---|---|---|
| [`unraid/`](unraid/README.md) | Unraid `10.0.3.11` | User scripts, NUT (UPS), logrotate, boot `go` file, Docker compose stacks, container updates (WUD) |
| [`synology/`](synology/README.md) | Synology `10.0.3.13` | Backup target layout and retention, rotation task |
| [`network/`](network/switch-ports.md) | EdgeSwitches `10.0.3.2`, `10.0.3.3`; UniFi APs | Port map, known cabling issues; [Wi-Fi networks, IoT address plan, router DNS/mDNS rules](network/wifi-and-iot.md) |
| [`home-assistant/`](home-assistant/README.md) | HA `10.0.40.7` | Dashboard builder, update notifications (HA and containers), entity renames, automations snapshot |

Open work: [`TODO.md`](TODO.md).

## Rules
- **No secrets in git.** Passwords live in Bitwarden Secrets Manager. `*.env`, `upsd.users`, `upsmon.conf` are gitignored.
- Files are LF-only (`.gitattributes`). Don't convert to CRLF — bash scripts break with `\r` errors.
- Each folder's README says where every file goes and what it needs.
