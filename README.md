# Grafana Observability Stack

Self-hosted observability stack for Portainer deployment. Receives **logs**, **metrics**, and **traces** from services running on other VMs (e.g. botchini on Coolify).

## Architecture

```
┌─────────────────────────┐         ┌──────────────────────────────────┐
│   Coolify VM            │         │   Portainer VM (this stack)      │
│                         │         │                                  │
│  botchini               │         │  ┌───────────┐  ┌────────────┐  │
│   ├─ traces (OTLP gRPC)─┼────────►│  │   Tempo   │  │  Grafana   │  │
│   ├─ metrics (/metrics) │◄────────┼──│Prometheus  │  │  :3000     │  │
│   └─ logs (JSON stdout) │         │  └───────────┘  └────────────┘  │
│                         │         │                                  │
│  Alloy (log forwarder)  │         │  ┌───────────┐  ┌────────────┐  │
│   └─ push to Loki ──────┼────────►│  │   Loki    │  │   Alloy    │  │
│                         │         │  └───────────┘  └────────────┘  │
└─────────────────────────┘         └──────────────────────────────────┘

Communication uses internal/LAN IPs between VMs.
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
2. Upload or paste the `docker-compose.yml`
3. Set the `GRAFANA_ADMIN_PASSWORD` environment variable
4. Edit `prometheus/prometheus.yml` — replace `BOTCHINI_HOST` with the Coolify VM's internal IP
5. Deploy the stack

## Connecting botchini (on Coolify VM)

### Environment variables to set in Coolify

```bash
# Internal IP of the Portainer VM running this grafana stack
OTEL_EXPORTER_OTLP_ENDPOINT=http://192.168.x.x:4317

# Expose the PromEx metrics port so Prometheus can scrape it
# (Coolify: set exposed ports to include 4021)
```

### Traces (botchini → Tempo)

Already configured. Botchini sends OTLP gRPC traces to `$OTEL_EXPORTER_OTLP_ENDPOINT`.

### Metrics (Prometheus → botchini)

Prometheus scrapes `BOTCHINI_HOST:4021/metrics`. Make sure port 4021 is published on the Coolify VM.
Edit `prometheus/prometheus.yml` and replace `BOTCHINI_HOST` with the Coolify VM's LAN IP.

### Logs (botchini → Loki)

Since botchini is on a different VM, Alloy can't read its Docker socket. Two options:

**Option A: Run Alloy on the Coolify VM (recommended)**

Deploy a small Alloy container on the Coolify VM that collects local Docker logs and pushes them to Loki:

```yaml
# docker-compose.alloy.yml - deploy on Coolify VM
services:
  alloy:
    image: grafana/alloy:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./alloy-forwarder.alloy:/etc/alloy/config.alloy:ro
    command: run /etc/alloy/config.alloy
    restart: unless-stopped
```

```hcl
# alloy-forwarder.alloy
discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
}

discovery.relabel "containers" {
  targets = discovery.docker.containers.targets

  rule {
    source_labels = ["__meta_docker_container_name"]
    target_label  = "container"
  }
  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_service"]
    target_label  = "service"
  }
}

loki.source.docker "containers" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.relabel.containers.output
  forward_to = [loki.process.containers.receiver]
}

loki.process "containers" {
  forward_to = [loki.write.loki.receiver]

  stage.json {
    expressions = {
      level   = "severity",
      message = "message",
    }
  }
  stage.labels {
    values = { level = "" }
  }
}

loki.write "loki" {
  endpoint {
    // Replace with the internal IP of the Portainer VM
    url = "http://192.168.x.x:3100/loki/api/v1/push"
  }
}
```

**Option B: Push to Alloy's push endpoint**

If you can't run Alloy on Coolify, configure a log shipper that POSTs to `http://PORTAINER_VM_IP:9095/loki/api/v1/push`.

## Exposing Grafana externally (Cloudflare Tunnel)

Use a Cloudflare Tunnel to expose only the Grafana UI:

```bash
cloudflared tunnel --url http://localhost:3000 --name grafana
```

Or add it to your existing `cloudflared` config on the Portainer VM:

```yaml
# ~/.cloudflared/config.yml
ingress:
  - hostname: grafana.yourdomain.com
    service: http://localhost:3000
```

Do **not** expose Tempo, Loki, or Prometheus ports through Cloudflare — those should only be accessible via internal IPs.

