# Grafana Observability Stack

Self-hosted observability stack for Portainer deployment on Proxmox. Receives **logs**, **metrics**, and **traces** from external applications via **Cloudflare Tunnel**.

## Architecture

```
┌──────────────────────────┐         ┌──────────────────────────────────────────┐
│   External Applications  │         │   Proxmox / Portainer (this stack)       │
│                          │         │                                          │
│  your-app                │         │  ┌────────────┐                          │
│   ├─ traces (OTLP HTTP)──┼─────┐   │  │   Tempo    │  ┌────────────┐         │
│   ├─ metrics (push)      │     │   │  │  :4317/18  │  │  Grafana   │         │
│   └─ logs (Loki push)    │     │   │  └────────────┘  │  :3000     │         │
│                          │     │   │                   └────────────┘         │
└──────────────────────────┘     │   │  ┌────────────┐  ┌────────────┐         │
                                 │   │  │   Loki     │  │   Alloy    │         │
        Cloudflare Tunnel        │   │  │  :3100     │  │  :9095     │         │
       ┌─────────────────┐       │   │  └────────────┘  └────────────┘         │
       │   cloudflared    │◄─────┘   │                                          │
       │  (routes traffic │          │  ┌────────────┐                          │
       │   to services)   │──────────│  │ Prometheus  │                         │
       └─────────────────┘          │  │  :9090      │                         │
                                     │  └────────────┘                          │
                                     └──────────────────────────────────────────┘
```

## Services

| Service        | Port  | Purpose                                         |
| -------------- | ----- | ------------------------------------------------ |
| **Grafana**    | 3000  | Dashboards & visualization                       |
| **Prometheus** | 9090  | Metrics storage & remote write receiver          |
| **Loki**       | 3100  | Log aggregation                                  |
| **Tempo**      | 4317  | Distributed traces (OTLP gRPC)                   |
| **Tempo**      | 4318  | Distributed traces (OTLP HTTP)                   |
| **Alloy**      | 12345 | Local Docker log collection                      |
| **Alloy**      | 9095  | Remote log push endpoint (Loki push API)         |

## Deploy to Portainer

1. In Portainer go to **Stacks → Add stack**
2. Select **Repository**, enter the Git repo URL, and set the branch
3. Set environment variables (see `.env.example`):
   - `GRAFANA_ADMIN_PASSWORD` — Grafana admin password
4. Deploy the stack

> **Important:** Use the **Repository** method, not "Upload" or "Web editor". The stack references config files via relative paths, so the entire repo must be cloned for them to be found.

## Dashboards and Alerts

Grafana is provisioned with dashboards and alert rules from this repo:

| Path                   | What it is                                                                   |
| ---------------------- | ---------------------------------------------------------------------------- |
| `dashboards/<folder>/` | Dashboard JSON files, provisioned into a Grafana folder of the same name     |
| `alerting/`            | Alert rules, contact points and notification policies                        |

Portainer doesn't mount files from the repository, so these files are embedded
inline into `docker-compose.yml`. **After changing any of them, run:**

```bash
python3 scripts/embed_configs.py
```

and commit both the file and the updated `docker-compose.yml`. The script
escapes `$` for docker compose and adds each dashboard's folder name as a tag.

To edit a dashboard, change it in Grafana (provisioned dashboards allow UI
edits, but they are reset on restart), export it as JSON into `dashboards/`
and run the script.

### Botchini

- **Botchini - Overview**: Discord commands (volume, failures, p95 response
  time), music playback (tracks started, failures by reason), screen sharing
  (streams started, viewers joining and a stream event log, with stream starts
  marked on every graph), Twitch/YouTube API health, and recent error logs
  from Loki
- **Botchini - PromEx \***: BEAM, application, Ecto and Phoenix dashboards
  exported from Botchini with `mix prom_ex.dashboard.export`

Alerts are sent to the Discord webhook in `DISCORD_ALERT_WEBHOOK_URL`:

