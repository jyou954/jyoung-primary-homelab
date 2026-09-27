"""Give confusing Home Assistant entities readable display names. Entity IDs are never changed.

python3 - < ha_rename.py            dry run: show what would change
python3 - --apply < ha_rename.py    apply; old names saved to /config/entity_name_changes-<date>.json
"""
import json
import sys
import time
import urllib.request

APPLY = "--apply" in sys.argv
TOKEN = open("/run/s6/container_environment/SUPERVISOR_TOKEN").read().strip()

RENAMES = {
    # wrong or duplicate light names
    "light.dining_room_lamp": "Dining Room Lamp",
    "light.dining_room_light": "Dining Room Light 1", "light.dining_room_light_2": "Dining Room Light 2",
    "light.front_study_light": "Front Study Light 1", "light.front_study_light_2": "Front Study Light 2",
    "light.living_room_light": "Living Room Light 1", "light.living_room_light_2": "Living Room Light 2",
    "light.living_room_light_3": "Living Room Light 3",
    "light.study_light": "Study Light 1", "light.study_light_2": "Study Light 2",
    "light.downstairs_hallway_light": "Downstairs Hallway Light 1",
    "light.downstairs_hallway_light_2": "Downstairs Hallway Light 2",
    "light.upstairs_hallway_light": "Upstairs Hallway Light 1",
    "light.upstairs_hallway_light_2": "Upstairs Hallway Light 2",
    "light.downstairs_hallway_go": "Downstairs Hallway Hue Go",
    "light.planter_1": "Backyard Planter 1", "light.planter_2": "Backyard Planter 2",
    # Hue motion sensors: "X Motion Sensor Motion" etc.
    **{"binary_sensor.%s_motion_sensor_motion" % a: "%s Motion Sensor" % n for a, n in [
        ("backyard", "Backyard"), ("frontyard", "Front Yard"), ("downstairs_hallway", "Downstairs Hallway"),
        ("upstairs_hallway", "Upstairs Hallway"), ("stair", "Stairs")]},
    **{"sensor.%s_motion_sensor_illuminance" % a: "%s Light Level" % n for a, n in [
        ("backyard", "Backyard"), ("frontyard", "Front Yard"), ("downstairs_hallway", "Downstairs Hallway"),
        ("upstairs_hallway", "Upstairs Hallway"), ("stair", "Stairs")]},
    **{"sensor.%s_motion_sensor_temperature" % a: "%s Temperature" % n for a, n in [
        ("backyard", "Backyard"), ("frontyard", "Front Yard"), ("downstairs_hallway", "Downstairs Hallway"),
        ("upstairs_hallway", "Upstairs Hallway"), ("stair", "Stairs")]},
    # doorbell, garage, weather
    "camera.front_doorbell": "Front Doorbell",
    "binary_sensor.front_door_bell_human": "Front Doorbell Person Detected",
    "binary_sensor.front_door_bell_motion": "Front Doorbell Motion",
    "binary_sensor.front_door_bell_online": "Front Doorbell Online",
    "binary_sensor.front_door_bell_ring": "Front Doorbell Ring",
    "binary_sensor.garage_status": "Garage Door",
    "weather.forecast_home": "Weather",
    # speakers
    "media_player.guest_bedroom_speaker": "Guest Bedroom Speaker",
    "media_player.master_bedroom_display": "Master Bedroom Display",
    # backups
    "sensor.backup_backup_manager_state": "Backup Status",
    "sensor.backup_last_attempted_automatic_backup": "Last Backup Attempt",
    "sensor.backup_last_successful_automatic_backup": "Last Successful Backup",
    "sensor.backup_next_scheduled_automatic_backup": "Next Scheduled Backup",
    # FoxESS: plain words instead of inverter shorthand
    "sensor.foxess_bat_soc": "Battery Charge",
    "sensor.foxess_bat_soc1": "Battery 1 Charge",
    "sensor.foxess_bat_soh": "Battery Health",
    "sensor.foxess_bat_temperature": "Battery Temperature",
    "sensor.foxess_bat_charge": "Battery Energy Charged",
    "sensor.foxess_bat_discharge": "Battery Energy Discharged",
    "sensor.foxess_bat_charge_power": "Battery Charging Power",
    "sensor.foxess_bat_discharge_power": "Battery Discharging Power",
    "sensor.foxess_inverter_bat_power": "Battery Power",
    "sensor.foxess_bat_minsoc": "Battery Minimum Charge",
    "sensor.foxess_bat_minsocongrid": "Battery Minimum Charge (On Grid)",
    "sensor.foxess_max_bat_charge_current": "Battery Max Charge Current",
    "sensor.foxess_max_bat_discharge_current": "Battery Max Discharge Current",
    "sensor.foxess_feedin": "Energy Exported to Grid",
    "sensor.foxess_feedin_power": "Grid Export Power",
    "sensor.foxess_grid_consumption": "Energy Imported from Grid",
    "sensor.foxess_grid_consumption_power": "Grid Import Power",
    "sensor.foxess_load": "House Energy Used",
    "sensor.foxess_load_power": "House Power",
    "sensor.foxess_solar": "Solar Energy",
    "sensor.foxess_energy_generated_month": "Energy Generated This Month",
    "sensor.foxess_inv_temperature": "Inverter Temperature",
    "sensor.foxess_ambient_temperature": "Inverter Ambient Temperature",
    "sensor.foxess_running_state": "Inverter Running State",
    "sensor.foxess_response_time": "FoxESS Cloud Response Time",
    **{"sensor.foxess_pv%d_%s" % (i, k): "Solar String %d %s" % (i, v)
       for i in (1, 2, 3) for k, v in (("volt", "Voltage"), ("current", "Current"), ("power", "Power"))},
    **{"sensor.foxess_%s_%s" % (p, k): "Grid Phase %s %s" % (p.upper(), v)
       for p in ("r", "s", "t") for k, v in (("volt", "Voltage"), ("current", "Current"), ("power", "Power"))},
    "sensor.foxess_r_freq": "Grid Phase R Frequency",
}

