from datetime import date, datetime

from app.database import get_connection


def create_event(
    track_id: int,
    entry_time: datetime,
    confidence: float,
    image_path: str,
) -> int:

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO detection_events (
                    track_id,
                    entry_time,
                    confidence,
                    image_path
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    track_id,
                    entry_time,
                    confidence,
                    image_path,
                ),
            )

            event_id = cursor.fetchone()[0]

            connection.commit()

            return event_id

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


def close_event(
    event_id: int,
    exit_time: datetime,
    duration_seconds: int,
) -> None:

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE detection_events
                SET
                    exit_time = %s,
                    duration_seconds = %s
                WHERE id = %s;
                """,
                (
                    exit_time,
                    duration_seconds,
                    event_id,
                ),
            )

            connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()



def get_events():

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    track_id,
                    entry_time,
                    exit_time,
                    duration_seconds,
                    confidence,
                    image_path,
                    created_at
                FROM detection_events
                ORDER BY entry_time DESC;
                """
            )

            rows = cursor.fetchall()

            return rows

    finally:
        connection.close()


def get_event_by_id(event_id: int):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    track_id,
                    entry_time,
                    exit_time,
                    duration_seconds,
                    confidence,
                    image_path,
                    created_at
                FROM detection_events
                WHERE id = %s;
                """,
                (event_id,),
            )

            return cursor.fetchone()

    finally:
        connection.close()
        connection.close()

def delete_event(event_id: int) -> bool:
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM detection_events
                WHERE id = %s
                RETURNING id;
                """,
                (event_id,),
            )
            deleted = cursor.fetchone() is not None
            connection.commit()
            return deleted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_active_events():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    track_id,
                    entry_time,
                    exit_time,
                    duration_seconds,
                    confidence,
                    image_path,
                    created_at
                FROM detection_events
                WHERE exit_time IS NULL
                ORDER BY entry_time DESC;
                """
            )

            return cursor.fetchall()

    finally:
        connection.close()


def get_events_today():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    track_id,
                    entry_time,
                    exit_time,
                    duration_seconds,
                    confidence,
                    image_path,
                    created_at
                FROM detection_events
                WHERE entry_time >= CURRENT_DATE
                  AND entry_time < CURRENT_DATE + INTERVAL '1 day'
                ORDER BY entry_time DESC;
                """
            )

            return cursor.fetchall()

    finally:
        connection.close()




        
def get_events_filtered(
    min_confidence: float | None = None,
    track_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            conditions = []
            parameters = []

            if min_confidence is not None:
                conditions.append("confidence >= %s")
                parameters.append(min_confidence)

            if track_id is not None:
                conditions.append("track_id = %s")
                parameters.append(track_id)

            if start_date is not None:
                conditions.append("entry_time >= %s::date")
                parameters.append(start_date)

            if end_date is not None:
                conditions.append("entry_time < %s::date + INTERVAL '1 day'")
                parameters.append(end_date)

            where_clause = (
                f"WHERE {' AND '.join(conditions)}"
                if conditions
                else ""
            )
            query = f"""
                SELECT
                    id,
                    track_id,
                    entry_time,
                    exit_time,
                    duration_seconds,
                    confidence,
                    image_path,
                    created_at
                FROM detection_events
                {where_clause}
                ORDER BY entry_time DESC;
            """

            cursor.execute(
                query,
                parameters,
            )

            return cursor.fetchall()

    finally:
        connection.close()


def get_dashboard_summary() -> dict[str, int | float]:
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE entry_time >= CURRENT_DATE
                          AND entry_time < CURRENT_DATE + INTERVAL '1 day'
                    ) AS entries_today,
                    COUNT(*) FILTER (WHERE exit_time IS NULL) AS people_inside,
                    COALESCE(
                        AVG(duration_seconds) FILTER (
                            WHERE duration_seconds IS NOT NULL
                              AND entry_time >= CURRENT_DATE
                              AND entry_time < CURRENT_DATE + INTERVAL '1 day'
                        ),
                        0
                    ) AS average_duration_seconds
                FROM detection_events;
                """
            )
            entries_today, people_inside, average_duration = cursor.fetchone()

            return {
                "entries_today": entries_today,
                "people_inside": people_inside,
                "average_duration_seconds": round(float(average_duration)),
            }

    finally:
        connection.close()