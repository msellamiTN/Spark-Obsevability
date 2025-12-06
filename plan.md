# Spark Observability Lab – Build Plan

## 1. Objectives
- Set up a local Spark cluster (master + worker) with Docker Compose.
- Expose Spark JVM and application metrics via JMX Prometheus Exporter.
- Collect, store, and visualize metrics using Prometheus and Grafana.
- Configure basic alerts with Alertmanager.
- Provide example Spark jobs (batch ETL, optional streaming) to generate metrics.

---

## 2. Target Architecture (High-Level)
- **Compute**
  - Spark Master (driver, web UI 8080, RPC 7077, JMX 7071)
  - Spark Worker (executors, web UI 8081, JMX 7072)
- **Metrics & Alerting**
  - JMX Prometheus Java Agent (driver + executors)
  - Prometheus (scrapes Spark JMX, Spark UI metrics, node-exporter)
  - Alertmanager (routes alerts, optional webhook)
  - Node Exporter (host/system metrics)
- **Dashboards**
  - Grafana with provisioned Prometheus data source
  - Dashboards for Spark cluster, Spark jobs, and system metrics

---

## 3. Project Structure

```text
spark-observability-lab/
├── docker-compose.yml
├── plan.md                      # This plan
├── docs/
│   └── spark-observability-lab.md
├── config/
│   ├── prometheus.yml
│   ├── spark-driver-jmx-exporter.yaml
│   ├── spark-executor-jmx-exporter.yaml
│   ├── alertmanager.yml
│   └── alert-rules.yml
├── jobs/
│   ├── etl_job.py
│   ├── streaming_job.py         # (optional)
│   └── data_generator.py        # (optional)
├── grafana/
│   ├── dashboards/
│   │   ├── spark-cluster.json
│   │   ├── spark-jobs.json
│   │   └── system-metrics.json
│   └── provisioning/
│       ├── datasources.yaml
│       └── dashboards.yaml
├── jars/
│   └── jmx_prometheus_javaagent.jar
└── data/
    └── etl_output/              # created by jobs
```

---

## 4. Implementation Phases

### Phase 1 – Base Infrastructure & Config

1. **Create directories**
   - `config/`, `jobs/`, `grafana/dashboards/`, `grafana/provisioning/`, `jars/`, `data/`.
2. **Download JMX exporter JAR**
   - Place `jmx_prometheus_javaagent.jar` in `jars/`.
3. **Prometheus configuration**
   - Create `config/prometheus.yml`:
     - `global` scrape settings.
     - `scrape_configs` for `prometheus`, `spark-driver`, `spark-executors`, `node-exporter`, `spark-app-metrics`.
4. **Alert rules**
   - Create `config/alert-rules.yml` for Spark and node alerts.
5. **Alertmanager**
   - Create `config/alertmanager.yml` with a default route and optional webhook receiver.
6. **Docker Compose**
   - Create `docker-compose.yml` with services:
     - `prometheus`, `grafana`, `alertmanager`, `node-exporter`, `spark-master`, `spark-worker`.
   - Mount configs and JMX exporter JAR.
   - Expose ports (Spark UIs, JMX, Prometheus, Grafana, Alertmanager, node-exporter).

**Exit criteria:** `docker-compose up -d` starts all containers and UIs are reachable.

---

### Phase 2 – Spark Jobs & Instrumentation

7. **Batch ETL job**
   - Implement `jobs/etl_job.py`:
     - Build `SparkSession` with `master = spark://spark-master:7077`.
     - Set `spark.metrics.namespace = etl_job`.
     - Generate test data, transform, aggregate, and write to `/data/etl_output`.
     - Sleep (e.g. 30s) before shutdown to allow metrics scraping.
8. **Optional streaming job**
   - Implement `jobs/streaming_job.py` (structured streaming from socket/file/Kafka).
   - Use similar metrics namespace configuration.
9. **Optional data generator**
   - Implement `jobs/data_generator.py` to feed streaming source.
10. **Job submission scripts/commands**
   - Standard commands using `docker exec spark-master spark-submit ...` for each job.

**Exit criteria:** Running `etl_job.py` produces results and Spark metrics appear in Prometheus.

---

### Phase 3 – Dashboards & Validation

11. **Grafana provisioning**
   - `grafana/provisioning/datasources.yaml` for Prometheus.
   - `grafana/provisioning/dashboards.yaml` pointing to `/var/lib/grafana/dashboards`.
12. **Dashboards**
   - `grafana/dashboards/spark-cluster.json`:
     - JVM heap used vs max.
     - GC time.
     - Executor memory usage.
     - Tasks completed/failed.
   - `grafana/dashboards/spark-jobs.json`:
     - Job and stage durations.
     - Task execution rate.
   - `grafana/dashboards/system-metrics.json`:
     - CPU, memory, disk metrics from node-exporter.
13. **Validation steps**
   - Run ETL job, then check:
     - Prometheus targets page (all `UP`).
     - PromQL queries: `up{job="spark-driver"}`, `jvm_heap_memory_used / jvm_heap_memory_max`, `rate(spark_tasks_completed_total[5m])`.
     - Grafana dashboards for live metrics.

**Exit criteria:** Dashboards automatically load and display meaningful metrics during job execution.

---

### Phase 4 – Lab Workflow for Students

14. **Part 1 – Environment setup**
   - Install Docker and Docker Compose.
   - Clone or create `spark-observability-lab` project from template.
15. **Part 2 – Bring up the stack**
   - `docker-compose up -d`.
   - Verify containers and UIs.
16. **Part 3 – Run and observe jobs**
   - Submit `etl_job.py`.
   - Explore Spark UI, Prometheus metrics, Grafana dashboards.
17. **Part 4 – Alerts**
   - Intentionally stress memory / tasks to trigger alerts.
   - Observe alerts in Prometheus and Alertmanager.
18. **Part 5 – Exercises**
   - Extend dashboards.
   - Add new alert rules.
   - Modify job logic and observe impact on metrics.

---

### Phase 5 – Optional Extensions

19. **Logging**
   - Integrate ELK (Elasticsearch, Logstash/Filebeat, Kibana) for Spark logs.
20. **Tracing**
   - Add Jaeger and basic OpenTelemetry instrumentation in the Spark driver.
21. **Production hardening**
   - Enable authentication, TLS, and resource limits.
   - Tune Prometheus retention and storage.
