"""iPhone update notifications with one-tap 'Install all' in a safe order that survives restarts.

python3 - < ha_update_notify.py                 create/refresh helper, script and automations
python3 - --send-now < ha_update_notify.py      also send the 'updates available' push right now

Pieces:
  input_boolean.updates_resume_after_restart   set just before Core/OS install, so the run resumes after the restart
  script.install_pending_updates               apps/cards first, then Core (restart), then OS (reboot)
  automation.notify_iphone_of_updates          one push listing all pending updates: Install all / Later
                                               (new update, debounced 5 min; weekly reminder Sun 10:00)
  automation.resume_updates_after_restart      on HA start, if the flag is on: clear it and continue the script
  automation.notify_iphone_of_container_updates  separate push for Unraid container updates (update.wud_*);
                                               these are never part of 'Install all'
"""
import base64
import json
import os
import socket
import struct
import sys
import time
import urllib.error
import urllib.request

TOKEN = open("/run/s6/container_environment/SUPERVISOR_TOKEN").read().strip()
H = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}
PHONE = "notify.mobile_app_jareds_iphone"
CORE = "update.home_assistant_core_update"
OS_ = "update.home_assistant_operating_system_update"
FLAG = "input_boolean.updates_resume_after_restart"


def api(path, body=None, method=None):
    req = urllib.request.Request("http://supervisor/core/api" + path, headers=H,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 method=method or ("POST" if body is not None else "GET"))
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"null")


# ---- helper (input_boolean) via websocket; REST can't create helpers
def exact(s, n):
    buf = b""
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c:
            raise EOFError
        buf += c
    return buf


def ws_send(s, o):
    d = json.dumps(o).encode()
    h = bytearray([0x81, 0x80 | len(d)]) if len(d) < 126 else bytearray([0x81, 0x80 | 126]) + struct.pack(">H", len(d))
    m = os.urandom(4)
    s.sendall(bytes(h) + m + bytes(b ^ m[i % 4] for i, b in enumerate(d)))


def ws_recv(s):
    msg = b""
    while True:
        b1, b2 = exact(s, 2)
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", exact(s, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", exact(s, 8))[0]
        p = exact(s, n)
        if (b1 & 0x0F) in (9, 10):
            continue
        msg += p
        if b1 & 0x80:
            return json.loads(msg)


