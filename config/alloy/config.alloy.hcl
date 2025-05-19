locals {
  loki_host   = "http://localhost:3100"
  tempo_host  = "http://localhost:4318"
  mimir_host  = "http://localhost:9009"
}

otelcol.receiver.otlp "default" {
  protocols {
    grpc {}
    http {}
  }
}

otelcol.exporter.otlp "traces" {
  endpoint = "${local.tempo_host}"
  tls {
    insecure = true
  }
}

otelcol.processor.batch "default" {}

otelcol.service "default" {
  pipelines {
    traces = {
      receivers  = [otelcol.receiver.otlp.default]
      processors = [otelcol.processor.batch.default]
      exporters  = [otelcol.exporter.otlp.traces]
    }
  }
}

prometheus.scrape "local_apps" {
  targets = ["localhost:9100"] # Example target: your app's metrics endpoint
}

loki.source.files "varlogs" {
  paths = ["/var/log/**/*.log"]
}

loki.source.journald "systemd" {}

loki.exporter "default" {
  endpoint = "${local.loki_host}/loki/api/v1/push"
}

loki.relabel "default" {
  rules {
    action = "replace"
    source_labels = ["__path__"]
    target_label  = "job"
    replacement   = "varlogs"
  }
}

loki.pipeline "logs" {
  sources  = [loki.source.files.varlogs, loki.source.journald.systemd]
  relabels = [loki.relabel.default]
  exporter = loki.exporter.default
}

prometheus.remote_write "mimir" {
  endpoint = "${local.mimir_host}/api/v1/push"
  basic_auth {
    username = env("MIMIR_USER")
    password = env("MIMIR_PASSWORD")
  }
}

prometheus.scrape "self" {
  targets = ["localhost:12345"] # Alloy metrics (optional if enabled)
}

prometheus.write "remote" {
  receivers = [prometheus.scrape.local_apps, prometheus.scrape.self]
  remote_write {
    client = prometheus.remote_write.mimir
  }
}
