#!/usr/bin/env node

import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const HA_URL = normalizeUrl(process.env.HA_URL || process.env.HASS_URL);
const HA_TOKEN = process.env.HA_TOKEN || process.env.HASS_TOKEN;
const OUT = resolve(process.argv[2] || "artifacts/ha-live-snapshot.json");

if (!HA_URL || !HA_TOKEN) {
  console.error(
    [
      "Missing Home Assistant connection details.",
      "",
      "Set these environment variables and run again:",
      "  HA_URL=http://homeassistant.local:8123",
      "  HA_TOKEN=<long-lived-access-token>",
      "",
      "Example:",
      "  HA_URL=http://192.168.1.186:8123 HA_TOKEN=... npm run ha:live",
    ].join("\n"),
  );
  process.exit(2);
}

const startedAt = new Date().toISOString();

try {
  const [api, config, states, services, ws] = await Promise.all([
    restGet("/api/"),
    restGet("/api/config"),
    restGet("/api/states"),
    restGet("/api/services"),
    websocketSnapshot(),
  ]);

  const snapshot = {
    generated_at: startedAt,
    home_assistant: {
      url: HA_URL,
      api,
      config,
    },
    counts: countThings({ states, services, ws }),
    summaries: buildSummaries({ states, ws }),
    live_states: states,
    services,
    registries: ws,
  };

  await mkdir(dirname(OUT), { recursive: true });
  await writeFile(OUT, `${JSON.stringify(snapshot, null, 2)}\n`);

  printSummary(snapshot);
  console.log(`\nWrote ${OUT}`);
} catch (error) {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
}

function normalizeUrl(value) {
  if (!value) return "";
  return value.replace(/\/+$/, "");
}

async function restGet(path) {
  const response = await fetch(`${HA_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${HA_TOKEN}`,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`GET ${path} failed: ${response.status} ${response.statusText}\n${body}`);
  }

  return response.json();
}

async function websocketSnapshot() {
  const wsUrl = `${HA_URL.replace(/^http/i, "ws")}/api/websocket`;
  const ws = new WebSocket(wsUrl);
  let nextId = 1;

  await new Promise((resolveOpen, rejectOpen) => {
    const timer = setTimeout(() => rejectOpen(new Error(`Timed out connecting to ${wsUrl}`)), 15000);
    ws.addEventListener(
      "open",
      () => {
        clearTimeout(timer);
        resolveOpen();
      },
      { once: true },
    );
    ws.addEventListener(
      "error",
      () => {
        clearTimeout(timer);
        rejectOpen(new Error(`Could not connect to ${wsUrl}`));
      },
      { once: true },
    );
  });

  const first = await receive(ws);
  if (first.type !== "auth_required") {
    throw new Error(`Unexpected WebSocket greeting: ${JSON.stringify(first)}`);
  }

  ws.send(JSON.stringify({ type: "auth", access_token: HA_TOKEN }));
  const auth = await receive(ws);
  if (auth.type !== "auth_ok") {
    throw new Error(`Home Assistant WebSocket auth failed: ${JSON.stringify(auth)}`);
  }

  const commands = {
    entity_registry_display: "config/entity_registry/list_for_display",
    device_registry: "config/device_registry/list",
    area_registry: "config/area_registry/list",
    floor_registry: "config/floor_registry/list",
    label_registry: "config/label_registry/list",
    exposed_entities: "homeassistant/expose_entity/list",
  };

  const result = {};
  for (const [key, type] of Object.entries(commands)) {
    result[key] = await command(ws, nextId++, type);
  }

  ws.close();
  return result;
}

async function command(ws, id, type) {
  ws.send(JSON.stringify({ id, type }));
  while (true) {
    const message = await receive(ws);
    if (message.id !== id) continue;
    if (!message.success) {
      return { error: message.error || message };
    }
    return message.result;
  }
}

function receive(ws) {
  return new Promise((resolveMessage, rejectMessage) => {
    const timer = setTimeout(() => rejectMessage(new Error("Timed out waiting for WebSocket message")), 15000);
    ws.addEventListener(
      "message",
      (event) => {
        clearTimeout(timer);
        try {
          resolveMessage(JSON.parse(event.data));
        } catch (error) {
          rejectMessage(error);
        }
      },
      { once: true },
    );
    ws.addEventListener(
      "error",
      () => {
        clearTimeout(timer);
        rejectMessage(new Error("Home Assistant WebSocket error"));
      },
      { once: true },
    );
  });
}

