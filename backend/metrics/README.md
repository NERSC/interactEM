# InteractEM - Metrics

A Prometheus-based metrics collection system for monitoring InteractEM pipeline performance, operator efficiency, and system status with real-time visualization in Grafana.

## Architecture
- **InteractEM** (with Metrics Server on port 8001) exposes metrics
- **Prometheus** (port 9090) scrapes metrics every 5 seconds
- **Grafana** (port 3000) queries Prometheus and displays dashboards

## Local Development Environment

| Service | URL | Description |
|---------|-----|-------------|
| **Metrics Server** | `http://localhost:8001` | Prometheus metrics endpoint |
| **Prometheus** | `http://localhost:9090` | Time-series database and monitoring |
| **Grafana** | `http://localhost:3000` | Visualization and dashboards |

**Access the Dashboard:**
1. Navigate to Grafana at `http://localhost:3000`
2. Go to **Dashboards** → **InteractEM** → **Interactem Pipeline Monitoring**