states = {s["entity_id"]: s for s in api("/states")}
if FLAG not in states:
    sock = socket.create_connection(("supervisor", 80), timeout=30)
    sock.sendall(("GET /core/websocket HTTP/1.1\r\nHost: supervisor\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % base64.b64encode(os.urandom(16)).decode()).encode())
    hd = b""
    while b"\r\n\r\n" not in hd:
        hd += sock.recv(1)
    ws_recv(sock)
    ws_send(sock, {"type": "auth", "access_token": TOKEN})
    ws_recv(sock)
    ws_send(sock, {"id": 1, "type": "input_boolean/create", "name": "Updates resume after restart", "icon": "mdi:update"})
    r = ws_recv(sock)
    print("helper:", "created" if r.get("success") else r.get("error"))
else:
    print("helper: exists")

HAS_BACKUP = "(state_attr(%s, 'supported_features') | int(0)) | bitwise_and(8) > 0"
# Unraid container updates (update.wud_*, from What's Up Docker) are left out of the HA flow:
# they have their own push, and "Install all" must never update containers.
PENDING = "states.update | rejectattr('entity_id', 'match', 'update.wud_') | selectattr('state', 'eq', 'on')"
PENDING_OTHER = ("{{ %s | map(attribute='entity_id')"
                 " | reject('in', ['%s', '%s']) | list }}" % (PENDING, CORE, OS_))
SUMMARY = ("{% for s in " + PENDING + " %}"
           "{{ s.attributes.title or s.name }}: {{ s.attributes.installed_version }} -> {{ s.attributes.latest_version }}\n"
           "{% endfor %}")


def install(entity_tpl):
    """update.install, with a backup first when the update supports it; never stop the run on one failure."""
    return {"if": [{"condition": "template", "value_template": "{{ %s }}" % (HAS_BACKUP % entity_tpl)}],
            "then": [{"action": "update.install", "target": {"entity_id": "{{ %s }}" % entity_tpl},
                      "data": {"backup": True}, "continue_on_error": True}],
            "else": [{"action": "update.install", "target": {"entity_id": "{{ %s }}" % entity_tpl},
                      "continue_on_error": True}]}


def push(title, message, tag="ha_updates"):
    return {"action": PHONE, "data": {"title": title, "message": message, "data": {"tag": tag}}}


script = {
    "alias": "Install pending updates",
    "description": "Installs every pending update in a safe order: apps/cards first, then Core (HA restarts), "
                   "then OS (reboots). Sets %s before a restart so automation.resume_updates_after_restart "
                   "continues the run." % FLAG,
    "mode": "single",
    "sequence": [
        {"variables": {"others": PENDING_OTHER,
                       # HACS custom integrations only load after a restart (cards just need a browser refresh).
                       "need_restart": "{{ others | select('in', integration_entities('hacs')) | list | count > 0 }}"}},
        {"repeat": {"for_each": "{{ others }}", "sequence": [install("repeat.item")]}},
        {"choose": [
            {"conditions": [{"condition": "state", "entity_id": CORE, "state": "on"}],
             "sequence": [
                 {"action": "input_boolean.turn_on", "target": {"entity_id": FLAG}},
                 push("Installing Home Assistant Core",
                      "HA will restart. Remaining updates continue automatically afterwards."),
                 install("'%s'" % CORE)]},
            {"conditions": [{"condition": "state", "entity_id": OS_, "state": "on"}],
             "sequence": [
                 {"action": "input_boolean.turn_on", "target": {"entity_id": FLAG}},
                 push("Installing Home Assistant OS", "HA will reboot for a few minutes."),
                 install("'%s'" % OS_)]}],
         "default": [
             {"action": "input_boolean.turn_off", "target": {"entity_id": FLAG}},
             push("Updates finished",
                  "{% set left = " + PENDING + " | map(attribute='name') | list %}"
                  "{{ 'All updates installed.' if not left else 'Still pending (install failed?): ' ~ left | join(', ') }}"),
             {"if": [{"condition": "template", "value_template": "{{ need_restart }}"}],
              "then": [push("Restarting Home Assistant", "Loading the updated custom integrations. Back in about a minute."),
                       {"action": "homeassistant.restart"}]}]},
    ],
}
print("script:", api("/config/script/config/install_pending_updates", script))

updates = sorted(e for e in states if e.startswith("update.") and not e.startswith("update.wud_"))
notify = {
    "id": "notify_iphone_of_updates",
    "alias": "Notify iPhone of updates",
    "description": "One push listing all pending updates with Install all / Later. Fires 5 min after a new update "
                   "appears (bursts collapse into one) and as a weekly reminder on Sundays at 10:00. "
                   "Update entities are listed explicitly; rerun ha_update_notify.py after adding integrations.",
    "mode": "restart",
    "triggers": [
        {"trigger": "state", "entity_id": updates, "from": "off", "to": "on", "id": "new"},
        {"trigger": "time", "at": "10:00:00", "id": "weekly"},
    ],
    "conditions": [{"condition": "template", "value_template": "{{ trigger.id == 'new' or now().weekday() == 6 }}"}],
    "actions": [
        {"if": [{"condition": "trigger", "id": "new"}], "then": [{"delay": "00:05:00"}]},
        {"condition": "template", "value_template": "{{ %s | list | count > 0 }}" % PENDING},
        {"condition": "state", "entity_id": "script.install_pending_updates", "state": "off"},
        {"variables": {"act_install": "{{ 'UPDATES_INSTALL_' ~ context.id }}",
                       "act_later": "{{ 'UPDATES_LATER_' ~ context.id }}"}},
        {"action": PHONE, "data": {
            "title": "{{ %s | list | count }} Home Assistant updates" % PENDING,
            "message": SUMMARY + "Order: apps first, then Core (restart), then OS (reboot).",
            "data": {"tag": "ha_updates", "actions": [
                {"action": "{{ act_install }}", "title": "Install all", "authenticationRequired": True},
                {"action": "{{ act_later }}", "title": "Later"}]}}},
        {"wait_for_trigger": [
            {"trigger": "event", "event_type": "mobile_app_notification_action", "event_data": {"action": "{{ act_install }}"}},
            {"trigger": "event", "event_type": "mobile_app_notification_action", "event_data": {"action": "{{ act_later }}"}}],
         "timeout": "24:00:00", "continue_on_timeout": False},
        {"condition": "template", "value_template": "{{ wait.trigger.event.data.action == act_install }}"},
        {"action": "script.turn_on", "target": {"entity_id": "script.install_pending_updates"}},
    ],
}
print("notify automation:", api("/config/automation/config/notify_iphone_of_updates", notify))

CONTAINERS_PENDING = "states.update | selectattr('entity_id', 'match', 'update.wud_') | selectattr('state', 'eq', 'on')"
container_notify = {
    "id": "notify_iphone_of_container_updates",
    "alias": "Notify iPhone of container updates",
    "description": "One push listing Unraid container updates found by What's Up Docker (report-only). "
                   "Waits 10 min so bursts collapse into one push. Tapping it opens the WUD page. Updates are "
                   "approved by hand (Compose Manager > Update Stack); HA's Install buttons do nothing.",
    "mode": "restart",
    "triggers": [{"trigger": "state", "entity_id": "sensor.wud_container_update_count"}],
    "conditions": [{"condition": "template", "value_template":
                    "{{ trigger.from_state is not none and trigger.from_state.state not in ['unknown', 'unavailable']"
                    " and trigger.to_state.state | int(0) > trigger.from_state.state | int(0) }}"}],
    "actions": [
        {"delay": "00:10:00"},
        {"condition": "template", "value_template": "{{ %s | list | count > 0 }}" % CONTAINERS_PENDING},
        {"action": PHONE, "data": {
            "title": "{% set n = " + CONTAINERS_PENDING + " | list | count %}{{ n }} container update{{ 's' if n > 1 }}",
            "message": "{% for s in " + CONTAINERS_PENDING + " %}"
                       "{% set a = s.attributes %}{{ s.name }}: "
                       "{{ 'new build of ' ~ a.installed_version if (a.latest_version or '') is match('sha256') "
                       "else a.installed_version ~ ' -> ' ~ a.latest_version }}\n{% endfor %}",
            "data": {"tag": "container_updates", "url": "https://wud.int.jyoung-primary.com"}}},
    ],
}
print("container notify automation:",
      api("/config/automation/config/notify_iphone_of_container_updates", container_notify))

resume = {
    "id": "resume_updates_after_restart",
    "alias": "Resume updates after restart",
    "description": "After a Core/OS update restarts HA, continue script.install_pending_updates.",
    "mode": "single",
    "triggers": [{"trigger": "homeassistant", "event": "start"}],
    "conditions": [{"condition": "state", "entity_id": FLAG, "state": "on"}],
    "actions": [
        {"action": "input_boolean.turn_off", "target": {"entity_id": FLAG}},
        {"delay": "00:02:00"},
        {"action": "script.turn_on", "target": {"entity_id": "script.install_pending_updates"}},
    ],
}
print("resume automation:", api("/config/automation/config/resume_updates_after_restart", resume))

try:
    print("old per-update script removed:", api("/config/script/config/ask_to_install_update", method="DELETE"))
except urllib.error.HTTPError as e:
    print("old per-update script: already gone (%s)" % e.code)

time.sleep(3)
for e in (FLAG, "script.install_pending_updates", "automation.notify_iphone_of_updates",
          "automation.resume_updates_after_restart", "automation.notify_iphone_of_container_updates"):
    try:
        print("%-45s %s" % (e, api("/states/" + e)["state"]))
    except urllib.error.HTTPError:
        print("%-45s MISSING" % e)

if "--send-now" in sys.argv:
    # Run just the push part: trigger the automation, skipping the 5-minute debounce (trigger.id is not 'new').
    # automation.trigger only returns when the run ends, and this run waits up to 24h for a tap.
    req = urllib.request.Request("http://supervisor/core/api/services/automation/trigger", headers=H, method="POST",
                                 data=json.dumps({"entity_id": "automation.notify_iphone_of_updates",
                                                  "skip_condition": True}).encode())
    try:
        urllib.request.urlopen(req, timeout=5)
    except (TimeoutError, OSError):
        pass
    print("push sent")
