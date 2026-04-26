#!/usr/bin/env python3
"""Validate Home Assistant entity and device references.

The repository does not commit Home Assistant's .storage registries, so this
check uses repo-maintained baselines as the source of truth for external
entities/devices plus a small set of entities defined directly in YAML.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_DIR = ROOT / ".ci"
ENTITY_BASELINE = BASELINE_DIR / "known_entities.txt"
DEVICE_BASELINE = BASELINE_DIR / "known_devices.txt"

SKIP_DIRS = {
    ".git",
    ".idea",
    ".venv",
    "node_modules",
    "custom_components",
    "www",
    "themes",
}
YAML_SUFFIXES = {".yaml", ".yml"}

ENTITY_RE = re.compile(r"(?<![A-Za-z0-9_])([a-z][a-z0-9_]*\.[a-zA-Z0-9_]+)(?![A-Za-z0-9_])")
DEVICE_RE = re.compile(r"\bdevice_id:\s*['\"]?([a-fA-F0-9]{32})['\"]?")
TOP_LEVEL_KEY_RE = re.compile(r"^([a-zA-Z0-9_]+):\s*(?:#.*)?$")
NESTED_KEY_RE = re.compile(r"^\s{2}([a-zA-Z0-9_]+):\s*(?:#.*)?$")
NAME_RE = re.compile(r"^\s+name:\s*['\"]?([^'\"\n#]+?)['\"]?\s*(?:#.*)?$")

IGNORED_ENTITY_DOMAINS = {
    "entity",
    "entities",
    "repeat",
    "trigger",
    "variables",
}

HA_ENTITY_DOMAINS = {
    "alarm_control_panel",
    "automation",
    "binary_sensor",
    "button",
    "calendar",
    "camera",
    "climate",
    "cover",
    "device_tracker",
    "fan",
    "group",
    "humidifier",
    "image",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "lawn_mower",
    "light",
    "lock",
    "media_player",
    "notify",
    "number",
    "person",
    "remote",
    "scene",
    "script",
    "select",
    "sensor",
    "siren",
    "sun",
    "switch",
    "text",
    "timer",
    "todo",
    "update",
    "vacuum",
    "valve",
    "water_heater",
    "weather",
    "zone",
}

SERVICE_NAMES = {
    "browse_media",
    "call_service",
    "clear_playlist",
    "close_cover",
    "close_popup",
    "create_event",
    "dismiss",
    "install",
    "decrement",
    "increment",
    "join",
    "media_next_track",
    "media_pause",
    "media_play",
    "media_play_pause",
    "media_previous_track",
    "media_seek",
    "media_stop",
    "notify",
    "open_cover",
    "pause",
    "play_media",
    "press",
    "reload",
    "repeat_set",
    "restart",
    "return_to_base",
    "select_option",
    "select_source",
    "send_command",
    "set_cover_position",
    "set_fan_mode",
    "set_hvac_mode",
    "set_percentage",
    "set_preset_mode",
    "set_shuffle",
    "set_speed",
    "set_swing_mode",
    "set_temperature",
    "set_value",
    "shuffle_set",
    "start",
    "state",
    "stop",
    "stop_cover",
    "toggle",
    "turn_off",
    "turn_on",
    "update_entity",
    "volume_down",
    "volume_mute",
    "volume_set",
    "volume_up",
}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def iter_yaml_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in YAML_SUFFIXES:
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        files.append(path)
    return sorted(files)


def read_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    values: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            values.add(line)
    return values


def write_baseline(path: Path, header: str, values: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(sorted(values))
    path.write_text(f"{header}\n{body}\n", encoding="utf-8")


def strip_comment(line: str) -> str:
    # Good enough for CI reference scanning; quoted HA templates are still kept.
    return line.split("#", 1)[0]


def is_service_reference(entity_id: str, line: str) -> bool:
    domain, name = entity_id.split(".", 1)
    if name in SERVICE_NAMES:
        return True
    return domain == "browser_mod" and name in SERVICE_NAMES


def collect_references() -> tuple[dict[str, set[Path]], dict[str, set[Path]]]:
    entity_refs: dict[str, set[Path]] = {}
    device_refs: dict[str, set[Path]] = {}

    for path in iter_yaml_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for raw_line in text.splitlines():
            line = strip_comment(raw_line)
            for entity_id in ENTITY_RE.findall(line):
                entity_id = entity_id.lower()
                domain = entity_id.split(".", 1)[0]
                if (
                    domain not in HA_ENTITY_DOMAINS
                    or domain in IGNORED_ENTITY_DOMAINS
                    or is_service_reference(entity_id, line)
                ):
                    continue
                entity_refs.setdefault(entity_id, set()).add(path)
            for device_id in DEVICE_RE.findall(line):
                device_refs.setdefault(device_id.lower(), set()).add(path)

    return entity_refs, device_refs


def collect_yaml_defined_entities() -> set[str]:
    defined: set[str] = set()

    for path in sorted((ROOT / "src" / "helpers").glob("*.yaml")):
        domain = "input_number"
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = TOP_LEVEL_KEY_RE.match(line)
            if match:
                defined.add(f"{domain}.{match.group(1).lower()}")

    for path in sorted((ROOT / "src" / "utility_meters").glob("*.yaml")):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = TOP_LEVEL_KEY_RE.match(line)
            if match:
                defined.add(f"sensor.{match.group(1).lower()}")

    configuration = ROOT / "configuration.yaml"
    if configuration.exists():
        current_domain: str | None = None
        for line in configuration.read_text(encoding="utf-8", errors="ignore").splitlines():
            top = TOP_LEVEL_KEY_RE.match(line)
            if top:
                current_domain = top.group(1)
                continue
            nested = NESTED_KEY_RE.match(line)
            if nested and current_domain in {"input_boolean", "input_datetime", "input_select", "input_text"}:
                defined.add(f"{current_domain}.{nested.group(1).lower()}")

    for path in sorted((ROOT / "src" / "templates").glob("*.yaml")):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = NAME_RE.match(line)
            if match:
                slug = slugify(match.group(1))
                if slug:
                    defined.add(f"sensor.{slug}")

    for path in [ROOT / "src" / "scenes.yaml"]:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.lstrip().startswith("id:"):
                scene_id = line.split(":", 1)[1].strip().strip("'\"")
                if scene_id:
                    defined.add(f"scene.{slugify(scene_id)}")

    scripts = ROOT / "src" / "scripts.yaml"
    if scripts.exists():
        for line in scripts.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = TOP_LEVEL_KEY_RE.match(line)
            if match:
                defined.add(f"script.{match.group(1).lower()}")

    return defined


def format_locations(paths: set[Path]) -> str:
    return ", ".join(str(path.relative_to(ROOT)) for path in sorted(paths))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write current external entity/device references to .ci baselines.",
    )
    parser.add_argument(
        "--check-baseline",
        action="store_true",
        help="Fail if .ci baselines are not exactly reproducible from current YAML.",
    )
    args = parser.parse_args()

    entity_refs, device_refs = collect_references()
    defined_entities = collect_yaml_defined_entities()

    if args.update_baseline:
        external_entities = set(entity_refs) - defined_entities
        write_baseline(
            ENTITY_BASELINE,
            "# Known real Home Assistant entities referenced by this repo.",
            external_entities,
        )
        write_baseline(
            DEVICE_BASELINE,
            "# Known real Home Assistant device IDs referenced by this repo.",
            set(device_refs),
        )
        print(f"Wrote {ENTITY_BASELINE.relative_to(ROOT)} ({len(external_entities)} entities)")
        print(f"Wrote {DEVICE_BASELINE.relative_to(ROOT)} ({len(device_refs)} devices)")
        return 0

    if args.check_baseline:
        expected_entities = set(entity_refs) - defined_entities
        expected_devices = set(device_refs)
        current_entities = read_baseline(ENTITY_BASELINE)
        current_devices = read_baseline(DEVICE_BASELINE)

        failed = False
        if expected_entities != current_entities:
            failed = True
            missing = sorted(expected_entities - current_entities)
            stale = sorted(current_entities - expected_entities)
            print(f"{ENTITY_BASELINE.relative_to(ROOT)} is out of date.")
            if missing:
                print("  Missing entities:")
                for entity_id in missing:
                    print(f"    - {entity_id}")
            if stale:
                print("  Stale entities:")
                for entity_id in stale:
                    print(f"    - {entity_id}")

        if expected_devices != current_devices:
            failed = True
            missing = sorted(expected_devices - current_devices)
            stale = sorted(current_devices - expected_devices)
            print(f"{DEVICE_BASELINE.relative_to(ROOT)} is out of date.")
            if missing:
                print("  Missing device IDs:")
                for device_id in missing:
                    print(f"    - {device_id}")
            if stale:
                print("  Stale device IDs:")
                for device_id in stale:
                    print(f"    - {device_id}")

        if failed:
            print("\nRegenerate baselines with:")
            print("  python3 scripts/validate_ha_references.py --update-baseline")
            return 1

        print("HA reference baselines are reproducible.")
        return 0

    known_entities = read_baseline(ENTITY_BASELINE) | defined_entities
    known_devices = read_baseline(DEVICE_BASELINE)

    unknown_entities = sorted(set(entity_refs) - known_entities)
    unknown_devices = sorted(set(device_refs) - known_devices)

    if unknown_entities:
        print("Unknown entity references:")
        for entity_id in unknown_entities:
            print(f"  - {entity_id} ({format_locations(entity_refs[entity_id])})")

    if unknown_devices:
        print("Unknown device_id references:")
        for device_id in unknown_devices:
            print(f"  - {device_id} ({format_locations(device_refs[device_id])})")

    if unknown_entities or unknown_devices:
        print("\nIf these are real HA objects, run:")
        print("  python scripts/validate_ha_references.py --update-baseline")
        return 1

    print(f"Validated {len(entity_refs)} entity references and {len(device_refs)} device IDs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
