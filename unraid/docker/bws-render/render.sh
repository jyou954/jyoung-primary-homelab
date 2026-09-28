#!/bin/sh
# Fetch every secret and render per-stack env files.
# Only keys matching "<stack>__<VAR>" where <stack> is in STACKS are rendered.
# All other secrets (personal tokens, one-off API keys, etc.) are ignored.
set -eu

CANONICAL_DIR="/boot/config/plugins/compose.manager/projects/bws-render"
CANONICAL_PATH="$CANONICAL_DIR/render.sh"

# Self-install guard: when invoked on the host (not from inside the container),
# refuse to run unless we live at the canonical path. Copy ourselves there if
# missing, then exit so the user re-invokes from the right place.
if [ ! -f /.dockerenv ]; then
  script_path=$(readlink -f "$0" 2>/dev/null || echo "$0")
  if [ "$script_path" != "$CANONICAL_PATH" ]; then
    if [ ! -f "$CANONICAL_PATH" ]; then
      mkdir -p "$CANONICAL_DIR"
      cp "$script_path" "$CANONICAL_PATH"
      chmod +x "$CANONICAL_PATH"
      echo "Installed render.sh to $CANONICAL_PATH"
    fi
    echo "Refusing to run from $script_path. Re-invoke from $CANONICAL_PATH." >&2
    exit 1
  fi
fi

# The stacks we render env files for. Add new ones here.
STACKS="authentik bookstack grafana homepage immich paperless semaphore technitium traefik wud"

export BWS_ACCESS_TOKEN="$(cat /run/secrets/access_token)"
OUT=/output

rm -f "$OUT"/*.env

# Build a newline-separated list for easy matching
allowed=$(printf '%s\n' $STACKS)

skipped=0
rendered=0

bws secret list --output json \
  | jq -r '.[] | "\(.key)\t\(.value)"' \
  | while IFS=$(printf '\t') read -r full_key value; do
      stack="${full_key%%__*}"
      env_var="${full_key#*__}"

      # Not in stack__VAR form, or prefix not in allowlist
      if [ "$stack" = "$full_key" ] || [ -z "$env_var" ] \
         || ! echo "$allowed" | grep -qx "$stack"; then
        skipped=$((skipped + 1))
        continue
      fi

      # Escape $ -> $$ so Compose doesn't treat $VAR_LIKE patterns in the value
      # as variable references during env_file interpolation. Compose unescapes
      # $$ back to $ when passing the value to the container.
      escaped=$(printf '%s' "$value" | sed 's/\$/\$\$/g')
      echo "$env_var=$escaped" >> "$OUT/$stack.env"

      rendered=$((rendered + 1))
    done

chmod 600 "$OUT"/*.env 2>/dev/null || true

echo "Rendered $(ls "$OUT"/*.env 2>/dev/null | wc -l) env files."
ls -l "$OUT"/*.env 2>/dev/null || echo "(no env files produced)"