function countThings({ states, services, ws }) {
  const domains = {};
  for (const state of states) {
    const domain = state.entity_id.split(".")[0];
    domains[domain] = (domains[domain] || 0) + 1;
  }

  return {
    states: states.length,
    devices: Array.isArray(ws.device_registry) ? ws.device_registry.length : 0,
    entity_registry: Array.isArray(ws.entity_registry_display?.entities)
      ? ws.entity_registry_display.entities.length
      : 0,
    areas: Array.isArray(ws.area_registry) ? ws.area_registry.length : 0,
    services: services.reduce((total, domain) => total + Object.keys(domain.services || {}).length, 0),
    domains,
  };
}

function buildSummaries({ states, ws }) {
  const byEntityId = new Map(states.map((state) => [state.entity_id, state]));
  const entities = ws.entity_registry_display?.entities || [];

  const interestingSensors = states
    .filter((state) => {
      const attrs = state.attributes || {};
      const unit = String(attrs.unit_of_measurement || "").toLowerCase();
      const deviceClass = String(attrs.device_class || "").toLowerCase();
      return (
        deviceClass.includes("power") ||
        deviceClass.includes("energy") ||
        unit === "w" ||
        unit === "kw" ||
        unit === "kwh" ||
        state.entity_id.includes("energy") ||
        state.entity_id.includes("electric")
      );
    })
    .map((state) => compactState(state))
    .sort((a, b) => a.entity_id.localeCompare(b.entity_id));

  const exposed = ws.exposed_entities?.exposed_entities || {};
  const exposedEntities = Object.entries(exposed)
    .filter(([, exposure]) => Object.values(exposure || {}).some(Boolean))
    .map(([entity_id, exposure]) => ({ entity_id, exposure, live: compactState(byEntityId.get(entity_id)) }))
    .sort((a, b) => a.entity_id.localeCompare(b.entity_id));

  const registryPowerCandidates = entities
    .filter((entity) => {
      const entityId = entity.ei || "";
      const live = byEntityId.get(entityId);
      const attrs = live?.attributes || {};
      return (
        entityId.includes("energy") ||
        entityId.includes("electric") ||
        attrs.device_class === "power" ||
        attrs.device_class === "energy" ||
        ["W", "kW", "kWh"].includes(attrs.unit_of_measurement)
      );
    })
    .map((entity) => ({
      entity_id: entity.ei,
      platform: entity.pl,
      area_id: entity.ai,
      device_id: entity.di,
      name: entity.en,
      live: compactState(byEntityId.get(entity.ei)),
    }))
    .sort((a, b) => a.entity_id.localeCompare(b.entity_id));

  return {
    energy_and_power_states: interestingSensors,
    exposed_entities: exposedEntities,
    registry_power_candidates: registryPowerCandidates,
  };
}

function compactState(state) {
  if (!state) return null;
  return {
    entity_id: state.entity_id,
    state: state.state,
    unit: state.attributes?.unit_of_measurement,
    device_class: state.attributes?.device_class,
    friendly_name: state.attributes?.friendly_name,
    last_changed: state.last_changed,
    last_updated: state.last_updated,
  };
}

function printSummary(snapshot) {
  const { counts, summaries, home_assistant: ha } = snapshot;
  console.log(`Connected to Home Assistant ${ha.config.version || ""} at ${ha.url}`);
  console.log(`States: ${counts.states}`);
  console.log(`Entity registry entries: ${counts.entity_registry}`);
  console.log(`Device registry entries: ${counts.devices}`);
  console.log(`Areas: ${counts.areas}`);
  console.log(`Power/energy candidates: ${summaries.registry_power_candidates.length}`);
  console.log(`Exposed entities: ${summaries.exposed_entities.length}`);

  const activePower = summaries.energy_and_power_states
    .filter((state) => Number.parseFloat(state.state) > 0)
    .slice(0, 12);

  if (activePower.length > 0) {
    console.log("\nActive power/energy states:");
    for (const state of activePower) {
      console.log(`- ${state.entity_id}: ${state.state}${state.unit ? ` ${state.unit}` : ""}`);
    }
  }
}