req = urllib.request.Request("http://supervisor/core/api/states", headers={"Authorization": "Bearer " + TOKEN})
states = {s["entity_id"]: s for s in json.load(urllib.request.urlopen(req))}
reg = {e["entity_id"]: e for e in json.load(open("/config/.storage/core.entity_registry"))["data"]["entities"]}
try:
    exposed = json.load(open("/config/.storage/homeassistant.exposed_entities"))["data"]["exposed_entities"]
except (OSError, KeyError):
    exposed = {}

todo, skipped = [], []
for eid, new in RENAMES.items():
    if eid not in states:
        skipped.append("%s: no such entity" % eid)
        continue
    if eid not in reg:
        skipped.append("%s: not in entity registry, can't be renamed from here" % eid)
        continue
    old = states[eid]["attributes"].get("friendly_name", "")
    if old == new:
        continue
    voice = [a.split(".")[-1] for a, on in exposed.get(eid, {}).get("assistants", {}).items()
             if on.get("should_expose") and a != "conversation"]
    todo.append((eid, old, new, voice))

for eid, old, new, voice in todo:
    print("%-48s %-40s -> %s%s" % (eid, old, new, ("   [voice: %s]" % ",".join(voice)) if voice else ""))
print("\n%d to rename, %d skipped" % (len(todo), len(skipped)))
for s in skipped:
    print("  skipped " + s)
if not APPLY:
    print("\nDry run only. Rerun with --apply.")
    sys.exit(0)

import base64
import os
import socket
import struct


def exact(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf += chunk
    return buf


def ws_send(s, obj):
    data = json.dumps(obj).encode()
    hdr = bytearray([0x81])
    n = len(data)
    if n < 126:
        hdr.append(0x80 | n)
    elif n < 65536:
        hdr.append(0x80 | 126)
        hdr += struct.pack(">H", n)
    else:
        hdr.append(0x80 | 127)
        hdr += struct.pack(">Q", n)
    mask = os.urandom(4)
    s.sendall(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))


def ws_recv(s):
    msg = b""
    while True:
        b1, b2 = exact(s, 2)
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", exact(s, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", exact(s, 8))[0]
        if b2 & 0x80:
            exact(s, 4)
        payload = exact(s, n)
        op = b1 & 0x0F
        if op == 8:
            raise EOFError("server closed websocket")
        if op in (9, 10):
            continue
        msg += payload
        if b1 & 0x80:
            return json.loads(msg)


sock = socket.create_connection(("supervisor", 80), timeout=30)
sock.sendall(("GET /core/websocket HTTP/1.1\r\nHost: supervisor\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
              "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
              % base64.b64encode(os.urandom(16)).decode()).encode())
head = b""
while b"\r\n\r\n" not in head:
    head += sock.recv(1)
ws_recv(sock)
ws_send(sock, {"type": "auth", "access_token": TOKEN})
if ws_recv(sock).get("type") != "auth_ok":
    sys.exit("websocket auth failed")
next_id = [0]


def call(**msg):
    next_id[0] += 1
    msg["id"] = next_id[0]
    ws_send(sock, msg)
    while True:
        r = ws_recv(sock)
        if r.get("id") == msg["id"]:
            if not r.get("success"):
                raise RuntimeError("%s failed: %s" % (msg["type"], r.get("error")))
            return r.get("result")


revert = {}
for eid, old, new, voice in todo:
    revert[eid] = reg[eid].get("name")
    call(type="config/entity_registry/update", entity_id=eid, name=new)
path = "/config/entity_name_changes-%s.json" % time.strftime("%Y%m%d-%H%M%S")
json.dump({"note": "previous registry names (null = integration default); restore with config/entity_registry/update",
           "previous": revert}, open(path, "w"), indent=2)
print("applied %d renames; previous names saved to %s" % (len(todo), path))
