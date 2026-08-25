import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Base
import database
from ariadne import graphql_sync
from app import schema

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    # Use SQLite in-memory for fast unit testing
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)
    yield

def test_ingest_metric_mutation():
    mutation = """
    mutation {
        ingestMetric(input: {
            sourceService: "auth-service",
            metricName: "p99_latency_ms",
            metricValue: 350.0,
            thresholdLimit: 200.0,
            payload: "{\\"host\\": \\"node-1\\"}"
        }) {
            id
            sourceService
            metricName
            metricValue
            thresholdLimit
            status
        }
    }
    """
    success, result = graphql_sync(schema, {"query": mutation})
    assert success
    assert "data" in result
    data = result["data"]["ingestMetric"]
    assert data["sourceService"] == "auth-service"
    assert data["metricName"] == "p99_latency_ms"
    assert data["status"] == "CRITICAL"

def test_get_metrics_query():
    # Ingest metric first
    ingest_query = """
    mutation {
        ingestMetric(input: {
            sourceService: "payment-gateway",
            metricName: "cpu_utilization_pct",
            metricValue: 50.0,
            thresholdLimit: 80.0
        }) {
            id
        }
    }
    """
    graphql_sync(schema, {"query": ingest_query})

    query = """
    query {
        getMetrics(service: "payment-gateway") {
            sourceService
            metricName
            metricValue
            status
        }
    }
    """
    success, result = graphql_sync(schema, {"query": query})
    assert success
    assert len(result["data"]["getMetrics"]) >= 1
    assert result["data"]["getMetrics"][0]["sourceService"] == "payment-gateway"

def test_diagnose_anomaly_query():
    query = """
    query {
        diagnoseAnomaly(service: "auth-service", metricName: "p99_latency_ms") {
            service
            metric
            detectedValue
            severity
            rootCauseAnalysis
            suggestedMitigation
        }
    }
    """
    success, result = graphql_sync(schema, {"query": query})
    assert success
    data = result["data"]["diagnoseAnomaly"]
    assert data["service"] == "auth-service"
    assert "rootCauseAnalysis" in data
    assert "suggestedMitigation" in data
