# Spark Prometheus Connection Issues - Diagnosis & Fix

## Current Problem

**Error**: `dial tcp 172.20.0.6:4040: connect: connection refused`

This means:
- Prometheus can resolve `spark-master` to IP `172.20.0.6`
- Port 4040 is **not listening** on that container
- The Spark metrics endpoint `/metrics/prometheus` doesn't exist

---

## Why Port 4040 Isn't Available

### Root Cause
Port 4040 is the **Spark Driver/Master UI port**, but it only becomes available when:
1. A Spark job is submitted and running, OR
2. The Spark History Server is actively serving logs

Without a running job, the Spark Master just listens on port 8080 (the web UI), not 4040.

**In your setup**: You have no Spark jobs running, so port 4040 doesn't exist.

---

## Solution: Enable Spark Metrics Properly

You need to explicitly configure Spark to expose metrics on a dedicated port. Here's how:

### Step 1: Create `config/metrics.properties`

```properties
# Spark Metrics Configuration for Prometheus

# Master/Driver metrics
master.sink.prometheus.class=org.apache.spark.metrics.sink.PrometheusSink
master.sink.prometheus.path=/metrics/prometheus
master.sink.prometheus.port=8888

# Worker metrics  
worker.sink.prometheus.class=org.apache.spark.metrics.sink.PrometheusSink
worker.sink.prometheus.path=/metrics/prometheus
worker.sink.prometheus.port=8889

# Application/Driver metrics (for running jobs)
driver.sink.prometheus.class=org.apache.spark.metrics.sink.PrometheusSink
driver.sink.prometheus.path=/metrics/prometheus
driver.sink.prometheus.port=8890

# Executor metrics
executor.sink.prometheus.class=org.apache.spark.metrics.sink.PrometheusSink
executor.sink.prometheus.path=/metrics/prometheus
executor.sink.prometheus.port=8891
```

### Step 2: Update `docker-compose.yml`

**For spark-master**, add volume mount and environment variable:

```yaml
spark-master:
  image: spark:3.5.0
  container_name: spark-master
  hostname: spark-master
  command: "/opt/spark/bin/spark-class org.apache.spark.deploy.master.Master"
  ports:
    - "8080:8080"      # Master Web UI
    - "7077:7077"      # Master RPC
    - "8888:8888"      # Prometheus metrics
  environment:
    - SPARK_MASTER_HOST=spark-master
    - SPARK_MASTER_PORT=7077
    - SPARK_CONF_DIR=/opt/spark/conf
  volumes:
    - ./config/metrics.properties:/opt/spark/conf/metrics.properties:ro
    - spark-events:/opt/spark/spark-events
    - ./jobs:/opt/spark/jobs
    - ./data:/opt/spark/data
  networks:
    - obs-spark
```

**For spark-worker**, add volume mount and environment variable:

```yaml
spark-worker:
  image: spark:3.5.0
  container_name: spark-worker-1
  hostname: spark-worker-1
  command: "/opt/spark/bin/spark-class org.apache.spark.deploy.worker.Worker spark://spark-master:7077"
  depends_on:
    - spark-master
  ports:
    - "8081:8081"      # Worker Web UI
    - "8889:8889"      # Prometheus metrics
  environment:
    - SPARK_MASTER_URL=spark://spark-master:7077
    - SPARK_WORKER_CORES=2
    - SPARK_WORKER_MEMORY=2G
    - SPARK_CONF_DIR=/opt/spark/conf
  volumes:
    - ./config/metrics.properties:/opt/spark/conf/metrics.properties:ro
    - spark-events:/opt/spark/spark-events
    - ./jobs:/opt/spark/jobs
    - ./data:/opt/spark/data
  networks:
    - obs-spark
```

**Remove all JMX-related environment variables** (the old approach won't work):
- Remove `SPARK_DRIVER_JAVA_OPTIONS`
- Remove `SPARK_EXECUTOR_JAVA_OPTIONS`
- Remove all JMX volume mounts from both containers

### Step 3: Update `prometheus.yml`

Replace the broken scrape configs with this:

```yaml
scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Spark Master/Driver metrics
  - job_name: 'spark-master'
    metrics_path: '/metrics/prometheus'
    scrape_interval: 15s
    static_configs:
      - targets: ['spark-master:8888']
        labels:
          component: 'master'
          app: 'spark'

  # Spark Worker metrics
  - job_name: 'spark-worker'
    metrics_path: '/metrics/prometheus'
    scrape_interval: 15s
    static_configs:
      - targets: ['spark-worker-1:8889']
        labels:
          component: 'worker'
          app: 'spark'

  # Spark Driver (running jobs) - optional, only works when jobs are running
  - job_name: 'spark-driver-jobs'
    metrics_path: '/metrics/prometheus'
    scrape_interval: 15s
    scrape_timeout: 5s
    static_configs:
      - targets: ['spark-master:8890']
        labels:
          component: 'driver'
          app: 'spark'

  # Node Exporter (Host metrics)
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
        labels:
          node: 'cluster-node'
```

---

## Implementation Checklist

- [ ] Create `config/metrics.properties` with the content above
- [ ] Update `docker-compose.yml` spark-master service
- [ ] Update `docker-compose.yml` spark-worker service
- [ ] **Remove all JMX environment variables** from both Spark services
- [ ] **Remove all JMX volume mounts** (jmx_prometheus_javaagent.jar and YAML configs)
- [ ] Update `prometheus.yml` with new scrape configs
- [ ] Run `docker-compose down && docker-compose up -d`
- [ ] Wait 30 seconds, then check Prometheus targets page
- [ ] Targets should now show `up` status

---

## Verification

1. **Check Prometheus targets**: Go to `http://localhost:9090/targets`
   - Should see spark-master, spark-worker, spark-driver-jobs as `UP`

2. **Check metrics directly**:
   ```bash
   curl http://localhost:8888/metrics/prometheus  # Master metrics
   curl http://localhost:8889/metrics/prometheus  # Worker metrics
   ```

3. **View in Grafana**: Metrics should appear in Grafana dashboards with prefix `spark_`

---

## Why This Works

- **Uses native Spark metrics**: No JMX complexity
- **Dedicated ports**: Master (8888), Worker (8889), Driver (8890), Executor (8891)
- **Always available**: Metrics exposed even without running jobs
- **Standard Prometheus format**: Native support, no custom agents needed
- **Configuration-driven**: metrics.properties is the standard Spark way