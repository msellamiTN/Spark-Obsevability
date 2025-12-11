# Spark Prometheus Integration Issues & Solutions

## Problems Identified

### 1. **JMX Exporter Not Actually Running**
Your docker-compose.yml sets the environment variables for JMX configuration, but there's a critical issue:

```
SPARK_DRIVER_JAVA_OPTIONS=-javaagent:/opt/spark/jars/jmx_prometheus_javaagent.jar=7071:...
```

**Problem**: This syntax tries to use JMX Exporter as a Java agent attached to the Spark process itself. However:
- The JAR file may not exist at that path in the container
- The configuration file path may be incorrect
- Spark's startup command doesn't properly inherit these JAVA_OPTIONS

### 2. **Multiple Connection Refused Errors**
All three metrics endpoints are down:
- `spark-master:7071` (Driver JMX) - Connection refused
- `spark-worker:7072` (Executor JMX) - Connection refused  
- `spark-master:4040` (Spark UI metrics) - Connection refused

This indicates:
- JMX ports aren't being exposed
- Spark's metrics system isn't configured to expose Prometheus metrics
- Port 4040 may not be accessible because no Spark job is running

---

## Root Causes

### Issue A: JMX Exporter Setup
The current approach assumes:
1. JMX agent JAR exists in the Spark image at `/opt/spark/jars/`
2. Configuration files are properly mounted
3. Java options are inherited by the Spark process

**Reality**: The official `spark:3.5.0` image likely doesn't include the JMX Exporter JAR, and the environment variable approach may not work as expected.

### Issue B: Spark Metrics Configuration
Spark has its own metrics system that can expose Prometheus-formatted metrics, but it requires:
- `metrics.properties` configuration file
- Enabling the Prometheus sink
- Proper classpath setup for the Prometheus metrics library

### Issue C: Port 4040 Unavailability
The Spark Driver UI on port 4040 only exposes `/metrics/prometheus` when a job is actively running or has recently completed. Without a job, this endpoint doesn't exist.

---

## Recommended Solutions

### **Option 1: Use Spark's Native Prometheus Integration (RECOMMENDED)**

Configure Spark to use its built-in Prometheus metrics sink instead of JMX Exporter.

**Steps:**

1. Create a `metrics.properties` file:
```properties
# Enable Prometheus sink for driver
driver.sink.prometheus.class=org.apache.spark.metrics.sink.PrometheusSink
driver.sink.prometheus.path=/metrics/prometheus
driver.sink.prometheus.period=10
driver.sink.prometheus.unit=seconds
driver.sink.prometheus.port=4040

# Enable Prometheus sink for executor
executor.sink.prometheus.class=org.apache.spark.metrics.sink.PrometheusSink
executor.sink.prometheus.path=/metrics/prometheus
executor.sink.prometheus.period=10
executor.sink.prometheus.unit=seconds
executor.sink.prometheus.port=4041
```

2. Update docker-compose.yml:
```yaml
spark-master:
  # ... existing config ...
  volumes:
    - ./config/metrics.properties:/opt/spark/conf/metrics.properties:ro
  environment:
    - SPARK_CONF_DIR=/opt/spark/conf
```

3. Update prometheus.yml to only scrape the metrics endpoint:
```yaml
scrape_configs:
  - job_name: 'spark-driver'
    static_configs:
      - targets: ['spark-master:4040']
    metrics_path: '/metrics/prometheus'
    scrape_interval: 15s
```

### **Option 2: Use a Separate JMX Exporter Container**

Run JMX Exporter as a separate service that connects to Spark's JMX port.

**Pros**: Cleaner separation of concerns
**Cons**: Requires exposing JMX remotely (security consideration)

### **Option 3: Use Spark Structured Streaming + Prometheus PushGateway**

For batch jobs or streaming applications, have Spark push metrics to Prometheus PushGateway.

---

## Immediate Quick Fix

If you want to get something working immediately without a running Spark job:

1. **Comment out the spark-app-metrics job** in prometheus.yml (it won't work without an active job)
2. **Remove JMX configuration** from docker-compose.yml for now
3. **Add node-exporter metrics** to monitor the cluster's system resources
4. **Deploy a test Spark job** that runs continuously to populate port 4040

This will at least let your observability stack function while you implement proper metrics collection.

---

## Files to Create/Modify

1. `./config/metrics.properties` - Spark metrics configuration
2. `docker-compose.yml` - Add volume mount for metrics.properties
3. `prometheus.yml` - Update to correct target ports
4. Remove or significantly modify the JMX-related environment variables