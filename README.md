# Spark Observability Lab

This project provides a small Spark standalone cluster (master + worker) with a complete **observability stack** based on:

- Prometheus (metrics collection and alerting)
- Grafana (dashboards)
- Node Exporter (host metrics)
- JMX Prometheus Exporter (Spark JVM + driver/executor metrics)

The detailed lab guide is in `docs/spark-observability-lab.md`. This README gives a **quick start** for users and students.

---

## 1. Prerequisites

- Docker and Docker Compose installed on the machine where containers run (local or remote VM).
- At least 4 vCPUs, 8 GB RAM recommended.
- Network access to the VM from your browser if you run remotely.

Clone (or copy) this repository to the target machine, e.g. on a VM:

```bash
cd ~
git clone <your-repo-url> Spark-Obsevability
cd Spark-Obsevability
```

> The rest of the commands in this README assume you are in the project root (`Spark-Obsevability`).

---

## 2. Project Layout

Key files and directories:

- `docker-compose.yml` – defines Spark, Prometheus, Grafana, Alertmanager, Node Exporter.
- `config/` – Prometheus config, alert rules, alertmanager, JMX exporter configs.
- `jobs/etl_job.py` – sample PySpark ETL job used to generate metrics.
- `grafana/` – provisioning and dashboards (including Node Exporter system metrics).
- `docs/spark-observability-lab.md` – full lab instructions and explanations.
- `plan.md` – implementation and teaching plan for the lab.

---

## 3. One-Time Setup

### 3.1 Download JMX Prometheus Exporter JAR

From the project root, on the machine that runs Docker:

```bash
mkdir -p jars
curl -L -o jars/jmx_prometheus_javaagent.jar \
  https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/1.0.0/jmx_prometheus_javaagent-1.0.0.jar
```

> This JAR is mounted into Spark containers to expose JVM and Spark metrics.

---

## 4. Start the Observability Stack

From the project root:

```bash
docker compose up -d

# Check container status
docker compose ps
```

You should see at least:

- `prometheus` – Up (healthy)
- `grafana` – Up (healthy)
- `alertmanager` – Up
- `node-exporter` – Up
- `spark-master` – Up
- `spark-worker` – Up

If `spark-master` or `spark-worker` are restarting, inspect logs:

```bash
docker logs spark-master --tail 50
docker logs spark-worker --tail 50
```

Refer to `docs/spark-observability-lab.md` → Troubleshooting for fixes.

---

## 5. Web Interfaces

Assuming Docker is bound to `0.0.0.0` (replace `<host>` with `localhost` or your VM IP):

- Spark Master UI: `http://<host>:8080`
- Spark Worker UI: `http://<host>:8081`
- Spark Driver UI (per job): `http://<host>:4040`
- Prometheus: `http://<host>:9090`
- Grafana: `http://<host>:3000` (default `admin` / `admin`)
- Alertmanager: `http://<host>:9093`

If running on a remote VM with firewalled ports, either open the ports or use SSH port forwarding from your laptop.

---

## 6. Run the Sample ETL Job

Submit the provided PySpark ETL job **from inside the Spark master container**:

```bash
docker exec spark-master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --executor-memory 1g \
  --executor-cores 2 \
  /jobs/etl_job.py
```

The job:

- Generates synthetic data.
- Applies filters and aggregations.
- Writes results to `/data/etl_output` (mounted to `./data` on the host).
- Keeps the Spark application alive briefly so Prometheus can scrape metrics.

While it runs, open:

- Spark UI: `http://<host>:4040`
- Prometheus: explore metrics like `up{job="spark-driver"}`.
- Grafana: Spark and system dashboards (see next section).

---

## 7. Grafana Dashboards

Grafana is configured via provisioning files in `grafana/provisioning/` and loads dashboards from `grafana/dashboards/`.

Currently included dashboards:

- **Node Exporter - System Metrics** (`system-metrics.json`)
  - CPU usage per instance (using `node_cpu_seconds_total`).
  - Memory usage percentage and GB used/total.
  - Disk usage and read/write throughput.
  - Network traffic per interface.

Additional Spark-specific dashboards can be added as JSON files in `grafana/dashboards/`.

To force Grafana to reload provisioning after changes:

```bash
docker compose restart grafana
```

---

## 8. Prometheus Alerts

Prometheus is configured with example alert rules in `config/alert-rules.yml`, including:

- `SparkHighMemoryUsage` – high JVM heap usage.
- `SparkHighGCTime` – high GC time.
- `SparkTaskFailures` – task failures in recent minutes.
- `HighCPUUsage` and `HighDiskUsage` – host-level alerts based on Node Exporter.

Alerts are sent to Alertmanager (`config/alertmanager.yml`), which can be configured to notify webhooks or other integrations.

---

## 9. Learning Path for Students

Recommended flow:

1. Start the stack with Docker Compose.
2. Explore the UIs (Spark, Prometheus, Grafana, Alertmanager).
3. Run `etl_job.py` and watch how metrics and dashboards change.
4. Inspect alert rules and trigger them by increasing load or reducing resources.
5. Extend dashboards or add new alerts as exercises.

For a more detailed, step-by-step lab with diagrams and PromQL examples, see `docs/spark-observability-lab.md`.
