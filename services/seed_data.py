import time
import random
import json
import requests
from datetime import datetime, timezone

SERVICES = ['auth-service', 'payment-gateway', 'order-router', 'search-indexer', 'database-pool']

METRIC_SPECS = {
    'auth-service': [
        ('p99_latency_ms', 120.0, 300.0, 50.0),
        ('cpu_utilization_pct', 45.0, 80.0, 15.0),
        ('error_rate', 2.0, 10.0, 1.0)
    ],
    'payment-gateway': [
        ('p99_latency_ms', 180.0, 400.0, 80.0),
        ('error_rate', 1.0, 5.0, 0.5),
        ('cpu_utilization_pct', 55.0, 85.0, 20.0)
    ],
    'order-router': [
        ('p99_latency_ms', 90.0, 250.0, 30.0),
        ('cpu_utilization_pct', 35.0, 75.0, 10.0),
        ('memory_usage_mb', 512.0, 1024.0, 100.0)
    ],
    'search-indexer': [
        ('p99_latency_ms', 210.0, 500.0, 90.0),
        ('cpu_utilization_pct', 60.0, 90.0, 25.0),
        ('memory_usage_mb', 1024.0, 2048.0, 200.0)
    ],
    'database-pool': [
        ('p99_latency_ms', 45.0, 150.0, 20.0),
        ('cpu_utilization_pct', 40.0, 85.0, 15.0),
        ('error_rate', 0.5, 3.0, 0.2)
    ]
}

def generate_metric_payload(service: str):
    metrics = METRIC_SPECS.get(service, [('p99_latency_ms', 100.0, 250.0, 30.0)])
    name, base, threshold, stdev = random.choice(metrics)

    # 12% chance of anomaly spike
    is_spike = random.random() < 0.12
    if is_spike:
        value = threshold * random.uniform(1.1, 2.5)
    else:
        value = max(1.0, random.gauss(base, stdev))

    value = round(value, 2)
    threshold = round(threshold, 2)

    payload_meta = {
        "host_id": f"node-{random.randint(101, 199)}",
        "region": random.choice(["us-east-1", "us-west-2", "eu-central-1"]),
        "trace_id": f"tr-{random.randint(10000, 99999)}"
    }

    return {
        "sourceService": service,
        "metricName": name,
        "metricValue": value,
        "thresholdLimit": threshold,
        "payload": json.dumps(payload_meta)
    }

def seed_once(target_url="http://localhost:5000/graphql"):
    headers = {"Content-Type": "application/json"}
    mutation = """
    mutation IngestMetric($input: IngestMetricInput!) {
        ingestMetric(input: $input) {
            id
            sourceService
            metricName
            metricValue
            thresholdLimit
            status
            createdAt
        }
    }
    """

    results = []
    for service in SERVICES:
        item = generate_metric_payload(service)
        body = {
            "query": mutation,
            "variables": {"input": item}
        }
        try:
            res = requests.post(target_url, json=body, headers=headers, timeout=5)
            if res.status_code == 200:
                results.append(res.json())
        except Exception as e:
            print(f"[Seed] Ingestion post error: {e}")
    return len(results)

def continuous_seed(target_url="http://localhost:5000/graphql", interval_sec=2.0):
    print(f"[DataPulse Simulator] Telemetry seed stream active targeting {target_url} every {interval_sec}s...")
    count = 0
    try:
        while True:
            ingested = seed_once(target_url)
            count += ingested
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ingested {ingested} metrics. Total: {count}")
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("[DataPulse Simulator] Stream stopped.")

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000/graphql"
    continuous_seed(url)
