import os
import unittest
from unittest.mock import patch

from talent_ranker.ai_analyzer import status


class AiAnalyzerTest(unittest.TestCase):
    def test_status_discloses_evidence_mode_without_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = status()
        self.assertFalse(result["enabled"])
        self.assertEqual("evidence", result["mode"])


if __name__ == "__main__":
    unittest.main()

