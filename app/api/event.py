from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query

from ..repositories.detection_event_repository import (
    get_active_events,
    get_event_by_id,
    get_events,
    get_events_filtered,
    get_events_today,
    delete_event,
)
from ..schema.detection_event import DetectionEventResponse

EVIDENCE_DIRECTORY = Path(__file__).resolve().parents[2] / "events"


router = APIRouter(
    prefix="/events",
    tags=["Events"],
)


def _event_response(row):
    filename = Path(row[6]).name if row[6] else None
    evidence_url = (
        f"/evidence/{quote(filename)}"
        if filename and (EVIDENCE_DIRECTORY / filename).is_file()
        else None
    )

    return DetectionEventResponse(
        id=row[0],
        track_id=row[1],
        entry_time=row[2],
        exit_time=row[3],
        duration_seconds=row[4],
        confidence=float(row[5]),
        image_path=row[6],
        created_at=row[7],
        evidence_url=evidence_url,
    )


@router.get("/",response_model=list[DetectionEventResponse],)
def read_events():
    rows = get_events()
    return [_event_response(row) for row in rows]


@router.get("/active", response_model=list[DetectionEventResponse])
def read_active_events():
    rows = get_active_events()
    return [_event_response(row) for row in rows]


@router.get("/today", response_model=list[DetectionEventResponse])
def read_events_today():
    rows = get_events_today()
    return [_event_response(row) for row in rows]




@router.get(
    "/filtered",
    response_model=list[DetectionEventResponse],
)
def read_filtered_events(
    min_confidence: float | None = Query(
        default=None,
        ge=0,
        le=1,
        description="Confianza mínima entre 0 y 1. Ejemplo: 0.80 equivale al 80 %.",
    ),
    track_id: int | None = Query(default=None, ge=0),
    start_date: date | None = Query(
        default=None,
        description="Filtra desde esta fecha de entrada, inclusive (YYYY-MM-DD).",
    ),
    end_date: date | None = Query(
        default=None,
        description="Filtra hasta esta fecha de entrada, inclusive (YYYY-MM-DD).",
    ),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date no puede ser posterior a end_date",
        )

    rows = get_events_filtered(
        min_confidence=min_confidence,
        track_id=track_id,
        start_date=start_date,
        end_date=end_date,
    )
    return [_event_response(row) for row in rows]

@router.delete("/{event_id}")
def eliminar_evento(event_id: int):
    if not delete_event(event_id):
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return {"message": "Evento eliminado correctamente", "id": event_id}


@router.get("/{event_id}", response_model=DetectionEventResponse)
def buscar_evento(event_id: int):
    row = get_event_by_id(event_id)

    if row is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return _event_response(row)