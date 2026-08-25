import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base

class OperationalMetric(Base):
    __tablename__ = 'operational_metrics'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_service = Column(String(100), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    threshold_limit = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='HEALTHY', index=True)
    payload = Column(JSON, nullable=True, default={})
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    __table_args__ = (
        Index(
            'idx_metrics_lookup',
            'source_service',
            'metric_name',
            created_at.desc()
        ),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "sourceService": self.source_service,
            "metricName": self.metric_name,
            "metricValue": self.metric_value,
            "thresholdLimit": self.threshold_limit,
            "status": self.status,
            "payload": str(self.payload) if isinstance(self.payload, dict) else (self.payload or "{}"),
            "createdAt": self.created_at.isoformat() if self.created_at else datetime.now(timezone.utc).isoformat()
        }
