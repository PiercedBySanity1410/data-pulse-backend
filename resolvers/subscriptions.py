import asyncio
import json
from ariadne import SubscriptionType
from services.redis_service import redis_service

subscription = SubscriptionType()

@subscription.source("metricStream")
async def metric_stream_source(obj, info, service=None):
    pubsub = redis_service.redis_client.pubsub() if redis_service.redis_client else None
    if pubsub:
        pubsub.subscribe("telemetry:stream")
        while True:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg.get("type") == "message":
                try:
                    data = json.loads(msg["data"])
                    if not service or data.get("sourceService") == service:
                        yield data
                except Exception:
                    pass
            await asyncio.sleep(0.5)
    else:
        # Fallback dummy stream if Redis client is missing
        while True:
            await asyncio.sleep(5)
            yield None

@subscription.field("metricStream")
def metric_stream_resolver(metric, info, service=None):
    return metric

@subscription.source("anomalyAlertStream")
async def anomaly_alert_stream_source(obj, info):
    pubsub = redis_service.redis_client.pubsub() if redis_service.redis_client else None
    if pubsub:
        pubsub.subscribe("telemetry:alerts")
        while True:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg.get("type") == "message":
                try:
                    yield json.loads(msg["data"])
                except Exception:
                    pass
            await asyncio.sleep(0.5)
    else:
        while True:
            await asyncio.sleep(5)
            yield None

@subscription.field("anomalyAlertStream")
def anomaly_alert_stream_resolver(alert, info):
    return alert
