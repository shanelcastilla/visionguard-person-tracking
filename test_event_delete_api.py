import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.event import router


class DeleteEventApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    @patch("app.api.event.delete_event", return_value=True)
    def test_delete_event_returns_deleted_id(self, delete_event):
        response = self.client.delete("/events/42")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"message": "Evento eliminado correctamente", "id": 42},
        )
        delete_event.assert_called_once_with(42)

    @patch("app.api.event.delete_event", return_value=False)
    def test_delete_missing_event_returns_not_found(self, delete_event):
        response = self.client.delete("/events/42")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Evento no encontrado")
        delete_event.assert_called_once_with(42)


if __name__ == "__main__":
    unittest.main()
