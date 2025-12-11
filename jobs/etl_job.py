from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as spark_sum, count, avg, max as spark_max
import time
import sys


def create_sample_data(spark, num_records=10000):
    """Generate sample data for ETL"""
    from pyspark.sql.types import StructType, StructField, IntegerType, StringType, DoubleType

    data = [
        (i, f"product_{i % 100}", float(i % 1000), i % 10)
        for i in range(num_records)
    ]

    schema = StructType([
        StructField("id", IntegerType(), True),
        StructField("product", StringType(), True),
        StructField("amount", DoubleType(), True),
        StructField("region", IntegerType(), True),
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
    df_transformed = (
        df.filter(col("amount") > 100)
        .withColumn("amount_usd", col("amount") * 1.1)
        .select("id", "product", "amount", "amount_usd", "region")
    )
    print(f"Transformed {df_transformed.count()} records")

    # Stage 3: Aggregate
    print("\n[STAGE 3] Aggregating by region...")
    df_agg = (
        df_transformed.groupBy("region")
        .agg(
            spark_sum("amount").alias("total_amount"),
            count("*").alias("transaction_count"),
            avg("amount").alias("avg_amount"),
            spark_max("amount").alias("max_amount"),
        )
        .sort(col("total_amount").desc())
    )
    print(f"Aggregated into {df_agg.count()} regions")

    # Stage 4: Output results
    print("\n[STAGE 4] Writing results...")
    df_agg.coalesce(1).write.mode("overwrite").csv("/opt/spark/data/etl_output", header=True)
    print("Results written to /opt/spark/data/etl_output")

    # Show sample results
    print("\n[RESULTS] Sample aggregations:")
    df_agg.show()

    print("\n" + "=" * 50)
    print("ETL Pipeline Completed")
    print("=" * 50)

    return df_agg


def main():
    # Create Spark session with metrics enabled
    spark = (
        SparkSession.builder.appName("SparkETLJob")
        .master("spark://spark-master:7077")
        .config("spark.executor.memory", "1g")
        .config("spark.executor.cores", "2")
        .config("spark.metrics.namespace", "etl_job")
        .getOrCreate()
    )

    try:
        # Run ETL pipeline
        etl_pipeline(spark)

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
