import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_root_endpoint(client):
    res_get = client.get('/')
    assert res_get.status_code == 200
    assert res_get.json == {"status": "ok", "service": "DataPulse API"}

    res_head = client.head('/')
    assert res_head.status_code == 200

def test_cors_headers_on_health(client):
    res = client.get('/health', headers={'Origin': 'https://data-pulse-frontend-gamma.vercel.app'})
    assert res.status_code == 200
    assert res.headers.get('Access-Control-Allow-Origin') == '*'

def test_cors_options_preflight(client):
    res = client.options('/events', headers={
        'Origin': 'https://data-pulse-frontend-gamma.vercel.app',
        'Access-Control-Request-Method': 'GET'
    })
    assert res.status_code == 200
    assert res.headers.get('Access-Control-Allow-Origin') == '*'

def test_events_sse_headers(client):
    res = client.get('/events', headers={'Origin': 'https://data-pulse-frontend-gamma.vercel.app'})
    assert res.status_code == 200
    assert res.headers.get('Content-Type') == 'text/event-stream'
    assert res.headers.get('Access-Control-Allow-Origin') == '*'
    assert res.headers.get('X-Accel-Buffering') == 'no'

def test_events_sse_data_stream(client):
    res = client.get('/events')
    assert res.status_code == 200
    # Read initial chunk of SSE stream
    chunk = next(res.response)
    assert b": ping" in chunk or b"data:" in chunk

