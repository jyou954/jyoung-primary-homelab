"""Doorbell announcement at full volume, then put every speaker back to its previous volume. Does not trigger it."""
import json
import time
import urllib.request

T = open("/run/s6/container_environment/SUPERVISOR_TOKEN").read().strip()
H = {"Authorization": "Bearer " + T, "Content-Type": "application/json"}
AID = "1752144414825"
SPEAKERS = ["media_player.kitchen_mini", "media_player.kitchen_hub", "media_player.living_room_mini",
            "media_player.dining_room_mini", "media_player.front_study_speaker", "media_player.study_mini",
            "media_player.master_bedroom_display", "media_player.bedroom_hub",
            "media_player.guest_bedroom_speaker", "media_player.upstairs_hallway_mini"]


def api(path, body=None):
    req = urllib.request.Request("http://supervisor/core/api" + path, headers=H,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=120).read() or b"null")


automation = {
    "id": AID,
    "alias": "Doorbell announce Google Home",
    "description": ("Doorbell pressed: every speaker to 100%, say 'Someone is at the front door' on each speaker "
                    "individually (Cast groups cut short clips off), then restore each speaker's previous volume "
                    "(50% if it was off and had none). Audio is cached so repeat rings work offline."),
    "triggers": [{"trigger": "state", "entity_id": "binary_sensor.front_door_bell_ring", "from": "off", "to": "on"}],
    "conditions": [],
    "actions": [
        {"variables": {
            "speakers": SPEAKERS,
            "previous": ("{% set ns = namespace(items=[]) %}"
                         "{% for e in speakers %}{% set v = state_attr(e, 'volume_level') %}"
                         "{% set ns.items = ns.items + [[e, v if v is number else 0.5]] %}{% endfor %}"
                         "{{ ns.items }}"),
        }},
        {"action": "media_player.volume_set", "target": {"entity_id": "{{ speakers }}"},
         "data": {"volume_level": 1.0}, "continue_on_error": True},
        {"action": "tts.speak", "target": {"entity_id": "tts.google_translate_en_com"},
         "data": {"media_player_entity_id": "{{ speakers }}", "message": "Someone is at the front door", "cache": True}},
        {"delay": "00:00:07"},
        {"repeat": {"for_each": "{{ previous }}", "sequence": [
            {"action": "media_player.volume_set", "target": {"entity_id": "{{ repeat.item[0] }}"},
             "data": {"volume_level": "{{ repeat.item[1] }}"}, "continue_on_error": True}]}},
    ],
    "mode": "single",
}

before = api("/states/automation.doorbell_announce_google_home")["attributes"].get("last_triggered")
print("save:", api("/config/automation/config/" + AID, automation))
time.sleep(3)
s = api("/states/automation.doorbell_announce_google_home")
print("automation state:", s["state"], "| last_triggered unchanged (not fired):", s["attributes"].get("last_triggered") == before)
print("config check:", api("/config/core/check_config", {}).get("result"))

# Render the 'previous volumes' template against live states, without running anything.
tpl = "{% set speakers = " + json.dumps(SPEAKERS) + " %}" + automation["actions"][0]["variables"]["previous"]
req = urllib.request.Request("http://supervisor/core/api/template", headers=H, data=json.dumps({"template": tpl}).encode(), method="POST")
print("volumes it would restore right now:", urllib.request.urlopen(req, timeout=30).read().decode())
