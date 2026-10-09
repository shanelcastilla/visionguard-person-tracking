from fastapi import APIRouter

from app.repositories.detection_event_repository import get_dashboard_summary
from app.services.camera_service import camera_service


router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard/summary")
def read_dashboard_summary():
    return {
        **get_dashboard_summary(),
        "camera": camera_service.get_status(),
    }
