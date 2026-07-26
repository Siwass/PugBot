import unittest
from datetime import date, datetime, time
from unittest.mock import patch

from handlers.post.schedule_service import (
    SCHEDULE_INPUT_FULL,
    SCHEDULE_INPUT_TIME_ONLY,
    combine_publish_at,
    parse_manual_publish_at,
    schedule_date_from_offset,
    validate_future_publish_at,
)


class ScheduleServiceTests(unittest.TestCase):
    def test_schedule_date_from_offset(self):
        fixed_now = datetime(2026, 7, 24, 10, 0)

        with patch(
            "handlers.post.schedule_service.get_local_now",
            return_value=fixed_now,
        ):
            self.assertEqual(
                schedule_date_from_offset(0),
                date(2026, 7, 24),
            )
            self.assertEqual(
                schedule_date_from_offset(2),
                date(2026, 7, 26),
            )

    def test_combine_publish_at(self):
        result = combine_publish_at(
            date(2026, 7, 24),
            time(18, 30),
        )
        self.assertEqual(result, datetime(2026, 7, 24, 18, 30))

    def test_parse_manual_publish_at_full(self):
        result = parse_manual_publish_at(
            "24.07.2026 18:30",
            selected_date=None,
            input_mode=SCHEDULE_INPUT_FULL,
        )
        self.assertEqual(result, datetime(2026, 7, 24, 18, 30))

    def test_parse_manual_publish_at_time_only(self):
        result = parse_manual_publish_at(
            "18:30",
            selected_date=date(2026, 7, 24),
            input_mode=SCHEDULE_INPUT_TIME_ONLY,
        )
        self.assertEqual(result, datetime(2026, 7, 24, 18, 30))

    def test_parse_manual_publish_at_invalid(self):
        self.assertIsNone(
            parse_manual_publish_at(
                "not-a-date",
                selected_date=None,
                input_mode=SCHEDULE_INPUT_FULL,
            )
        )
        self.assertIsNone(
            parse_manual_publish_at(
                "25:99",
                selected_date=date(2026, 7, 24),
                input_mode=SCHEDULE_INPUT_TIME_ONLY,
            )
        )

    def test_validate_future_publish_at(self):
        fixed_now = datetime(2026, 7, 24, 18, 0)

        with patch(
            "handlers.post.schedule_service.get_local_now",
            return_value=fixed_now,
        ):
            self.assertTrue(
                validate_future_publish_at(datetime(2026, 7, 24, 18, 1))
            )
            self.assertFalse(
                validate_future_publish_at(datetime(2026, 7, 24, 18, 0))
            )
            self.assertFalse(
                validate_future_publish_at(datetime(2026, 7, 24, 17, 59))
            )


if __name__ == "__main__":
    unittest.main()
