import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://datapulse:datapulse_pass@localhost:5432/datapulse_db"
    )
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    PORT = int(os.getenv("PORT", 5000))
    REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", 10))
