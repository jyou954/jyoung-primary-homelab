"""Readable names for the What's Up Docker (WUD) entities and devices in Home Assistant.

python3 - < wud_entity_names.py

WUD names each update entity after the container's wud.display.name label, or the raw container name
when there is no label. This sets the HA registry name instead, so pushes and dashboards read well.
Rerun after adding containers; unknown containers get a tidied-up version of their container name.
"""
import base64
import json
import os
import socket
import struct

TOKEN = open("/run/s6/container_environment/SUPERVISOR_TOKEN").read().strip()

# Container name -> readable name. Containers with a wud.display.name label can be left out.
CONTAINERS = {
    "authentik-postgresql": "Authentik Database",
    "authentik-redis": "Authentik Redis",
    "authentik-server": "Authentik",
    "authentik-worker": "Authentik Worker",
    "bookstack-server": "BookStack",
    "bookstack-mariadb": "BookStack Database",
    "grafana": "Grafana",
    "homepage": "Homepage",
    "immich-machine-learning": "Immich Machine Learning",
    "immich-server": "Immich",
    "node_exporter": "Node Exporter",
    "paperless-gotenberg": "Paperless Gotenberg",
    "paperless-postgresql": "Paperless Database",
    "paperless-redis": "Paperless Redis",
    "paperless-server": "Paperless",
    "paperless-tika": "Paperless Tika",
    "prometheus": "Prometheus",
    "semaphore-postgresql": "Semaphore Database",
    "semaphore-server": "Semaphore",
    "socket-proxy-authentik": "Authentik Socket Proxy",
    "socket-proxy-traefik": "Traefik Socket Proxy",
    "socket-proxy-wud": "WUD Socket Proxy",
    "unifi": "UniFi Controller",
    "unraid-technitium": "Technitium DNS",
    "unraid-traefik": "Traefik",
    "vaultwarden": "Vaultwarden",
    "wud": "What's Up Docker",
}

# Databases are never updated from HA: their update entities are disabled, which hides them and their
# Install button. Update them by hand with a dump first (see unraid/README.md). WUD's web UI still lists them.
DATABASES = {
    "authentik-postgresql", "authentik-redis", "bookstack-mariadb", "paperless-postgresql",
    "paperless-redis", "semaphore-postgresql", "immich-postgresql", "immich-redis",
}

OTHER_ENTITIES = {
    "sensor.wud_container_update_count": "Container Updates Available",
    "sensor.wud_container_total_count": "Containers Watched",
    "binary_sensor.wud_container_update_status": "Container Updates Pending",
    "binary_sensor.wud_container_status": "Container Update Checker Connected",
    "sensor.wud_container_unraid_update_count": "Unraid Container Updates Available",
    "sensor.wud_container_unraid_total_count": "Unraid Containers Watched",
    "binary_sensor.wud_container_unraid_update_status": "Unraid Container Updates Pending",
    "binary_sensor.wud_container_unraid_running": "Unraid Container Check Running",
}

DEVICES = {"wud": "What's Up Docker", "wud_unraid": "Unraid Containers"}


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
    if len(d) < 126:
        h = bytearray([0x81, 0x80 | len(d)])
    elif len(d) < 65536:
        h = bytearray([0x81, 0x80 | 126]) + struct.pack(">H", len(d))
    else:
        h = bytearray([0x81, 0x80 | 127]) + struct.pack(">Q", len(d))
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


sock = socket.create_connection(("supervisor", 80), timeout=30)
sock.sendall(("GET /core/websocket HTTP/1.1\r\nHost: supervisor\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
              "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % base64.b64encode(os.urandom(16)).decode()).encode())
hd = b""
while b"\r\n\r\n" not in hd:
    hd += sock.recv(1)
ws_recv(sock)
ws_send(sock, {"type": "auth", "access_token": TOKEN})
ws_recv(sock)
next_id = 0


def call(msg):
    global next_id
    next_id += 1
    ws_send(sock, dict(msg, id=next_id))
    while True:
        r = ws_recv(sock)
        if r.get("id") == next_id:
            if not r.get("success"):
                raise RuntimeError(r.get("error"))
            return r.get("result")


def readable(container):
    return CONTAINERS.get(container) or container.replace("_", " ").replace("-", " ").title()


prefix = "update.wud_container_unraid_"
entities = [e for e in call({"type": "config/entity_registry/list"}) if e["entity_id"].startswith("update.wud_")
            or e["entity_id"] in OTHER_ENTITIES]
by_key = {c.replace("-", "_").replace(".", "_"): c for c in CONTAINERS}
for e in sorted(entities, key=lambda x: x["entity_id"]):
    eid = e["entity_id"]
    if eid in OTHER_ENTITIES:
        name = OTHER_ENTITIES[eid]
    else:
        key = eid[len(prefix):] if eid.startswith(prefix) else eid.split(".", 1)[1]
        name = readable(by_key.get(key, key))
    container = by_key.get(eid[len(prefix):]) if eid.startswith(prefix) else None
    update = {}
    if e.get("name") != name:
        update["name"] = name
    if container in DATABASES and e.get("disabled_by") is None:
        update["disabled_by"] = "user"
    if update:
        call(dict({"type": "config/entity_registry/update", "entity_id": eid}, **update))
    print("%-55s %s%s%s" % (eid, name, "" if update else " (unchanged)",
                            " [disabled: database]" if container in DATABASES else ""))

for d in call({"type": "config/device_registry/list"}):
    for domain, ident in d.get("identifiers", []):
        if domain == "mqtt" and ident in DEVICES and d.get("name_by_user") != DEVICES[ident]:
            call({"type": "config/device_registry/update", "device_id": d["id"], "name_by_user": DEVICES[ident]})
            print("device %-48s %s" % (d["name"], DEVICES[ident]))
