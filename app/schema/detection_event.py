from datetime import datetime

from pydantic import BaseModel


class DetectionEventResponse(BaseModel):

    id: int
    track_id: int
    entry_time: datetime
    exit_time: datetime | None
    duration_seconds: int | None
    confidence: float
    image_path: str
    created_at: datetime
    evidence_url: str | None = None