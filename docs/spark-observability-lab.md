# Docker Compose Spark Cluster Observability Lab
## Complete Setup with Prometheus, Grafana, and JMX Exporter

**Version:** 2.0 | **Last Updated:** December 2025  
**Spark Version:** 3.4.1 | **Prometheus:** 2.50+ | **Grafana:** 10.0+

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Installation & Setup](#installation--setup)
5. [Running the Lab](#running-the-lab)
6. [Spark Job Submission](#spark-job-submission)
7. [Grafana Dashboards](#grafana-dashboards)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Configurations](#advanced-configurations)

---

## Architecture Overview

This lab demonstrates a complete observability stack for Apache Spark:

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Network: obs-spark               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │   Spark Master   │  │   Spark Worker   │                │
│  │  (+ Driver)      │  │  (+ Executors)   │                │
│  │                  │  │                  │                │
│  │ JMX Metrics Port │  │ JMX Metrics Port │                │
│  │  :7071 (driver)  │  │  :7072 (exec)    │                │
│  └─────────┬────────┘  └────────┬─────────┘                │
│            │                    │                           │
│            │ Expose metrics     │                           │
│            └─────────┬──────────┘                           │
│                      │                                      │
│          ┌───────────▼──────────┐                          │
│          │ Prometheus (9090)    │                          │
│          │ - Scrape Spark JMX   │                          │
│          │ - Store metrics      │                          │
│          │ - Alert rules        │                          │
│          └───────────┬──────────┘                          │
│                      │                                      │
│          ┌───────────▼──────────┐                          │
│          │ Grafana (3000)       │                          │
│          │ - Dashboards         │                          │
│          │ - Visualizations     │                          │
│          │ - Alerting           │                          │
│          └──────────────────────┘                          │
│                                                              │
│  ┌──────────────────┐                                      │
│  │   Node Exporter  │  (Host metrics)                      │
│  │  :9100           │                                      │
│  └──────────────────┘                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **Spark Master + Worker**: Distributed processing with JMX metrics
- **Prometheus**: Time-series database, metric scraping, alert evaluation
- **Grafana**: Visualization, dashboarding, alerting
- **JMX Exporter**: Translates JVM metrics to Prometheus format
- **Node Exporter**: System-level metrics (CPU, memory, disk, network)

---

## Prerequisites

**System Requirements:**
- Docker & Docker Compose (20.10+)
- 4+ CPU cores
- 8+ GB RAM
- 10GB free disk space

**Software:**
```bash
docker --version     # Docker 20.10+
docker-compose --version  # Docker Compose 2.0+
```

**Verify Installation:**
```bash
docker run hello-world
docker-compose --version
```

---

## Project Structure

```
spark-observability-lab/
├── docker-compose.yml
├── config/
│   ├── prometheus.yml
│   ├── spark-driver-jmx-exporter.yaml
│   ├── spark-executor-jmx-exporter.yaml
│   ├── alertmanager.yml
│   └── alert-rules.yml
├── jobs/
│   ├── etl_job.py
│   ├── streaming_job.py
│   └── data_generator.py
├── grafana/
│   ├── dashboards/
│   │   ├── spark-cluster.json
│   │   ├── spark-jobs.json
│   │   └── system-metrics.json
│   └── provisioning/
│       ├── datasources.yaml
│       └── dashboards.yaml
└── README.md
```

---

## Installation & Setup

### Step 1: Create Project Directory

```bash
mkdir spark-observability-lab
cd spark-observability-lab

# Create subdirectories
mkdir -p config jobs grafana/dashboards grafana/provisioning
```

### Step 2: Download JMX Exporter JAR

```bash
mkdir -p jars

# Download the JMX Prometheus Exporter JAR
wget -O jars/jmx_prometheus_javaagent.jar \
  https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/1.0.0/jmx_prometheus_javaagent-1.0.0.jar

# Verify download
ls -lh jars/jmx_prometheus_javaagent.jar
```

### Step 3: Create Prometheus Configuration

**File: `config/prometheus.yml`**

```yaml
# Prometheus configuration
global:
  scrape_interval: 10s
  scrape_timeout: 5s
  evaluation_interval: 10s
  external_labels:
    monitor: 'spark-cluster'
    environment: 'local'

# Alerting configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Alert rules
rule_files:
  - '/etc/prometheus/alert-rules.yml'

# Scrape configurations
scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Spark Driver metrics via JMX Exporter
  - job_name: 'spark-driver'
    metrics_path: '/metrics'
    scrape_interval: 5s
    static_configs:
      - targets: ['spark-master:7071']
        labels:
          component: 'driver'
          app: 'spark'

  # Spark Executor metrics (port varies by executor)
  - job_name: 'spark-executors'
    metrics_path: '/metrics'
    scrape_interval: 5s
    static_configs:
      - targets: ['spark-worker:7072']
        labels:
          component: 'executor'
          app: 'spark'

  # Node Exporter (Host metrics)
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
        labels:
          node: 'cluster-node'

  # Spark Application Metrics (native endpoint)
  - job_name: 'spark-app-metrics'
    metrics_path: '/metrics/prometheus'
    scrape_interval: 5s
    scrape_timeout: 3s
    static_configs:
      - targets: ['localhost:4040']
        labels:
          type: 'spark-driver-ui'
    relabel_configs:
      - source_labels: [__address__]
        regex: '([^:]+)(?::\d+)?'
        target_label: instance
        replacement: '${1}:4040'
```

### Step 4: Create JMX Exporter Configurations

**File: `config/spark-driver-jmx-exporter.yaml`**

```yaml
# JMX Exporter config for Spark Driver
lowercaseOutputName: true
lowercaseOutputLabelNames: true
whitelistObjectNames:
  # JVM Metrics
  - 'java.lang:type=Memory'
  - 'java.lang:type=GarbageCollector,name=*'
  - 'java.lang:type=Threading'
  - 'java.lang:type=Runtime'
  
  # Spark Metrics
  - 'metrics:name=jvm.*'
  - 'metrics:name=driver.*'
  - 'metrics:name=executor.*'
  - 'metrics:name=BlockManager.*'
  - 'metrics:name=DAGScheduler.*'
  - 'metrics:name=tasks.*'
  - 'metrics:name=stage.*'

rules:
  # JVM Memory
  - pattern: 'java.lang<type=Memory>HeapMemoryUsage(.+)'
    name: 'jvm_heap_memory_$1'
    type: GAUGE
    help: 'JVM Heap Memory'

  # Garbage Collection
  - pattern: 'java.lang<type=GarbageCollector, name=(.+?)><CollectionCount|CollectionTime>'
    name: 'jvm_gc_${0}_${1}'
    type: GAUGE
    labels:
      gc_name: '$1'

  # Threading
  - pattern: 'java.lang<type=Threading><ThreadCount|PeakThreadCount>'
    name: 'jvm_threads_${0}'
    type: GAUGE

  # Spark Tasks
  - pattern: 'metrics<name=(.+?)><(.+?)>'
    name: 'spark_$1_$2'
    type: GAUGE
```

**File: `config/spark-executor-jmx-exporter.yaml`**

```yaml
# JMX Exporter config for Spark Executors
lowercaseOutputName: true
lowercaseOutputLabelNames: true
whitelistObjectNames:
  # JVM Metrics
  - 'java.lang:type=Memory'
  - 'java.lang:type=GarbageCollector,name=*'
  - 'java.lang:type=Threading'
  
  # Spark Executor Metrics
  - 'metrics:name=executor.*'
  - 'metrics:name=BlockManager.*'

rules:
  # JVM Memory
  - pattern: 'java.lang<type=Memory>HeapMemoryUsage(.+)'
    name: 'jvm_heap_memory_$1'
    type: GAUGE

  # Garbage Collection
  - pattern: 'java.lang<type=GarbageCollector, name=(.+?)><CollectionCount|CollectionTime>'
    name: 'jvm_gc_${0}_${1}'
    type: GAUGE
    labels:
      gc_name: '$1'

  # Executor Metrics
  - pattern: 'metrics<name=(.+?)><(.+?)>'
    name: 'spark_$1_$2'
    type: GAUGE
```

### Step 5: Create Alert Rules

**File: `config/alert-rules.yml`**

```yaml
groups:
  - name: spark_alerts
    interval: 10s
    rules:
      # High memory usage
      - alert: SparkHighMemoryUsage
        expr: 'jvm_heap_memory_used / jvm_heap_memory_max > 0.85'
        for: 2m
        labels:
          severity: 'warning'
        annotations:
          summary: 'High heap memory usage detected'
          description: 'Spark {{ $labels.instance }} heap memory usage > 85%'

      # High GC time
      - alert: SparkHighGCTime
        expr: 'rate(jvm_gc_collection_seconds_sum[5m]) > 0.1'
        for: 2m
        labels:
          severity: 'warning'
        annotations:
          summary: 'High garbage collection time'
          description: 'Spark {{ $labels.instance }} GC time is elevated'

      # Task failures
      - alert: SparkTaskFailures
        expr: 'increase(spark_tasks_failed_total[5m]) > 0'
        for: 1m
        labels:
          severity: 'warning'
        annotations:
          summary: 'Spark task failures detected'
          description: 'Tasks failing on {{ $labels.instance }}'

  - name: node_alerts
    interval: 10s
    rules:
      # High CPU usage
      - alert: HighCPUUsage
        expr: '100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80'
        for: 2m
        labels:
          severity: 'warning'
        annotations:
          summary: 'High CPU usage'
          description: 'CPU usage on {{ $labels.instance }} is above 80%'

      # High disk usage
      - alert: HighDiskUsage
        expr: '(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100 > 85'
        for: 2m
        labels:
          severity: 'warning'
        annotations:
          summary: 'High disk usage'
          description: 'Disk usage on {{ $labels.instance }} is above 85%'
```

### Step 6: Create Alertmanager Configuration

**File: `config/alertmanager.yml`**

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'default'
  group_by: ['alertname', 'instance']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h

receivers:
  - name: 'default'
    webhook_configs:
      # Optional: Send to webhook
      - url: 'http://localhost:5001/'
        send_resolved: true
```

### Step 7: Create Docker Compose File

**File: `docker-compose.yml`**

```yaml
version: '3.8'

services:
  # Prometheus - Metrics collection and storage
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./config/alert-rules.yml:/etc/prometheus/alert-rules.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    networks:
      - obs-spark
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:9090"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  # Grafana - Visualization and Dashboarding
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_SECURITY_ADMIN_USER=admin
      - GF_INSTALL_PLUGINS=grafana-piechart-panel,grafana-worldmap-panel
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - grafana_data:/var/lib/grafana
    depends_on:
      prometheus:
        condition: service_healthy
    networks:
      - obs-spark
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  # Alertmanager - Alert routing and management
  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./config/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    networks:
      - obs-spark
    restart: unless-stopped

  # Node Exporter - System metrics
  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    ports:
      - "9100:9100"
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    networks:
      - obs-spark
    restart: unless-stopped

  # Spark Master with JMX metrics
  spark-master:
    image: docker.io/spark:3.4.1
    container_name: spark-master
    ports:
      - "8080:8080"
      - "7077:7077"
      - "4040:4040"
      - "7071:7071"  # JMX metrics port
    environment:
      - SPARK_MODE=master
      - SPARK_RPC_AUTHENTICATION_ENABLED=no
      - SPARK_RPC_ENCRYPTION_ENABLED=no
      - SPARK_LOCAL_STORAGE_ENCRYPTION_ENABLED=no
      - SPARK_SSL_ENABLED=no
      # JMX configuration
      - SPARK_DRIVER_JAVA_OPTIONS=-Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.port=7071 -Dcom.sun.management.jmxremote.authenticate=false -Dcom.sun.management.jmxremote.ssl=false -Djava.rmi.server.hostname=spark-master
    volumes:
      - ./jars/jmx_prometheus_javaagent.jar:/opt/spark/jars/jmx_prometheus_javaagent.jar:ro
      - ./config/spark-driver-jmx-exporter.yaml:/opt/spark/conf/driver-jmx-exporter.yaml:ro
      - ./jobs:/jobs
      - ./data:/data
    command: bin/spark-class org.apache.spark.deploy.master.Master --host spark-master --port 7077 --webui-port 8080
    networks:
      - obs-spark
    restart: unless-stopped

  # Spark Worker
  spark-worker:
    image: docker.io/spark:3.4.1
    container_name: spark-worker
    ports:
      - "8081:8081"
      - "7072:7072"  # JMX metrics port
    environment:
      - SPARK_MODE=worker
      - SPARK_MASTER_HOST=spark-master
      - SPARK_MASTER_PORT=7077
      - SPARK_WORKER_PORT=7078
      - SPARK_WORKER_WEBUI_PORT=8081
      - SPARK_WORKER_CORES=2
      - SPARK_WORKER_MEMORY=2G
      # JMX configuration
      - SPARK_EXECUTOR_JAVA_OPTIONS=-Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.port=7072 -Dcom.sun.management.jmxremote.authenticate=false -Dcom.sun.management.jmxremote.ssl=false -Djava.rmi.server.hostname=spark-worker
    volumes:
      - ./jars/jmx_prometheus_javaagent.jar:/opt/spark/jars/jmx_prometheus_javaagent.jar:ro
      - ./config/spark-executor-jmx-exporter.yaml:/opt/spark/conf/executor-jmx-exporter.yaml:ro
      - ./jobs:/jobs
      - ./data:/data
    depends_on:
      - spark-master
    networks:
      - obs-spark
    restart: unless-stopped

networks:
  obs-spark:
    driver: bridge

volumes:
  prometheus_data:
  grafana_data:
  alertmanager_data:
```

---

## Running the Lab

### Step 1: Start All Services

```bash
docker-compose build
docker-compose up -d

# Verify all containers are running
docker-compose ps
```

Expected output:
```
NAME               STATUS              PORTS
spark-master       Up 10 seconds        8080->8080/tcp, 7077->7077/tcp
spark-worker       Up 8 seconds         8081->8081/tcp, 7078->7078/tcp
prometheus         Up 5 seconds         9090->9090/tcp
grafana            Up 3 seconds         3000->3000/tcp
alertmanager       Up 2 seconds         9093->9093/tcp
node-exporter      Up 1 second          9100->9100/tcp
```

### Step 2: Access Web UIs

| Service | URL | Credentials |
|---------|-----|-------------|
| Spark Master | http://localhost:8080 | - |
| Spark Worker | http://localhost:8081 | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | `admin` / `admin` |
| Alertmanager | http://localhost:9093 | - |

### Step 3: Verify Prometheus Targets

Visit http://localhost:9090/targets

All targets should show **UP** status:
- `prometheus` (9090)
- `spark-driver` (7071)
- `spark-executors` (7072)
- `node-exporter` (9100)

---

## Spark Job Submission

### Sample ETL Job with Metrics

**File: `jobs/etl_job.py`**

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as spark_sum, count, avg, max as spark_max
import time
import sys

def create_sample_data(spark, num_records=10000):
    """Generate sample data for ETL"""
    from pyspark.sql.types import StructType, StructField, IntegerType, StringType, DoubleType
    
    data = [(i, f"product_{i%100}", float(i % 1000), i % 10) 
            for i in range(num_records)]
    
    schema = StructType([
        StructField("id", IntegerType(), True),
        StructField("product", StringType(), True),
        StructField("amount", DoubleType(), True),
        StructField("region", IntegerType(), True)
    ])
    
    return spark.createDataFrame(data, schema)

def etl_pipeline(spark):
    """ETL pipeline with multiple stages"""
    
    print("=" * 50)
    print("Starting ETL Pipeline")
    print("=" * 50)
    
    # Stage 1: Load data
    print("\n[STAGE 1] Loading data...")
    df = create_sample_data(spark, num_records=100000)
    print(f"Loaded {df.count()} records")
    
    # Stage 2: Transform
    print("\n[STAGE 2] Transforming data...")
    df_transformed = df.filter(col("amount") > 100) \
                       .withColumn("amount_usd", col("amount") * 1.1) \
                       .select("id", "product", "amount", "amount_usd", "region")
    print(f"Transformed {df_transformed.count()} records")
    
    # Stage 3: Aggregate
    print("\n[STAGE 3] Aggregating by region...")
    df_agg = df_transformed.groupBy("region") \
                           .agg(
                               spark_sum("amount").alias("total_amount"),
                               count("*").alias("transaction_count"),
                               avg("amount").alias("avg_amount"),
                               spark_max("amount").alias("max_amount")
                           ) \
                           .sort(col("total_amount").desc())
    print(f"Aggregated into {df_agg.count()} regions")
    
    # Stage 4: Output results
    print("\n[STAGE 4] Writing results...")
    df_agg.coalesce(1).write.mode("overwrite").csv("/data/etl_output", header=True)
    print("Results written to /data/etl_output")
    
    # Show sample results
    print("\n[RESULTS] Sample aggregations:")
    df_agg.show()
    
    print("\n" + "=" * 50)
    print("ETL Pipeline Completed")
    print("=" * 50)
    
    return df_agg

def main():
    # Create Spark session with metrics enabled
    spark = SparkSession.builder \
        .appName("SparkETLJob") \
        .master("spark://spark-master:7077") \
        .config("spark.executor.memory", "1g") \
        .config("spark.executor.cores", "2") \
        .config("spark.metrics.namespace", "etl_job") \
        .getOrCreate()
    
    try:
        # Run ETL pipeline
        result = etl_pipeline(spark)
        
        # Keep running for metric collection
        print("\nMetrics collection in progress...")
        print("Visit Prometheus at http://localhost:9090/targets")
        print("Visit Grafana at http://localhost:3000")
        
        time.sleep(30)  # Allow time for metric scraping
        
    except Exception as e:
        print(f"Error in ETL pipeline: {e}")
        sys.exit(1)
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
```

### Submit Spark Job

```bash
# Submit the job
docker exec spark-master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --executor-memory 1g \
  --executor-cores 2 \
  /jobs/etl_job.py

# Monitor in Spark UI: http://localhost:4040
```

### Monitor Metrics Collection

During job execution:

**Prometheus Queries:**
```promql
# Check metrics are being collected
up{job="spark-driver"}

# Heap memory usage
jvm_heap_memory_used / jvm_heap_memory_max

# Task execution rate
rate(spark_tasks_completed_total[5m])

# Job completion rate
rate(spark_jobs_total[5m])
```

---

## Grafana Dashboards

### Setup Grafana Data Sources

**File: `grafana/provisioning/datasources.yaml`**

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

**File: `grafana/provisioning/dashboards.yaml`**

```yaml
apiVersion: 1

providers:
  - name: 'Spark Dashboards'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

### Create Custom Spark Dashboard

Create **`grafana/dashboards/spark-cluster.json`** with these key panels:

**Example Panel: Heap Memory Usage**
```json
{
  "title": "Spark Heap Memory Usage",
  "type": "graph",
  "targets": [
    {
      "expr": "jvm_heap_memory_used / 1024 / 1024",
      "legendFormat": "Heap Used (MB)"
    },
    {
      "expr": "jvm_heap_memory_max / 1024 / 1024",
      "legendFormat": "Heap Max (MB)"
    }
  ]
}
```

**Example Panel: Task Execution Rate**
```json
{
  "title": "Task Execution Rate",
  "type": "graph",
  "targets": [
    {
      "expr": "rate(spark_tasks_completed_total[1m])",
      "legendFormat": "Tasks/sec"
    }
  ]
}
```

---

## Troubleshooting

### Issue: Prometheus targets show DOWN

**Solution:**
```bash
# Check service connectivity
docker exec prometheus ping spark-master

# Verify JMX ports are exposed
docker exec spark-master netstat -tlnp | grep 7071

# Check Prometheus logs
docker logs prometheus
```

### Issue: No metrics appearing

**Solution:**
1. Ensure JMX JAR is mounted in containers
2. Verify JMX exporter YAML files are correct
3. Check Spark logs: `docker logs spark-master`
4. Manually test JMX: `curl http://localhost:7071/metrics`

### Issue: Grafana cannot connect to Prometheus

**Solution:**
```bash
# Restart Grafana
docker restart grafana

# Verify network connectivity
docker network inspect obs-spark
```

---

## Advanced Configurations

### Enable Spark Native Prometheus Metrics (Spark 3.0+)

```bash
# Add to spark-submit command
--conf spark.metrics.appStatusSource.enabled=true \
--conf spark.metrics.conf=/opt/spark/conf/metrics.properties
```

### Configure Prometheus Retention

**In `docker-compose.yml`:**
```yaml
command:
  - '--storage.tsdb.retention.time=90d'
  - '--storage.tsdb.max-block-duration=30d'
```

### Enable Remote Storage (InfluxDB/S3)

```yaml
# Prometheus remote write to InfluxDB
global:
  remote_write:
    - url: "http://influxdb:8086/api/v1/prom/write?db=prometheus"
```

### Add Custom Spark Exporter

For long-running Spark jobs, use **Prometheus Pushgateway**:

```yaml
pushgateway:
  image: prom/pushgateway:latest
  ports:
    - "9091:9091"
  networks:
    - obs-spark
```

---

## Metrics Reference

### Key Spark Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `jvm_heap_memory_used` | Current heap usage | > 85% |
| `jvm_gc_collection_seconds_sum` | GC time | > 10% of runtime |
| `spark_tasks_completed_total` | Completed tasks | - |
| `spark_tasks_failed_total` | Failed tasks | > 5% |
| `spark_executor_memory_usage` | Executor memory | > 80% |
| `spark_stage_delay` | Stage execution delay | > 1min |

---

## Next Steps

1. **Production Hardening**: Add authentication, SSL/TLS, and resource limits
2. **Log Aggregation**: Integrate ELK stack (Elasticsearch, Logstash, Kibana)
3. **Distributed Tracing**: Add Jaeger for request tracing
4. **Advanced Alerts**: Configure Slack/PagerDuty integrations
5. **Cost Analysis**: Add Spark job cost estimation metrics

---

**Questions? Issues?** Check logs:
```bash
docker-compose logs -f [service-name]
docker exec -it [container-name] bash
```