# Alloy agent — Pelican game-server host (`pelican-wings`)

The agent that ships the Pelican game servers' logs and metrics into this
stack. It **runs on the Pelican host**, not here: it needs that host's Docker
socket (`discovery.docker` + `loki.source.docker`), the host cgroups/`/proc`
(the embedded cAdvisor exporter) and `/var/log/pelican` (the daemon log file
source). Nothing here can be moved into the stack's own `docker-compose.yml`
without losing all of that — what lives in this repo is only its *config*, so
the agent, the dashboards and the alert rules have one source of truth.

```
agents/pelican-wings/
  config.alloy        Alloy pipeline: Docker logs, cAdvisor, daemon log, game-version/backup gauges
  docker-compose.yml  The agent's own compose file (this directory only)
  .env.example        Copy to .env — host label, docker GID, Cloudflare Access token
```

## Deploy / update on the Pelican host

```bash
git clone https://github.com/lucapasquale/grafana-stack.git /opt/grafana-stack
cd /opt/grafana-stack/agents/pelican-wings
cp .env.example .env      # fill in ALLOY_HOSTNAME, DOCKER_GID, CF_ACCESS_*
docker compose up -d
```

Updating after a config change lands on `main`:

```bash
git -C /opt/grafana-stack pull
cd /opt/grafana-stack/agents/pelican-wings
docker compose up -d --force-recreate alloy
```

Alloy reads `config.alloy` **once at startup**, so an edited file does nothing
until the container is recreated. (Symptom of forgetting: the running config
disagrees with the file — e.g. metrics land with an old scrape `job` name.)

`.env` is never committed: the root `.gitignore` pattern `.env` matches files
with that name at any depth.

## What it feeds into the stack

| Sink | Endpoint | Content |
| ---- | -------- | ------- |
| Loki | `https://logs.luca.codes/loki/api/v1/push` | game-server stdout/stderr as `{service="pelican"}`, plus the Pelican daemon log as `{job="pelican_daemon"}` |
| Prometheus (remote write) | `https://prometheus.luca.codes/api/v1/write` | cAdvisor container metrics, Alloy's own `/metrics` (`loki_process_custom_pelican_*` gauges/counters), all relabelled with `game`, `service="pelican"`, `host` |

The dashboards that read this data live in `dashboards/pelican/` and are
provisioned by Grafana Git Sync — see the repository README.

## The UUID → game map (read this before adding a server)

Pelican names each game container after its server UUID, so every label that
a human reads comes from a mapping hardcoded **three times** in `config.alloy`:

1. `discovery.relabel.pelican_only` — keyed on `pelican_uuid`, drives **log**
   stream labels (`game`).
2. `prometheus.relabel.add_game_label` — keyed on `name`, for **cAdvisor**
   container metrics.
3. `prometheus.relabel.add_game_label` — keyed on `server_uuid`, for the
   **backup** gauge coming out of the daemon log.

Adding or replacing a server means updating all three lists (search for the
UUID you are replacing). A container whose UUID is missing from a list keeps
working, but its logs/metrics arrive without a `game` label, so it disappears
from every per-game panel.

Current mappings:

| UUID | `game` |
| ---- | ------ |
| `9d771143-8389-4699-a596-9bb11b2819aa` | `minecraft_fabric` |
| `1f1e04be-f4a7-4b4d-8e0e-e24b3ca7982b` | `romestead` |
| `8deac147-eb74-4aa7-8288-7b4ddfe1abb6` | `palworld` |
| `21e58aa7-dcf1-4fb7-be96-613355a6ca49` | `valheim` |
| `da2a1da9-2cb3-4bf7-ae8f-0a86bd62d22d` | `project_zomboid` |
| `398cbf9d-578e-4bac-9219-708f6cd9efa6` | `enshrouded` |

Game-version parsing is per game (`stage.match` blocks in
`loki.process.game_server_logs`): each one matches that game's own startup
line and emits `pelican_game_version_info{gameversion="…"}`. A game without a
matching block simply has no version panel until one is added.

## Notes / known rough edges

- `/var/log/pelican` is version dependent; if it is empty, switch
  `local.file_match` to the journal source and swap the mount in
  `docker-compose.yml` for `- /var/log/journal:/var/log/journal:ro`.
- `pelican_player_joins_total` fires on connection *attempt* (before auth) and
  there is no matching "leave" line yet, so "players online" cannot be derived
  from it — see the TODO in `config.alloy`.
- The game-version and backup gauges use `max_idle_duration = "168h"` so they
  survive between restarts and backups; without it the panels go to "No data".
