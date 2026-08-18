import unittest

from src.orchestrator import parse_route


class RouterParsingTests(unittest.TestCase):
    def test_parses_plain_json(self):
        result = parse_route(
            '{"action":"route","domains":["sales"],"clarification":""}'
        )
        self.assertEqual(["sales"], result["domains"])

    def test_parses_fenced_json(self):
        result = parse_route(
            '```json\n{"action":"clarify","domains":[],'
            '"clarification":"Which domain?"}\n```'
        )
        self.assertEqual("clarify", result["action"])

    def test_rejects_unknown_action(self):
        with self.assertRaises(ValueError):
            parse_route('{"action":"answer","domains":[]}')


if __name__ == "__main__":
    unittest.main()
