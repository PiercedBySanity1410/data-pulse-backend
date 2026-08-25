import sys
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.redis_service import redis_service
from database import Base
import database
from ariadne import graphql_sync
from app import schema

def test_cache_key_generation():
    key1 = redis_service.generate_cache_key("getMetrics", {"service": "auth-service", "limit": 10})
    key2 = redis_service.generate_cache_key("getMetrics", {"limit": 10, "service": "auth-service"})
    key3 = redis_service.generate_cache_key("getMetrics", {"service": "payment-gateway", "limit": 10})

    # Arg order shouldn't change hash
    assert key1 == key2
    # Different args yield different hash
    assert key1 != key3

def test_caching_behavior(monkeypatch):
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)

    ingest_query = """
    mutation {
        ingestMetric(input: {
            sourceService: "search-indexer",
            metricName: "memory_usage_mb",
            metricValue: 1200.0,
            thresholdLimit: 2000.0
        }) {
            id
        }
    }
    """
    graphql_sync(schema, {"query": ingest_query})

    query = """
    query {
        getMetrics(service: "search-indexer") {
            sourceService
            metricValue
        }
    }
    """

    start_time = time.time()
    success1, result1 = graphql_sync(schema, {"query": query})
    duration1_ms = (time.time() - start_time) * 1000

    start_time = time.time()
    success2, result2 = graphql_sync(schema, {"query": query})
    duration2_ms = (time.time() - start_time) * 1000

    assert success1 and success2
    assert result1 == result2
    # Second fetch should be fast
    assert duration2_ms < 50.0
