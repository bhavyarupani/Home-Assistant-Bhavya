#!/usr/bin/env bash
set -euo pipefail

try_ha_cli_restart() {
  if command -v ha >/dev/null 2>&1 && ha core restart; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n ha core restart; then
    return 0
  fi

  return 1
}

try_docker_restart() {
  local docker_cmd="docker"
  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi

  if ! docker ps --format '{{.Names}}' >/tmp/ha-docker-containers.txt 2>/dev/null; then
    docker_cmd="sudo -n docker"
    if ! $docker_cmd ps --format '{{.Names}}' >/tmp/ha-docker-containers.txt 2>/dev/null; then
      return 1
    fi
  fi

  echo "Docker containers:" >&2
  sed 's/^/  /' /tmp/ha-docker-containers.txt >&2

  local container
  for container in homeassistant home-assistant hass io-homeassistant-core; do
    if grep -qx "$container" /tmp/ha-docker-containers.txt; then
      $docker_cmd restart "$container"
      return 0
    fi
  done

  container="$(grep -Ei 'homeassistant|home-assistant|^hass$' /tmp/ha-docker-containers.txt | head -n 1 || true)"
  if [ -n "$container" ]; then
    $docker_cmd restart "$container"
    return 0
  fi

  return 1
}

try_service_restart() {
  local service_name
  for service_name in home-assistant@homeassistant home-assistant homeassistant hass; do
    if command -v systemctl >/dev/null 2>&1 && sudo -n systemctl restart "$service_name" >/dev/null 2>&1; then
      return 0
    fi
    if command -v service >/dev/null 2>&1 && sudo -n service "$service_name" restart >/dev/null 2>&1; then
      return 0
    fi
  done

  return 1
}

echo "Restarting Home Assistant"
if try_ha_cli_restart; then
  echo "Home Assistant restart requested with HA CLI"
  exit 0
fi

echo "HA CLI restart failed; checking restart fallbacks." >&2
echo "Available commands:" >&2
for cmd in ha docker systemctl service hass sudo; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "  $cmd: yes" >&2
  else
    echo "  $cmd: no" >&2
  fi
done

if try_docker_restart; then
  echo "Home Assistant restarted with Docker"
  exit 0
fi

if try_service_restart; then
  echo "Home Assistant restarted with system service"
  exit 0
fi

echo "Home Assistant config was updated, but restart failed." >&2
echo "The HA CLI is unauthorized and no supported restart fallback worked." >&2
exit 1
