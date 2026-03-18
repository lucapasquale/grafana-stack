# Grafana Observability Stack

Self-hosted observability stack for Portainer deployment. Receives **logs**, **metrics**, and **traces** from services like [botchini](../botchini).

## Services

| Service        | Port  | Purpose                                    |
| -------------- | ----- | ------------------------------------------ |
| **Grafana**    | 3000  | Dashboards & visualization                 |
| **Prometheus** | 9090  | Metrics storage & scraping                 |
| **Loki**       | 3100  | Log aggregation                            |
| **Tempo**      | 4317  | Distributed traces (OTLP gRPC)             |
| **Tempo**      | 4318  | Distributed traces (OTLP HTTP)             |
| **Alloy**      | 12345 | Log collector (Docker container logs → Loki)|

## Deploy to Portainer

1. In Portainer go to **Stacks → Add stack**
2. Upload or paste the `docker-compose.yml`
3. Set the `GRAFANA_ADMIN_PASSWORD` environment variable
4. Deploy the stack

## Connecting services

### Traces (OpenTelemetry → Tempo)

Set the OTLP endpoint in your service to `http://<stack-host>:4317` (gRPC) or `http://<stack-host>:4318` (HTTP).

### Metrics (Prometheus scraping)

Edit `prometheus/prometheus.yml` and add your service's target under `scrape_configs`:

```yaml
- job_name: "my-service"
  static_configs:
    - targets: ["my-service-host:metrics-port"]
```

### Logs (Container stdout → Alloy → Loki)

Alloy auto-discovers Docker containers on the host and ships their stdout/stderr to Loki. For JSON-structured logs (recommended), Alloy parses severity levels automatically.

## Networking

If your services run in a separate Docker Compose stack, create an external network so they can reach Tempo/Prometheus:

```yaml
# In your service's docker-compose.yml
networks:
  observability:
    external: true
    name: grafana-stack_observability
```
