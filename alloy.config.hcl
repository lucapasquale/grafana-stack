server "otel" {
  http {
    listen_address = "0.0.0.0:4318"
  }
}

otelcol.receiver.otlp "default" {
  protocols = {
    http = {}
  }
}

otelcol.processor.batch "default" {}

otelcol.exporter.loki "default" {
  endpoint = "http://loki:3100/loki/api/v1/push"
  tls {
    insecure = true
  }
}

otelcol.exporter.otlp "tempo" {
  endpoint = "http://tempo:4318"
  tls {
    insecure = true
  }
}

otelcol.exporter.prometheusremotewrite "default" {
  endpoint = "http://prometheus:9090/api/v1/write"
}

otelcol.connector.pipeline "default" {
  receivers  = [otelcol.receiver.otlp.default]
  processors = [otelcol.processor.batch.default]
  exporters  = [
    otelcol.exporter.loki.default,
    otelcol.exporter.otlp.tempo,
    otelcol.exporter.prometheusremotewrite.default
  ]
}
