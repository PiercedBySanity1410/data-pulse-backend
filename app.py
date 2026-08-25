import os
import json
import time
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from ariadne import load_schema_from_path, make_executable_schema, graphql_sync, explorer
from config import Config
from database import init_db, SessionLocal
from models import OperationalMetric
from resolvers import query, mutation, subscription
from services.redis_service import redis_service

app = Flask(__name__)
CORS(app)

# Load GraphQL Schema & Executable Schema
schema_path = os.path.join(os.path.dirname(__file__), "schema.graphql")
type_defs = load_schema_from_path(schema_path)
schema = make_executable_schema(type_defs, query, mutation, subscription)

# Auto-initialize database tables on app startup
try:
    init_db()
    print("[DataPulse API] Database tables initialized successfully.")
except Exception as e:
    print(f"[DataPulse API] Database init warning: {e}")

@app.route("/health", methods=["GET"])
def health_check():
    db_status = "healthy"
    db = SessionLocal()
    try:
        db.query(OperationalMetric).first()
    except Exception as e:
        db_status = f"unhealthy ({e})"
    finally:
        db.close()

    redis_status = "healthy" if redis_service.redis_client and redis_service.redis_client.ping() else "offline/degraded"

    return jsonify({
        "status": "online",
        "service": "DataPulse Operations API",
        "database": db_status,
        "redis": redis_status,
        "timestamp": time.time()
    }), 200

@app.route("/graphql", methods=["GET"])
def graphql_explorer():
    return explorer.ExplorerGraphiQL().html(None), 200

@app.route("/graphql", methods=["POST"])
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(
        schema,
        data,
        context_value={"request": request},
        debug=app.debug
    )
    status_code = 200 if success else 400
    return jsonify(result), status_code

@app.route("/events", methods=["GET"])
def sse_events():
    def event_stream():
        pubsub = redis_service.redis_client.pubsub() if redis_service.redis_client else None
        if pubsub:
            pubsub.subscribe("telemetry:stream")
            for message in pubsub.listen():
                if message and message.get("type") == "message":
                    data = message.get("data")
                    yield f"data: {data}\n\n"
        else:
            # Polling fallback if Redis pubsub is unavailable
            last_id = None
            while True:
                db = SessionLocal()
                try:
                    q = db.query(OperationalMetric).order_by(OperationalMetric.created_at.desc())
                    latest = q.first()
                    if latest and str(latest.id) != last_id:
                        last_id = str(latest.id)
                        yield f"data: {json.dumps(latest.to_dict())}\n\n"
                except Exception:
                    pass
                finally:
                    db.close()
                time.sleep(2.0)

    return Response(event_stream(), content_type="text/event-stream")

if __name__ == "__main__":
    print(f"[DataPulse Backend] Starting server on port {Config.PORT}...")
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
