import unittest

from rules import ROUTINE_FIELDS, SAFETY_TYPES, decide


class GuestSupportPolicyTests(unittest.TestCase):
    def test_safety_takes_precedence_over_routine_and_does_not_read_bookings(self):
        for intent in SAFETY_TYPES:
            with self.subTest(intent=intent):
                decision = decide(("refund", intent), "HMTEST1234")
                self.assertEqual(decision.action, "escalate")
                self.assertEqual(decision.booking_fields, ())

    def test_uncertain_missing_and_unknown_fail_closed(self):
        self.assertEqual(decide(("wifi",), None).action, "escalate")
        self.assertEqual(decide(("wifi",), "INVALID").action, "escalate")
        self.assertEqual(decide(("wifi",), "HMTEST1234", uncertain=True).action, "escalate")
        self.assertEqual(decide(("wifi",), "HMTEST1234", conflicting_booking=True).action, "escalate")
        self.assertEqual(decide(("unknown",), "HMTEST1234").action, "escalate")

    def test_routine_uses_only_predefined_read_only_fields(self):
        for intent, allowed in ROUTINE_FIELDS.items():
            with self.subTest(intent=intent):
                decision = decide((intent,), "HMTEST1234")
                self.assertEqual(decision.action, "auto_answer")
                self.assertEqual(decision.booking_fields, allowed)


if __name__ == "__main__":
    unittest.main()
