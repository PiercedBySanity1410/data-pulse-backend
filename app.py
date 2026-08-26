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
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"[DataPulse API Error] Unhandled Exception: {e}")
    response = jsonify({
        "error": "Internal Server Error",
        "message": str(e)
    })
    response.status_code = 500
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

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

@app.route("/health", methods=["GET", "OPTIONS"])
def health_check():
    if request.method == "OPTIONS":
        return Response(status=200)
    db_status = "healthy"
    try:
        db = SessionLocal()
        try:
            db.query(OperationalMetric).first()
        finally:
            db.close()
    except Exception as e:
        db_status = f"unhealthy ({e})"

    redis_status = "healthy" if redis_service.redis_client and redis_service.redis_client.ping() else "offline/degraded"

    return jsonify({
        "status": "online",
        "service": "DataPulse Operations API",
        "database": db_status,
        "redis": redis_status,
        "timestamp": time.time()
    }), 200

@app.route("/graphql", methods=["GET", "OPTIONS"])
def graphql_explorer():
    if request.method == "OPTIONS":
        return Response(status=200)
    return explorer.ExplorerGraphiQL().html(None), 200

@app.route("/graphql", methods=["POST", "OPTIONS"])
def graphql_server():
    if request.method == "OPTIONS":
        return Response(status=200)
    data = request.get_json()
    success, result = graphql_sync(
        schema,
        data,
        context_value={"request": request},
        debug=app.debug
    )
    status_code = 200 if success else 400
    return jsonify(result), status_code

@app.route("/events", methods=["GET", "OPTIONS"])
def sse_events():
    if request.method == "OPTIONS":
        res = Response(status=200)
        res.headers["Access-Control-Allow-Origin"] = "*"
        res.headers["Access-Control-Allow-Headers"] = "*"
        res.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        return res

    def event_stream():
        # Send initial SSE keepalive comment to flush headers and establish stream immediately
        yield ": ping\n\n"

        last_id = None
        redis_failed = False

        # Attempt Redis PubSub streaming if client is available
        if redis_service.redis_client and not redis_failed:
            try:
                pubsub = redis_service.redis_client.pubsub()
                pubsub.subscribe("telemetry:stream")
                for message in pubsub.listen():
                    if message and message.get("type") == "message":
                        data = message.get("data")
                        yield f"data: {data}\n\n"
            except GeneratorExit:
                return
            except Exception as e:
                print(f"[SSE Error] Redis pubsub failed: {e}. Falling back to DB polling.")
                redis_failed = True

        # Database polling fallback loop
        last_ping = time.time()
        while True:
            try:
                db = SessionLocal()
                try:
                    q = db.query(OperationalMetric).order_by(OperationalMetric.created_at.desc())
                    latest = q.first()
                    if latest and str(latest.id) != last_id:
                        last_id = str(latest.id)
                        yield f"data: {json.dumps(latest.to_dict())}\n\n"
                finally:
                    db.close()
            except GeneratorExit:
                return
            except Exception as db_err:
                print(f"[SSE DB Warning] {db_err}")

            # Send keepalive ping comment every 15s to keep proxy connection alive
            if time.time() - last_ping > 15:
                yield ": keepalive\n\n"
                last_ping = time.time()

            time.sleep(2.0)

    res = Response(event_stream(), content_type="text/event-stream")
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Cache-Control"] = "no-cache"
    res.headers["Connection"] = "keep-alive"
    res.headers["X-Accel-Buffering"] = "no"
    return res

if __name__ == "__main__":
    print(f"[DataPulse Backend] Starting server on port {Config.PORT}...")
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)

