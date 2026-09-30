"""Build the Home Assistant dashboards and push them over the websocket API.

Runs inside the Advanced SSH add-on:
  python3 - [--force] < ha_tablet_dashboard.py            kiosk tablet dashboard at /tablet-home
  python3 - --target=overview < ha_tablet_dashboard.py    default Overview dashboard, plus Admin page
The tablet dashboard is only overwritten with --force. Overview is always overwritten.
"""
import base64
import json
import os
import socket
import struct
import sys
import urllib.request

ADMIN = "--target=overview" in sys.argv
URL_PATH = "lovelace" if ADMIN else "tablet-home"
TOKEN = open("/run/s6/container_environment/SUPERVISOR_TOKEN").read().strip()
FORCE = "--force" in sys.argv

req = urllib.request.Request("http://supervisor/core/api/states", headers={"Authorization": "Bearer " + TOKEN})
STATES = {s["entity_id"]: s for s in json.load(urllib.request.urlopen(req))}
# ---------------------------------------------------------------- websocket


def ws_open():
    s = socket.create_connection(("supervisor", 80), timeout=30)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall(("GET /core/websocket HTTP/1.1\r\nHost: supervisor\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % key).encode())
    head = b""
    while b"\r\n\r\n" not in head:
        head += s.recv(1)
    if b" 101 " not in head.split(b"\r\n", 1)[0]:
        sys.exit("websocket handshake failed: %s" % head.split(b"\r\n", 1)[0].decode())
    return s


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


def exact(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf += chunk
    return buf


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


sock = ws_open()
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
                sys.exit("%s failed: %s" % (msg["type"], r.get("error")))
            return r.get("result")


# IDs of real admin users, so the Admin page and tile are hidden from everyone else (e.g. the kiosk tablet).
ADMIN_IDS = [u["id"] for u in call(type="config/auth/list")
             if not u.get("system_generated") and u.get("is_active") and "system-admin" in (u.get("group_ids") or [])]
if ADMIN and not ADMIN_IDS:
    sys.exit("no admin users found; refusing to build an Admin page nobody can see")

# ---------------------------------------------------------------- rooms
# (name, icon, hue room group, individual lights, scene prefix, temperature sensor, motion sensor)
ROOMS = [
    ("Living Room", "mdi:sofa", "light.living_room",
     ["light.living_room_light", "light.living_room_light_2", "light.living_room_light_3", "light.living_room_strip"],
     "living_room", "sensor.stair_motion_sensor_temperature", "binary_sensor.stair_motion_sensor_motion"),
    ("Dining Room", "mdi:silverware-fork-knife", "light.dining_room",
     ["light.dining_room_light", "light.dining_room_light_2", "light.dining_room_lamp"],
     "dining_room", None, None),
    ("Front Study", "mdi:bookshelf", "light.front_study",
     ["light.front_study_light", "light.front_study_light_2"],
     "front_study", None, None),
    ("Study", "mdi:desk", "light.study",
     ["light.study_light", "light.study_light_2", "light.study_desk_strip"],
     "study", None, None),
    ("Bedroom", "mdi:bed", "light.bedroom",
     ["light.bedroom_lamp_2"],
     "bedroom", None, None),
    ("Downstairs Hallway", "mdi:stairs-down", "light.downstairs_hallway",
     ["light.downstairs_hallway_light", "light.downstairs_hallway_light_2", "light.downstairs_hallway_go"],
     "downstairs_hallway", "sensor.downstairs_hallway_motion_sensor_temperature", "binary_sensor.downstairs_hallway_motion"),
    ("Upstairs Hallway", "mdi:stairs-up", "light.upstairs_hallway",
     ["light.upstairs_hallway_light", "light.upstairs_hallway_light_2"],
     "upstairs_hallway", "sensor.upstairs_hallway_motion_sensor_temperature", "binary_sensor.upstairs_hallway_motion"),
    ("Front Yard", "mdi:flower-tulip-outline", "light.frontyard",
     ["light.frontyard_lily_%d" % i for i in range(1, 5)],
     "frontyard", "sensor.frontyard_motion_sensor_temperature", "binary_sensor.frontyard_motion"),
    ("Backyard", "mdi:tree-outline", "light.backyard",
     ["light.backyard_lily_%d" % i for i in range(1, 8)]
     + ["light.backyard_pedestal_1", "light.backyard_pedestal_2", "light.bamboo_light", "light.planter_1", "light.planter_2"],
     "backyard", "sensor.backyard_motion_sensor_temperature", "binary_sensor.backyard_motion"),
    # No lights, only curtains (see ROOM_COVERS).
    ("Second Bedroom", "mdi:bed-outline", None, [], "second_bedroom", None, None),
]
OUTDOOR = {"frontyard", "backyard"}
# Curtains per room (scene prefix -> covers). Zemismart BCM500DS-TYZ on Zigbee2MQTT.
ROOM_COVERS = {"bedroom": [("cover.bedroom_curtain", "Curtain")],
               "second_bedroom": [("cover.second_bedroom_curtains", "Both curtains"),
                                  ("cover.second_bedroom_blackout_curtain", "Blackout"),
                                  ("cover.second_bedroom_privacy_curtain", "Privacy screen")]}

LIGHT_NAMES = {
    "light.bedroom_lamp_2": "Lamp", "light.dining_room_lamp": "Lamp", "light.downstairs_hallway_go": "Hue Go",
    "light.study_desk_strip": "Desk strip", "light.living_room_strip": "Strip", "light.bamboo_light": "Bamboo",
    "light.planter_1": "Planter 1", "light.planter_2": "Planter 2",
}
SCENE_ORDER = [("bright", "mdi:brightness-7"), ("relax", "mdi:sofa-outline"), ("read", "mdi:book-open-variant"),
               ("concentrate", "mdi:head-lightbulb-outline"), ("energize", "mdi:lightning-bolt"),
               ("dimmed", "mdi:brightness-4"), ("nightlight", "mdi:weather-night")]


def light_name(eid, prefix):
    if eid in LIGHT_NAMES:
        return LIGHT_NAMES[eid]
    rest = eid.split(".", 1)[1]
    if rest.startswith(prefix + "_"):
        rest = rest[len(prefix) + 1:]
    if rest == "light":
        return "Light 1"
    return rest.replace("_", " ").capitalize()


def room_scenes(prefix, room):
    """Standard Hue scenes in a fixed order. Outdoor rooms, and every room on Overview, also get the rest."""
    picked, seen = [], set()
    for suffix, icon in SCENE_ORDER:
        eid = "scene.%s_%s" % (prefix, suffix)
        if eid in STATES and STATES[eid]["state"] != "unavailable":
            picked.append((eid, suffix.capitalize(), icon))
    if prefix in OUTDOOR or ADMIN:
        for eid, s in sorted(STATES.items()):
            if not eid.startswith("scene.%s_" % prefix) or s["state"] == "unavailable" or eid.endswith("new_scene"):
                continue
            name = s["attributes"].get("friendly_name", eid).lower()
            if any(eid == p[0] for p in picked) or name in seen:
                continue
            seen.add(name)
            label = s["attributes"].get("friendly_name", eid)
            for strip in (room + " ", "Frontyard ", "Backyard "):
                if label.lower().startswith(strip.lower()):
                    label = label[len(strip):]
            picked.append((eid, label[:1].upper() + label[1:], "mdi:palette-outline"))
    return picked


def action(service, entity_ids, confirm=None):
    a = {"action": "perform-action", "perform_action": service}
    if entity_ids:
        a["target"] = {"entity_id": entity_ids}
    if confirm:
        a["confirmation"] = {"text": confirm}
    return a


def cols(card, n):
    card["grid_options"] = {"columns": n}
    return card


def heading(text, icon, badges=None):
    h = {"type": "heading", "heading": text, "icon": icon, "heading_style": "title"}
    if badges:
        h["badges"] = [{"type": "entity", "entity": b, "show_state": True, "show_icon": True} for b in badges]
    return h


def light_card(entity, name, controls=True):
    c = {"type": "custom:mushroom-light-card", "entity": entity, "name": name,
         "use_light_color": True, "tap_action": {"action": "toggle"}, "hold_action": {"action": "more-info"}}
    if controls:
        c.update({"show_brightness_control": True, "collapsible_controls": True})
    return c


GROUPS = [r[2] for r in ROOMS if r[2]]


def spacer(height="28px"):
    return {"type": "custom:button-card", "show_name": False, "show_icon": False, "show_label": False,
            "tap_action": {"action": "none"}, "hold_action": {"action": "none"},
            "grid_options": {"columns": "full", "rows": "auto"},
            "styles": {"card": [{"height": height}, {"background": "none"}, {"box-shadow": "none"}, {"border": "none"}]}}


NAV_COLORS = {"amber": "#D98200", "purple": "#7E57C2", "green": "#2E7D32", "blue": "#1E6FD9", "slate": "#546E7A",
              "teal": "#00897B"}


def big_button(title, subtitle, icon, color, path, columns, height, icon_px):
    wrap = [{"white-space": "normal"}, {"overflow": "visible"}, {"text-overflow": "clip"}, {"color": "white"}]
    return {"type": "custom:button-card", "name": title, "label": subtitle, "show_label": True, "icon": icon,
            "tap_action": {"action": "navigate", "navigation_path": "/%s/%s" % (URL_PATH, path)},
            "grid_options": {"columns": columns, "rows": "auto"},
            "styles": {
                "card": [{"background-color": NAV_COLORS[color]}, {"border-radius": "18px"}, {"height": height},
                         {"padding": "12px"}, {"box-shadow": "0 4px 12px rgba(0,0,0,0.35)"}],
                "icon": [{"width": "%dpx" % icon_px}, {"color": "white"}],
                "name": [{"font-size": "22px"}, {"font-weight": "700"}] + wrap,
                "label": [{"font-size": "15px"}, {"opacity": "0.9"}] + wrap,
            }}


# Home's lights section spans 2 view columns, so its grid is 24 wide: 8 = a third, 6 = a quarter.
# Tablet has 4 buttons (one row of quarters); Overview adds Admin, so 5 (a row of 3, then 2).
def nav_card(title, subtitle, icon, color, path):
    return big_button(title, subtitle, icon, color, path, 8 if ADMIN else 6, "160px", 56)


def back_section(title="Back to Home", path="home"):
    card = big_button(title, "", "mdi:arrow-left-circle", "blue", path, "full", "84px", 44)
    card["show_label"] = False
    card["styles"]["grid"] = [{"grid-template-areas": '"i n"'}, {"grid-template-columns": "48px auto"},
                              {"justify-content": "center"}, {"align-items": "center"}, {"column-gap": "14px"}]
    card["styles"]["img_cell"] = [{"width": "48px"}, {"height": "48px"}]
    card["styles"]["name"] = [{"font-size": "26px"}, {"font-weight": "700"}, {"color": "white"}]
    return {"type": "grid", "column_span": 3, "cards": [card]}

# ---------------------------------------------------------------- Home view
home_header = {"type": "grid", "column_span": 3, "cards": [
    cols({"type": "custom:mushroom-title-card",
          "title": "Good {{ 'morning' if now().hour < 12 else 'afternoon' if now().hour < 18 else 'evening' }}",
          "subtitle": "{{ now().strftime('%A %-d %B') }}"}, 12),
    cols({"type": "custom:mushroom-chips-card", "alignment": "start", "chips": [
        {"type": "weather", "entity": "weather.forecast_home", "show_conditions": True, "show_temperature": True},
        {"type": "entity", "entity": "person.overlord", "use_entity_picture": True},
        {"type": "template", "icon": "mdi:solar-power-variant", "icon_color": "amber",
         "content": "{{ states('sensor.foxess_pv_power') | float(0) | round(1) }} kW solar",
         "tap_action": {"action": "navigate", "navigation_path": "/%s/energy" % URL_PATH}},
        {"type": "template",
         "icon": "{% set s = states('sensor.foxess_bat_soc') | int(0) %}mdi:battery{{ '' if s >= 95 else '-' ~ ((s // 10) * 10) if s >= 10 else '-outline' }}",
         "icon_color": "{% set s = states('sensor.foxess_bat_soc') | int(0) %}{{ 'green' if s > 50 else 'orange' if s > 20 else 'red' }}",
         "content": "{{ states('sensor.foxess_bat_soc') }}% battery",
         "tap_action": {"action": "navigate", "navigation_path": "/%s/energy" % URL_PATH}},
        {"type": "template", "icon": "mdi:lightbulb-group-off-outline", "icon_color": "red", "content": "All off",
         "tap_action": action("light.turn_off", GROUPS, "Turn off every light in the house and garden?")},
    ]}, 12),
]}

home_lights = {"type": "grid", "column_span": 2, "cards": [heading("Lights", "mdi:lightbulb-group")]
               + [cols(light_card(r[2], r[0]), 6) for r in ROOMS if r[2]]
               + [spacer(),
                  heading("More controls - tap a button", "mdi:gesture-tap-button"),
                  nav_card("Rooms & scenes", "Every light, room by room", "mdi:floor-plan", "amber", "rooms"),
                  nav_card("Music", "Speakers and volume", "mdi:music", "purple", "media"),
                  nav_card("Solar & battery", "Power and usage", "mdi:solar-power-variant", "green", "energy"),
                  nav_card("Sensors", "Doors, motion, temperature", "mdi:motion-sensor", "teal", "sensors")]
               + ([{"type": "conditional", "grid_options": {"columns": 8, "rows": "auto"},
                    "conditions": [{"condition": "user", "users": ADMIN_IDS}],
                    "card": nav_card("Admin", "Updates, backups, links", "mdi:shield-crown-outline", "slate", "admin")}]
                  if ADMIN else [])}

home_side = {"type": "grid", "cards": [
    heading("Front door", "mdi:doorbell-video"),
    cols({"type": "picture-entity", "entity": "camera.front_doorbell", "camera_view": "auto",
          "show_name": False, "show_state": False}, 12),
    cols({"type": "custom:mushroom-entity-card", "entity": "binary_sensor.garage_status", "name": "Garage",
          "icon": "mdi:garage-variant"}, 6),
    cols({"type": "custom:mushroom-entity-card", "entity": "binary_sensor.front_door_bell_human", "name": "Person at door",
          "icon": "mdi:account-eye"}, 6),
    heading("Energy", "mdi:lightning-bolt-circle"),
    cols({"type": "custom:mushroom-entity-card", "entity": "sensor.foxess_pv_power", "name": "Solar",
          "icon": "mdi:solar-power-variant", "icon_color": "amber"}, 6),
    cols({"type": "custom:mushroom-entity-card", "entity": "sensor.foxess_load_power", "name": "House",
          "icon": "mdi:home-lightning-bolt-outline", "icon_color": "blue"}, 6),
    cols({"type": "custom:mushroom-entity-card", "entity": "sensor.foxess_grid_consumption_power", "name": "From grid",
          "icon": "mdi:transmission-tower-import", "icon_color": "red"}, 6),
    cols({"type": "custom:mushroom-entity-card", "entity": "sensor.foxess_feedin_power", "name": "To grid",
          "icon": "mdi:transmission-tower-export", "icon_color": "green"}, 6),
    cols({"type": "gauge", "entity": "sensor.foxess_bat_soc", "name": "Battery", "min": 0, "max": 100, "needle": True,
          "severity": {"green": 50, "yellow": 20, "red": 0}}, 12),
]}

home_view = {"title": "Home", "path": "home", "icon": "mdi:home", "type": "sections", "max_columns": 3,
             "sections": [home_header, home_lights, home_side]}

# ---------------------------------------------------------------- Rooms view + one subview per room
# Rooms is a grid of big room buttons; each opens that room's own page (a subview: no tab in the top bar).
MAIN_SCENES = {"bright", "relax", "dimmed", "nightlight"}


def scene_chips(scenes):
    return cols({"type": "custom:mushroom-chips-card", "alignment": "start", "chips": [
        {"type": "template", "icon": ic, "icon_color": "amber", "content": label,
         "tap_action": action("scene.turn_on", eid)} for eid, label, ic in scenes]}, "full")


def room_path(prefix):
    return "room-" + prefix.replace("_", "-")


def room_button(name, icon, lights, covers, prefix, temp):
    """Room tile: amber while any light is on; the label says what's on, the temperature and curtain state."""
    watch = lights + [c for c, _ in covers] + ([temp] if temp else [])
    js = ("const L = %s; const C = %s; const T = %s;"
          "const on = L.filter(e => states[e] && states[e].state === 'on').length;"
          "const p = [];"
          "if (L.length) p.push(on ? on + (on === 1 ? ' light on' : ' lights on') : 'Lights off');"
          "if (C.length) { const o = C.filter(e => states[e] && states[e].state !== 'closed').length;"
          "  p.push(o ? 'Curtains open' : 'Curtains closed'); }"
          "if (T && states[T]) p.push(states[T].state + ' °C');"
          "return p.join(' · ');") % (json.dumps(lights), json.dumps([c for c, _ in covers][:1]), json.dumps(temp))
    bg = ("[[[ const L = %s; return L.some(e => states[e] && states[e].state === 'on') ? '%s' : '%s'; ]]]"
          % (json.dumps(lights), NAV_COLORS["amber"], NAV_COLORS["slate"]))
    card = big_button(name, "", icon, "slate", room_path(prefix), 12, "130px", 44)
    card["label"] = "[[[ " + js + " ]]]"
    card["triggers_update"] = watch
    card["styles"]["card"][0] = {"background-color": bg}
    return card


room_views, room_buttons = [], []
for name, icon, group, lights, prefix, temp, motion in ROOMS:
    covers = ROOM_COVERS.get(prefix, [])
    room_buttons.append(room_button(name, icon, lights, covers, prefix, temp))
    sections = [back_section("Back to Rooms", "rooms")]
    if group:
        light_cards = [heading(name + " lights", icon, [b for b in (temp, motion) if b]),
                       cols(light_card(group, "All " + name.lower()), "full")]
        if len(lights) > 1:
            light_cards += [cols(light_card(l, light_name(l, prefix)), 12) for l in lights]
        sections.append({"type": "grid", "cards": light_cards})
    side = []
    if covers:
        side += [heading("Curtains", "mdi:curtains")] + [
            cols({"type": "custom:mushroom-cover-card", "entity": c, "name": cname, "icon": "mdi:curtains",
                  "show_buttons_control": True, "show_position_control": True}, "full") for c, cname in covers]
    scenes = room_scenes(prefix, name)
    main = [s for s in scenes if s[0].rsplit("_", 1)[-1] in MAIN_SCENES]
    more = [s for s in scenes if s not in main]
    if main:
        side += [heading("Scenes", "mdi:palette"), scene_chips(main)]
    if more:
        side += [{"type": "heading", "heading": "More scenes", "heading_style": "subtitle"}, scene_chips(more)]
    if side:
        sections.append({"type": "grid", "cards": side})
    room_views.append({"title": name, "path": room_path(prefix), "icon": icon, "subview": True,
                       "back_path": "/%s/rooms" % URL_PATH, "type": "sections", "max_columns": 2,
                       "sections": sections})

# Room buttons grouped by HA floor (Settings > Areas > Floors), outdoor rooms last, alphabetical within each.
_floors = {f["floor_id"]: f["name"] for f in call(type="config/floor_registry/list")}
AREA_FLOOR = {a["area_id"]: _floors.get(a.get("floor_id")) for a in call(type="config/area_registry/list")}
FLOOR_ORDER = [("Ground Floor", "mdi:home-floor-g"), ("Upstairs", "mdi:home-floor-1"),
               ("Outside", "mdi:tree-outline"), ("Other", "mdi:home-outline")]


def room_floor(prefix):
    return "Outside" if prefix in OUTDOOR else (AREA_FLOOR.get(prefix) or "Other")


by_floor = {}
for r, button in zip(ROOMS, room_buttons):
    by_floor.setdefault(room_floor(r[4]), []).append((r[0], button))
floor_cards = []
for floor, ficon in FLOOR_ORDER:
    if floor in by_floor:
        floor_cards += [heading(floor, ficon)] + [b for _, b in sorted(by_floor[floor])]

# Rooms section spans all 3 view columns (36 wide): 12 = three room buttons per row.
rooms_view = {"title": "Rooms", "path": "rooms", "icon": "mdi:floor-plan", "type": "sections", "max_columns": 3,
              "sections": [back_section(), {"type": "grid", "column_span": 3, "cards": floor_cards}]}

# ---------------------------------------------------------------- Media view
# Groups are Cast groups (they use port 32xxx instead of 8009 in the Cast log).
SPEAKER_GROUPS = ["media_player.all_speakers", "media_player.downstairs", "media_player.upstairs",
                  "media_player.bedroom_speakers"]
SPEAKERS = ["media_player.living_room_mini", "media_player.kitchen_hub",
            "media_player.kitchen_mini", "media_player.dining_room_mini", "media_player.front_study_speaker",
            "media_player.study_mini", "media_player.master_bedroom_display", "media_player.bedroom_hub",
            "media_player.guest_bedroom_speaker", "media_player.upstairs_hallway_mini"]
PLAYERS = SPEAKER_GROUPS + SPEAKERS


def player_card(p, columns):
    return cols({"type": "custom:mushroom-media-player-card", "entity": p, "use_media_info": True,
                 "show_volume_level": True, "collapsible_controls": True,
                 "media_controls": ["play_pause_stop", "previous", "next"],
                 "volume_controls": ["volume_mute", "volume_set"]}, columns)


# Media section spans all 3 view columns, so its grid is 36 wide: 9 = a quarter, 6 = a sixth.
media_view = {"title": "Music", "path": "media", "icon": "mdi:music", "type": "sections", "max_columns": 3,
              "sections": [back_section(), {"type": "grid", "column_span": 3, "cards":
                  [heading("Speaker groups - play in several rooms at once", "mdi:speaker-multiple")]
                  + [player_card(p, 9) for p in SPEAKER_GROUPS]
                  + [spacer(), heading("Individual speakers", "mdi:speaker")]
                  + [player_card(p, 6) for p in SPEAKERS]}]}

# ---------------------------------------------------------------- Energy view


def daily_energy(days):
    return {"type": "statistics-graph", "chart_type": "bar", "period": "day", "days_to_show": days,
            "stat_types": ["change"], "entities": [
                {"entity": "sensor.foxess_solar", "name": "Solar made"},
                {"entity": "sensor.foxess_load", "name": "House used"},
                {"entity": "sensor.foxess_grid_consumption", "name": "Bought from grid"},
                {"entity": "sensor.foxess_feedin", "name": "Sold to grid"}]}


energy_view = {"title": "Solar", "path": "energy", "icon": "mdi:solar-power-variant", "type": "sections", "max_columns": 3,
               "sections": [
                   back_section(),
                   # Spans 2 view columns, so its grid is 24 wide.
                   {"type": "grid", "column_span": 2, "cards": [
                       heading("Last 24 hours", "mdi:chart-line"),
                       cols({"type": "history-graph", "hours_to_show": 24, "entities": [
                           {"entity": "sensor.foxess_pv_power", "name": "Solar"},
                           {"entity": "sensor.foxess_load_power", "name": "House"},
                           {"entity": "sensor.foxess_inverter_bat_power", "name": "Battery"},
                           {"entity": "sensor.foxess_grid_consumption_power", "name": "From grid"},
                           {"entity": "sensor.foxess_feedin_power", "name": "To grid"}]}, "full"),
                       heading("Last 7 days - energy per day", "mdi:calendar-week"),
                       cols(daily_energy(7), "full"),
                       heading("Last 30 days - energy per day", "mdi:calendar-month"),
                       cols(daily_energy(30), "full"),
                       heading("Energy totals", "mdi:counter"),
                       cols({"type": "entities", "entities": [
                           {"entity": "sensor.foxess_solar", "name": "Solar"},
                           {"entity": "sensor.foxess_load", "name": "House"},
                           {"entity": "sensor.foxess_grid_consumption", "name": "From grid"}]}, 12),
                       cols({"type": "entities", "entities": [
                           {"entity": "sensor.foxess_feedin", "name": "To grid"},
                           {"entity": "sensor.foxess_bat_charge", "name": "Battery charged"},
                           {"entity": "sensor.foxess_bat_discharge", "name": "Battery discharged"}]}, 12),
                   ]},
                   {"type": "grid", "cards": [
                       heading("Battery", "mdi:home-battery-outline"),
                       cols({"type": "gauge", "entity": "sensor.foxess_bat_soc", "name": "Charge", "min": 0, "max": 100,
                             "needle": True, "severity": {"green": 50, "yellow": 20, "red": 0}}, 12),
                       cols({"type": "history-graph", "hours_to_show": 24, "entities": [
                           {"entity": "sensor.foxess_bat_soc", "name": "Battery charge (24h)"}]}, 12),
                       cols({"type": "entities", "entities": [
                           {"entity": "sensor.foxess_inverter_bat_power", "name": "Power"},
                           {"entity": "sensor.foxess_bat_soh", "name": "Health"},
                           {"entity": "sensor.foxess_bat_temperature", "name": "Temperature"}]}, 12),
                       heading("Panels", "mdi:solar-panel"),
                       cols({"type": "entities", "entities": [
                           {"entity": "sensor.foxess_pv1_power", "name": "String 1"},
                           {"entity": "sensor.foxess_pv2_power", "name": "String 2"},
                           {"entity": "sensor.foxess_pv3_power", "name": "String 3"}]}, 12),
                       heading("Inverter", "mdi:solar-power"),
                       cols({"type": "entities", "entities": [
                           {"entity": "sensor.foxess_running_state", "name": "State"},
                           {"entity": "sensor.foxess_inv_temperature", "name": "Temperature"}]}, 12),
                   ]},
               ]}

# ---------------------------------------------------------------- Sensors view
# Hue motion sensors: (name, entity prefix). Each has _motion, _temperature, _illuminance and _battery.
MOTION_SENSORS = [("Stairs", "stair_motion_sensor"),
                  ("Downstairs hallway", "downstairs_hallway_motion_sensor"),
                  ("Upstairs hallway", "upstairs_hallway_motion_sensor"),
                  ("Front yard", "frontyard_motion_sensor"),
                  ("Backyard", "backyard_motion_sensor")]
# Meross plugs (local, Meross LAN): (name, entity prefix, icon)
PLUGS = [("Seed light", "seed_light", "mdi:sprout"), ("Study air purifier", "study_air_purifier", "mdi:air-purifier")]
# Every battery sensor that is reporting, lowest first when the page is built (FoxESS min-charge settings excluded).
BATTERIES = sorted((eid for eid, s in STATES.items()
                    if eid.startswith("sensor.") and s["attributes"].get("device_class") == "battery"
                    and s["attributes"].get("unit_of_measurement") == "%" and s["state"] not in ("unavailable", "unknown")
                    and not eid.startswith(("sensor.jareds_iphone", "sensor.foxess"))),
                   key=lambda e: float(STATES[e]["state"]))

# Live list (not fixed at build time) of batteries under 20%. Dashboards render templates in strict mode, so
# attributes are read with .get() (a missing device_class would otherwise blank the card).
LOW_BATTERY_MD = (
    "{% set ns = namespace(out=[]) %}{% for s in states.sensor %}"
    "{% if s.attributes.get('device_class') == 'battery' and s.state | is_number"
    " and 'jareds_iphone' not in s.entity_id and 'foxess' not in s.entity_id and s.state | float < 20 %}"
    "{% set ns.out = ns.out + ['- **' ~ s.name ~ '**: ' ~ s.state ~ '%'] %}{% endif %}"
    "{% endfor %}{{ ns.out | join('\\n') if ns.out else 'All batteries above 20%.' }}")


def sensor_card(entity, name, icon, color=None, tap=None):
    c = {"type": "custom:mushroom-entity-card", "entity": entity, "name": name, "icon": icon}
    if color:
        c["icon_color"] = color
    if tap:
        c["tap_action"] = tap
    return cols(c, 6)


# The garage opener only shows its state here; on the tablet a tap does nothing, so it can't be opened by accident.
garage_tap = None if ADMIN else {"action": "none"}
sensors_view = {"title": "Sensors", "path": "sensors", "icon": "mdi:motion-sensor", "type": "sections", "max_columns": 3,
                "sections": [
                    back_section(),
                    {"type": "grid", "cards": [
                        heading("Doors", "mdi:door"),
                        sensor_card("binary_sensor.front_door_sensor_contact", "Front door", "mdi:door", "blue"),
                        sensor_card("binary_sensor.back_door_sensor_contact", "Back door", "mdi:door", "blue"),
                        sensor_card("cover.garage_door", "Garage", "mdi:garage-variant", "blue", garage_tap),
                        sensor_card("binary_sensor.front_door_bell_human", "Person at door", "mdi:account-eye", "blue"),
                        heading("Plugs", "mdi:power-socket-au"),
                    ] + [c for name, p, icon in PLUGS for c in (
                        sensor_card("switch." + p, name, icon, "green", {"action": "toggle"}),
                        sensor_card("sensor.%s_power" % p, name + " power", "mdi:flash", "amber"))] + [
                        cols({"type": "statistics-graph", "chart_type": "bar", "period": "day", "days_to_show": 7,
                              "stat_types": ["change"], "title": "Energy per day (7 days)",
                              "entities": [{"entity": "sensor.%s_energy" % p, "name": name} for name, p, _ in PLUGS]},
                             12),
                    ]},
                    {"type": "grid", "cards": [
                        heading("Motion", "mdi:motion-sensor")]
                        + [sensor_card("binary_sensor.%s_motion" % p, name, "mdi:motion-sensor", "orange")
                           for name, p in MOTION_SENSORS]
                        + [heading("Temperature", "mdi:thermometer")]
                        + [sensor_card("sensor.%s_temperature" % p, name, "mdi:thermometer", "red")
                           for name, p in MOTION_SENSORS]
                        + [cols({"type": "history-graph", "hours_to_show": 24, "title": "Last 24 hours", "entities": [
                            {"entity": "sensor.%s_temperature" % p, "name": name} for name, p in MOTION_SENSORS]}, 12)]},
                    {"type": "grid", "cards": [
                        heading("Light level", "mdi:brightness-5")]
                        + [sensor_card("sensor.%s_illuminance" % p, name, "mdi:brightness-5", "yellow")
                           for name, p in MOTION_SENSORS]
                        + [heading("Batteries", "mdi:battery-alert-variant-outline"),
                           cols({"type": "markdown", "content": LOW_BATTERY_MD}, 12),
                           cols({"type": "entities", "title": "All batteries (lowest first)",
                                 "entities": BATTERIES}, 12)]},
                ]}

# ---------------------------------------------------------------- Admin view (Overview only)


def service_button(title, subtitle, icon, color, service, confirm):
    return cols({"type": "custom:mushroom-template-card", "primary": title, "secondary": subtitle, "icon": icon,
                 "icon_color": color, "tap_action": action(service, [], confirm)}, 12)


def link(title, address, icon, color, url=None, navigate=None):
    tap = {"action": "navigate", "navigation_path": navigate} if navigate else {"action": "url", "url_path": url}
    return cols({"type": "custom:mushroom-template-card", "primary": title, "secondary": address, "icon": icon,
                 "icon_color": color, "tap_action": tap}, 6)


UPDATES_MD = (
    "{% set u = states.update | selectattr('state', 'eq', 'on') | list %}"
    "{% if u %}{% for s in u %}- **{{ s.name }}**: {{ s.attributes.installed_version }} -> "
    "{{ s.attributes.latest_version }}\n{% endfor %}"
    "{% else %}Everything is up to date.{% endif %}")

BROKEN_MD = (
    "{% set b = states | selectattr('state', 'eq', 'unavailable')"
    " | rejectattr('domain', 'in', ['scene', 'button', 'event', 'conversation', 'tts', 'notify']) | list %}"
    "{% if b %}**{{ b | length }} unavailable**\n\n{% for s in b | sort(attribute='entity_id') %}"
    "- {{ s.name }} `{{ s.entity_id }}`\n{% endfor %}{% else %}Nothing unavailable.{% endif %}")

FOXESS_DIAG = ["running_state", "response_time", "inv_temperature", "ambient_temperature", "bat_temperature",
               "bat_soh", "bat_minsoc", "bat_minsocongrid", "max_bat_charge_current", "max_bat_discharge_current",
               "pv1_volt", "pv1_current", "pv2_volt", "pv2_current", "pv3_volt", "pv3_current",
               "r_volt", "r_current", "r_freq", "s_volt", "s_current", "t_volt", "t_current", "meter2_power"]

admin_view = {"title": "Admin", "path": "admin", "icon": "mdi:shield-crown-outline", "type": "sections",
              "visible": [{"user": uid} for uid in ADMIN_IDS],
              "max_columns": 3, "sections": [
    back_section(),
    {"type": "grid", "cards": [
        heading("Updates", "mdi:update"),
        cols({"type": "markdown", "content": UPDATES_MD}, 12),
        link("Open updates", "Settings > Updates", "mdi:package-up", "blue", navigate="/config/updates"),
        link("Open add-ons", "Settings > Apps", "mdi:puzzle", "blue", navigate="/_my_redirect/supervisor"),
        heading("Backups", "mdi:backup-restore"),
        cols({"type": "entities", "entities": [
            {"entity": "sensor.backup_backup_manager_state", "name": "Status"},
            {"entity": "sensor.backup_last_successful_automatic_backup", "name": "Last successful"},
            {"entity": "sensor.backup_last_attempted_automatic_backup", "name": "Last attempted"},
            {"entity": "sensor.backup_next_scheduled_automatic_backup", "name": "Next scheduled"}]}, 12),
        link("Open backups", "Settings > Backups", "mdi:backup-restore", "blue", navigate="/config/backup"),
        heading("System", "mdi:cog"),
        service_button("Restart Home Assistant", "Takes about a minute", "mdi:restart", "red",
                       "homeassistant.restart", "Restart Home Assistant now?"),
        service_button("Reload automations", "After editing automations", "mdi:robot", "orange",
                       "automation.reload", "Reload all automations?"),
        service_button("Reload scenes", "After editing scenes", "mdi:palette", "orange",
                       "scene.reload", "Reload all scenes?"),
    ]},
    {"type": "grid", "cards": [
        heading("Needs attention", "mdi:alert-circle-outline"),
        cols({"type": "markdown", "content": BROKEN_MD}, 12),
    ]},
    {"type": "grid", "cards": [
        heading("Quick links", "mdi:link-variant"),
        link("Unraid", "unraid.int.jyoung-primary.com", "mdi:server", "orange",
             url="https://unraid.int.jyoung-primary.com/login"),
        link("Unraid (IP)", "10.0.3.11:8180", "mdi:server", "grey", url="http://10.0.3.11:8180"),
        link("Technitium DNS", "unraid-technitium.int...", "mdi:dns", "teal",
             url="https://unraid-technitium.int.jyoung-primary.com:53443/"),
        link("Technitium (IP)", "10.0.3.11:5380", "mdi:dns", "grey", url="http://10.0.3.11:5380"),
        link("Synology", "10.0.3.13:5001", "mdi:nas", "blue", url="https://10.0.3.13:5001"),
        link("Grafana", "grafana.int.jyoung-primary.com", "mdi:chart-areaspline", "amber",
             url="https://grafana.int.jyoung-primary.com"),
        link("HA Settings", "Settings", "mdi:cog", "blue", navigate="/config/dashboard"),
        link("HA (IP)", "10.0.40.7:8123", "mdi:home-assistant", "grey", url="http://10.0.40.7:8123"),
        heading("Doorbell", "mdi:doorbell-video"),
        cols({"type": "entities", "entities": [
            {"entity": "binary_sensor.front_door_bell_online", "name": "Online"},
            {"entity": "binary_sensor.front_door_bell_ring", "name": "Ring"},
            {"entity": "binary_sensor.front_door_bell_motion", "name": "Motion"},
            {"entity": "binary_sensor.front_door_bell_human", "name": "Person"}]}, 12),
        heading("Phone", "mdi:cellphone"),
        cols({"type": "entities", "entities": [
            {"entity": "sensor.jareds_iphone_battery_level", "name": "Battery"},
            {"entity": "sensor.jareds_iphone_battery_state", "name": "Charging"},
            {"entity": "binary_sensor.jareds_iphone_kiosk_mode", "name": "Kiosk mode"},
            {"entity": "binary_sensor.jareds_iphone_kiosk_screensaver", "name": "Kiosk screensaver"}]}, 12),
    ]},
    {"type": "grid", "column_span": 3, "cards": [
        heading("Solar inverter diagnostics", "mdi:solar-power"),
        cols({"type": "entities", "entities": ["sensor.foxess_" + s for s in FOXESS_DIAG[:12]]}, 18),
        cols({"type": "entities", "entities": ["sensor.foxess_" + s for s in FOXESS_DIAG[12:]]}, 18),
    ]},
]}

views = [home_view, rooms_view, media_view, energy_view, sensors_view] + ([admin_view] if ADMIN else []) + room_views
CONFIG = {"title": "Home" if ADMIN else "Tablet", "views": views}

# ---------------------------------------------------------------- validate
used = set()


def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("entity", "entity_id") and isinstance(v, str):
                used.add(v)
            elif k == "entity_id" and isinstance(v, list):
                used.update(v)
            elif k == "entities" and isinstance(v, list):
                used.update(x for x in v if isinstance(x, str))
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(CONFIG)
bad = []
for eid in sorted(used):
    s = STATES.get(eid)
    if s is None:
        bad.append("missing: " + eid)
    elif s["state"] == "unavailable" or (s["state"] == "unknown" and not eid.startswith("scene.")):
        bad.append("%s: %s" % (s["state"], eid))
print("entities used: %d" % len(used))
if bad:
    print("NOT SAVED, broken entities in config:")
    print("\n".join("  " + b for b in bad))
    sys.exit(1)

if ADMIN:
    call(type="lovelace/config/save", config=CONFIG)
    print("saved Overview (/lovelace)")
else:
    existing = [d for d in call(type="lovelace/dashboards/list") if d["url_path"] == URL_PATH]
    if existing and not FORCE:
        sys.exit("dashboard /%s already exists; rerun with --force to overwrite it" % URL_PATH)
    if not existing:
        call(type="lovelace/dashboards/create", url_path=URL_PATH, title="Tablet", icon="mdi:tablet-dashboard",
             require_admin=False, show_in_sidebar=True, mode="storage")
        print("created dashboard /%s" % URL_PATH)
    call(type="lovelace/config/save", url_path=URL_PATH, config=CONFIG)
print("saved: %d views (%d room pages), %d speakers" % (len(CONFIG["views"]), len(room_views), len(PLAYERS)))
