from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs

import requests

from duifene.api import DuifeneApi
from duifene.models import CheckInActivity, Course, Outcome
from duifene.processor import ActivityProcessor
from duifene.rate_limit import RateLimiter
from duifene.settings import Settings


class FakeResponse:
    status_code = 200
    text = '{"msgbox": "签到成功"}'

    def json(self) -> dict[str, str]:
        return {"msgbox": "签到成功"}


class CapturingSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        return FakeResponse()


class LocationSignInTests(unittest.TestCase):
    def test_sign_by_location_includes_course_and_class_ids(self) -> None:
        settings = Settings()
        session = CapturingSession()
        api = DuifeneApi(session, settings, RateLimiter(settings))
        api._user_id = "7577411"
        course = Course("300331", "507258", "马克思主义基本原理")

        with patch("duifene.api.random.uniform", return_value=0.0):
            api.sign_by_location(course, 114.12345678, 22.87654321)

        request = session.requests[0]
        self.assertEqual(
            request["url"],
            "https://www.duifene.com/_CheckIn/CheckInRoomHandler.ashx",
        )
        self.assertEqual(
            parse_qs(str(request["data"])),
            {
                "action": ["signin"],
                "cid": ["300331"],
                "tcid": ["507258"],
                "sid": ["7577411"],
                "latitude": ["22.87654321"],
                "longitude": ["114.12345678"],
            },
        )
        self.assertEqual(
            request["headers"]["X-Requested-With"],  # type: ignore[index]
            "XMLHttpRequest",
        )

    def test_processor_passes_course_to_location_sign_in(self) -> None:
        class FakeLimiter:
            @staticmethod
            def is_blocking() -> bool:
                return False

        class FakeApi:
            limiter = FakeLimiter()

            def __init__(self) -> None:
                self.location_calls: list[tuple[Course, float, float]] = []

            @staticmethod
            def fetch_headcount(activity_id: str) -> tuple[int, int]:
                return 11, 50

            def sign_by_location(
                self, course: Course, longitude: float, latitude: float
            ) -> str:
                self.location_calls.append((course, longitude, latitude))
                return "签到成功"

        class FakePush:
            subscribed_id = None

            @staticmethod
            def subscribe(activity_id: str) -> bool:
                return True

            @staticmethod
            def take_follow_point() -> tuple[float, float, float]:
                return 114.5, 22.5, 3.0

            @staticmethod
            def stop() -> None:
                pass

        class UnusedResolver:
            @staticmethod
            def resolve(course: Course) -> None:
                return None

        class FakeStore:
            @staticmethod
            def save_center(
                class_id: str, longitude: float, latitude: float
            ) -> None:
                pass

        settings = Settings()
        now = datetime.now()
        course = Course("300331", "507258", "马克思主义基本原理")
        activity = CheckInActivity.from_raw(
            {
                "ID": "2551457",
                "CheckInType": "3",
                "CanApply": "1",
                "StatusID": "2",
                "StatusName": "缺勤",
                "CreaterDate": now.strftime("%Y/%m/%d %H:%M:%S"),
                "ApplyLimitDate": (now + timedelta(days=1, minutes=10)).strftime(
                    "%Y/%m/%d %H:%M:%S"
                ),
            }
        )
        api = FakeApi()
        processor = ActivityProcessor(
            settings,
            api,  # type: ignore[arg-type]
            FakePush(),  # type: ignore[arg-type]
            UnusedResolver(),  # type: ignore[arg-type]
            FakeStore(),  # type: ignore[arg-type]
            lambda message: None,
        )

        outcome = processor.process(activity, course)

        self.assertIs(outcome, Outcome.SIGNED)
        self.assertEqual(api.location_calls, [(course, 114.5, 22.5)])


if __name__ == "__main__":
    unittest.main()
