#!/usr/bin/env python3
"""
Embeds the Grafana dashboards and alert rules into docker-compose.yml.

Portainer doesn't mount files from the stack's repository, so every config
has to live inline in docker-compose.yml. Dashboards and alert rules are kept
as regular files (dashboards/<folder>/*.json, alerting/*.yaml) and this script
copies them into the generated section of the compose file.

Run it after changing any of those files:

    python3 scripts/embed_configs.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"
CONFIGS_BEGIN = "  # BEGIN GENERATED CONFIGS (scripts/embed_configs.py)"
CONFIGS_END = "  # END GENERATED CONFIGS"
MOUNTS_BEGIN = "      # BEGIN GENERATED MOUNTS (scripts/embed_configs.py)"
MOUNTS_END = "      # END GENERATED MOUNTS"


def escape(text):
    # docker compose interpolates $VAR in the file, $$ keeps a literal $
    return text.replace("$", "$$")


def config_name(path):
    return re.sub(r"[^a-z0-9]+", "_", path.stem.lower())


def dashboard_configs():
    """Yields (config name, mount target, content) for every dashboard"""
    for path in sorted(ROOT.glob("dashboards/*/*.json")):
        folder = path.parent.name
        dashboard = json.loads(path.read_text())
        tags = dashboard.get("tags") or []
        dashboard["tags"] = sorted(set(tags) | {folder})
        content = json.dumps(dashboard, separators=(",", ":"))
        target = f"/etc/grafana/dashboards/{folder}/{path.name}"
        yield f"grafana_dashboard_{config_name(path)}", target, content


def alerting_configs():
    """Yields (config name, mount target, content) for every alerting file"""
    for path in sorted(ROOT.glob("alerting/*.yaml")):
        target = f"/etc/grafana/provisioning/alerting/{path.name}"
        yield f"grafana_alerting_{config_name(path)}", target, path.read_text()


def render_configs(configs):
    lines = [CONFIGS_BEGIN]
    for name, _target, content in configs:
        lines.append(f"  {name}:")
        lines.append("    content: |")
        lines.extend(f"      {line}" if line else "" for line in escape(content).splitlines())
        lines.append("")
    lines.append(CONFIGS_END)
    return "\n".join(lines)


def render_mounts(configs):
    lines = [MOUNTS_BEGIN]
    for name, target, _content in configs:
        lines.append(f"      - source: {name}")
        lines.append(f"        target: {target}")
    lines.append(MOUNTS_END)
    return "\n".join(lines)


def replace_section(text, begin, end, rendered):
    pattern = re.compile(re.escape(begin) + ".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Couldn't find the '{begin.strip()}' marker in {COMPOSE.name}")
    return pattern.sub(lambda _match: rendered, text)


configs = [*dashboard_configs(), *alerting_configs()]
compose = COMPOSE.read_text()
compose = replace_section(compose, CONFIGS_BEGIN, CONFIGS_END, render_configs(configs))
compose = replace_section(compose, MOUNTS_BEGIN, MOUNTS_END, render_mounts(configs))
COMPOSE.write_text(compose)
print(f"Embedded {len(configs)} configs into {COMPOSE.name}")
