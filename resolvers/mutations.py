import json
from ariadne import MutationType
import database
from models import OperationalMetric
from services.redis_service import redis_service
from services.ai_agent import ai_agent_service

mutation = MutationType()

def process_single_ingestion(db, input_data: dict) -> OperationalMetric:
    src_service = input_data["sourceService"]
    metric_name = input_data["metricName"]
    val = float(input_data["metricValue"])
    thresh = float(input_data["thresholdLimit"])
    raw_payload = input_data.get("payload", "{}")

    # Evaluate status
    if val >= thresh * 1.3:
        status = "CRITICAL"
    elif val >= thresh:
        status = "WARNING"
    else:
        status = "HEALTHY"

    try:
        parsed_payload = json.loads(raw_payload) if isinstance(raw_payload, str) and raw_payload.strip().startswith("{") else {"raw": str(raw_payload)}
    except Exception:
        parsed_payload = {"raw": str(raw_payload)}

    metric = OperationalMetric(
        source_service=src_service,
        metric_name=metric_name,
        metric_value=val,
        threshold_limit=thresh,
        status=status,
        payload=parsed_payload
    )

    db.add(metric)
    db.commit()
    db.refresh(metric)

    metric_dict = metric.to_dict()

    # Invalidate query caches
    redis_service.invalidate_cache()

    # Publish telemetry stream update
    redis_service.publish_event("telemetry:stream", metric_dict)

    # If critical, trigger RCA alert broadcast
    if status == "CRITICAL":
        insight = ai_agent_service.analyze_anomaly(
            service=src_service,
            metric_name=metric_name,
            detected_value=val,
            threshold_limit=thresh,
            status=status
        )
        redis_service.publish_event("telemetry:alerts", insight)

    return metric

@mutation.field("ingestMetric")
def resolve_ingest_metric(parent, info, input):
    db = database.SessionLocal()
    try:
        metric = process_single_ingestion(db, input)
        return metric.to_dict()
    finally:
        db.close()

@mutation.field("batchIngestMetrics")
def resolve_batch_ingest_metrics(parent, info, inputs):
    db = database.SessionLocal()
    count = 0
    try:
        for item in inputs:
            process_single_ingestion(db, item)
            count += 1
        return count
    finally:
        db.close()
