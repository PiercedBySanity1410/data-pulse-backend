from datetime import datetime, timedelta, timezone
from ariadne import QueryType
import database
from models import OperationalMetric
from services.redis_service import redis_service, cached_resolver
from services.ai_agent import ai_agent_service
from sqlalchemy import func

query = QueryType()

@query.field("getMetrics")
def resolve_get_metrics(parent, info, service=None, status=None, limit=50, offset=0):
    cache_key = redis_service.generate_cache_key("getMetrics", {"service": service, "status": status, "limit": limit, "offset": offset})
    cached = redis_service.get_cached(cache_key)
    if cached is not None:
        return cached

    db = database.SessionLocal()
    try:
        q = db.query(OperationalMetric)
        if service:
            q = q.filter(OperationalMetric.source_service == service)
        if status:
            q = q.filter(OperationalMetric.status == status)

        q = q.order_by(OperationalMetric.created_at.desc())
        q = q.offset(offset).limit(limit)

        metrics = q.all()
        result = [m.to_dict() for m in metrics]
        redis_service.set_cached(cache_key, result)
        return result
    finally:
        db.close()

@query.field("getServiceSummaries")
def resolve_get_service_summaries(parent, info):
    cache_key = redis_service.generate_cache_key("getServiceSummaries", {})
    cached = redis_service.get_cached(cache_key)
    if cached is not None:
        return cached

    db = database.SessionLocal()
    try:
        # Get all distinct source services
        services = db.query(OperationalMetric.source_service).distinct().all()
        service_names = [s[0] for s in services]

        if not service_names:
            service_names = ['auth-service', 'payment-gateway', 'order-router', 'search-indexer', 'database-pool']

        summaries = []
        for sname in service_names:
            healthy_cnt = db.query(OperationalMetric).filter(
                OperationalMetric.source_service == sname,
                OperationalMetric.status == 'HEALTHY'
            ).count()

            warning_cnt = db.query(OperationalMetric).filter(
                OperationalMetric.source_service == sname,
                OperationalMetric.status == 'WARNING'
            ).count()

            critical_cnt = db.query(OperationalMetric).filter(
                OperationalMetric.source_service == sname,
                OperationalMetric.status == 'CRITICAL'
            ).count()

            # Latency average for p99_latency_ms
            avg_lat = db.query(func.avg(OperationalMetric.metric_value)).filter(
                OperationalMetric.source_service == sname,
                OperationalMetric.metric_name == 'p99_latency_ms'
            ).scalar()

            if avg_lat is None:
                avg_lat = db.query(func.avg(OperationalMetric.metric_value)).filter(
                    OperationalMetric.source_service == sname
                ).scalar() or 0.0

            summaries.append({
                "sourceService": sname,
                "healthyCount": healthy_cnt,
                "warningCount": warning_cnt,
                "criticalCount": critical_cnt,
                "avgLatencyMs": round(float(avg_lat), 2)
            })

        redis_service.set_cached(cache_key, summaries)
        return summaries
    finally:
        db.close()

@query.field("getMetricHistory")
def resolve_get_metric_history(parent, info, service, metricName, minutes=60):
    cache_key = redis_service.generate_cache_key("getMetricHistory", {"service": service, "metricName": metricName, "minutes": minutes})
    cached = redis_service.get_cached(cache_key)
    if cached is not None:
        return cached

    db = database.SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        metrics = db.query(OperationalMetric).filter(
            OperationalMetric.source_service == service,
            OperationalMetric.metric_name == metricName,
            OperationalMetric.created_at >= since
        ).order_by(OperationalMetric.created_at.asc()).all()

        result = [m.to_dict() for m in metrics]
        redis_service.set_cached(cache_key, result)
        return result
    finally:
        db.close()

@query.field("diagnoseAnomaly")
def resolve_diagnose_anomaly(parent, info, service, metricName):
    db = database.SessionLocal()
    try:
        latest = db.query(OperationalMetric).filter(
            OperationalMetric.source_service == service,
            OperationalMetric.metric_name == metricName
        ).order_by(OperationalMetric.created_at.desc()).first()

        recent = db.query(OperationalMetric).filter(
            OperationalMetric.source_service == service,
            OperationalMetric.metric_name == metricName
        ).order_by(OperationalMetric.created_at.desc()).limit(10).all()

        recent_dicts = [r.to_dict() for r in recent]

        detected_val = latest.metric_value if latest else 250.0
        thresh_limit = latest.threshold_limit if latest else 100.0
        status_val = latest.status if latest else 'CRITICAL'

        insight = ai_agent_service.analyze_anomaly(
            service=service,
            metric_name=metricName,
            detected_value=detected_val,
            threshold_limit=thresh_limit,
            status=status_val,
            recent_history=recent_dicts
        )
        return insight
    finally:
        db.close()