| Alert                           | Fires when                                                                 |
| ------------------------------- | -------------------------------------------------------------------------- |
| Botchini commands failing       | More than 2 interactions failed in the last 15 minutes                     |
| Botchini music playback failing | More than 2 tracks failed in 30 minutes, ignoring user errors (age restricted, unavailable, unsupported links, offline streams) |
| Botchini external API errors    | More than 20% of a service's API requests failed over 10 minutes, for 5 minutes |
| Botchini is down                | Alloy can't scrape Botchini's metrics for 3 minutes                        |

> **Note:** Grafana refuses to start when the Discord contact point has no URL,
> so `DISCORD_ALERT_WEBHOOK_URL` falls back to a placeholder when unset. Alerts
> just fail to deliver until the real webhook is configured.

## Cloudflare Tunnel Setup

cloudflared runs on the host and routes traffic to the stack's published ports on `localhost`.

In your tunnel's **Public Hostname** tab, add routes for each service your apps need:

| Public hostname              | Service                      | Purpose                         |
| ---------------------------- | ---------------------------- | ------------------------------- |
| `grafana.yourdomain.com`     | `http://localhost:3000`      | Grafana dashboards              |
| `otlp.yourdomain.com`        | `http://localhost:4318`      | OTLP HTTP traces                |
| `logs.yourdomain.com`        | `http://localhost:9095`      | Loki push API (log ingestion)   |
| `prometheus.yourdomain.com`  | `http://localhost:9090`      | Prometheus remote write         |

> **Note:** For OTLP gRPC (port 4317), use the HTTP endpoint (4318) instead — Cloudflare Tunnel works best with HTTP traffic.

## Securing Ingestion Endpoints with Cloudflare Access

The ingestion endpoints (traces, logs, metrics) must be protected so only your applications can push data. Use **Cloudflare Access Service Tokens** to authenticate machine-to-machine traffic.

### 1. Create a Service Token

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Access → Service Auth → Service Tokens**
2. Click **Create Service Token**
3. Name it (e.g. `grafana-stack-ingest`)
4. Save the **Client ID** and **Client Secret** — the secret is only shown once

### 2. Create an Access Application

1. Go to **Access → Applications → Add an application → Self-hosted**
2. Add the ingestion hostnames as application domains:
   - `otlp.yourdomain.com`
   - `logs.yourdomain.com`
   - `prometheus.yourdomain.com`
3. Create a policy with:
   - **Action:** Service Auth
   - **Include:** Service Token — select the token you created
4. Save the application

> **Note:** Do **not** add `grafana.yourdomain.com` to this Access application — Grafana has its own login and should remain accessible via browser.

### 3. Configure your applications

Your apps need to send the service token headers alongside their telemetry. Set these environment variables:

```bash
# Cloudflare Access service token
CF_ACCESS_CLIENT_ID=<your-client-id>.access
CF_ACCESS_CLIENT_SECRET=<your-client-secret>

# Traces — OTLP HTTP
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.yourdomain.com
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_HEADERS="CF-Access-Client-Id=${CF_ACCESS_CLIENT_ID},CF-Access-Client-Secret=${CF_ACCESS_CLIENT_SECRET}"

# Logs — push to Alloy (Loki push API)
LOKI_PUSH_URL=https://logs.yourdomain.com/loki/api/v1/push
# Include CF-Access-Client-Id and CF-Access-Client-Secret headers in your HTTP client

# Metrics — Prometheus remote write
PROMETHEUS_REMOTE_WRITE_URL=https://prometheus.yourdomain.com/api/v1/write
# Include CF-Access-Client-Id and CF-Access-Client-Secret headers in your HTTP client
```

The `OTEL_EXPORTER_OTLP_HEADERS` env var is part of the OpenTelemetry spec — most OTLP SDKs and collectors support it natively. For log and metric push clients, add the two headers to your HTTP requests manually.

