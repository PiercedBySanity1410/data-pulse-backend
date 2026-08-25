from datetime import datetime, timezone

class AnomalyDiagnosticService:
    def analyze_anomaly(self, service: str, metric_name: str, detected_value: float, threshold_limit: float, status: str, recent_history: list = None) -> dict:
        now_iso = datetime.now(timezone.utc).isoformat()
        pct_exceeded = ((detected_value - threshold_limit) / threshold_limit * 100) if threshold_limit > 0 else 50.0

        rca_templates = {
            "p99_latency_ms": f"P99 latency spiked to {detected_value}ms ({pct_exceeded:.1f}% above SLA baseline of {threshold_limit}ms). Upstream database lock contention or thread pool exhaustion in '{service}'.",
            "cpu_utilization_pct": f"CPU usage reached {detected_value}% (threshold: {threshold_limit}%). Heavy execution loops or processing spike in '{service}'.",
            "error_rate": f"Error rate surged to {detected_value} errors/sec (threshold: {threshold_limit}). Cascading third-party gateway timeouts or unhandled database connection retries.",
            "memory_usage_mb": f"Memory footprint ballooned to {detected_value}MB (limit: {threshold_limit}MB). Potential memory leak or uncollected heap garbage in worker threads."
        }

        mitigation_templates = {
            "p99_latency_ms": "1. Flush hot query cache via Redis CLI. 2. Scale service instance replicas +2. 3. Inspect PostgreSQL slow query log.",
            "cpu_utilization_pct": "1. Auto-scale CPU quota or trigger HPA. 2. Apply rate limiting. 3. Profile active threads.",
            "error_rate": "1. Enable fallback mock responses. 2. Check downstream connectivity & API keys. 3. Restart container pod.",
            "memory_usage_mb": "1. Trigger heap dump. 2. Restart worker container process. 3. Increase container memory limits."
        }

        rca = rca_templates.get(
            metric_name,
            f"Metric '{metric_name}' in service '{service}' breached threshold limit ({detected_value} vs threshold {threshold_limit}). Anomalous resource usage detected."
        )

        mitigation = mitigation_templates.get(
            metric_name,
            "1. Check application logs. 2. Verify network connectivity. 3. Scale instances if load remains high."
        )

        return {
            "service": service,
            "metric": metric_name,
            "detectedValue": float(detected_value),
            "severity": status,
            "rootCauseAnalysis": rca,
            "suggestedMitigation": mitigation,
            "analyzedAt": now_iso
        }

ai_agent_service = AnomalyDiagnosticService()
