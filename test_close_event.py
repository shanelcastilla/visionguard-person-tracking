from datetime import datetime, timedelta, timezone

from app.repositories.detection_event_repository import (
    create_event,
    close_event,
)


def main():

    entry_time = datetime.now(timezone.utc)

    event_id = create_event(
        track_id=10,
        entry_time=entry_time,
        confidence=0.96,
        image_path="events/test_person.jpg",
    )

    print(f"🟢 Entrada creada. ID: {event_id}")

    exit_time = entry_time + timedelta(seconds=30)

    close_event(
        event_id=event_id,
        exit_time=exit_time,
        duration_seconds=30,
    )

    print("🔴 Salida registrada correctamente")


if __name__ == "__main__":
    main()