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
| **Prometheus** | 9090  | Metrics storage, scrapes botchini on remote VM   |
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
4. Edit `prometheus/prometheus.yml` — replace `BOTCHINI_HOST` with the target VM's internal IP
5. Deploy the stack

> **Important:** Use the **Repository** method, not "Upload" or "Web editor". The stack references config files via relative paths, so the entire repo must be cloned for them to be found.

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

### 3. Configure your applications

Set these environment variables in your apps:

```bash
# Traces — OTLP HTTP
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.yourdomain.com
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Logs — push to Alloy (Loki push API)
LOKI_PUSH_URL=https://logs.yourdomain.com/loki/api/v1/push

# Metrics — Prometheus remote write
PROMETHEUS_REMOTE_WRITE_URL=https://prometheus.yourdomain.com/api/v1/write
```

## Connecting botchini (on Coolify VM)

For botchini specifically, set these in Coolify:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.yourdomain.com
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

Prometheus can still scrape botchini over the LAN — edit `prometheus/prometheus.yml` and replace `BOTCHINI_HOST` with the Coolify VM's internal IP.

For logs, either:
- **Run Alloy on the Coolify VM** that pushes to `https://logs.yourdomain.com/loki/api/v1/push`
- **Push directly from the app** to the same Loki push URL

