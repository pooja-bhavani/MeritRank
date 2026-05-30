import base64
import unittest

from talent_ranker.models import Candidate
from talent_ranker.resume_parser import parse_resume


class ResumeParserTest(unittest.TestCase):
    def test_text_resume_extracts_contact_skills_and_role(self) -> None:
        resume = """Riya Shah
Platform Engineer
riya@example.com
Built AWS and Kubernetes infrastructure using Terraform, Docker, and Python.
5 years of platform engineering experience.
"""
        candidate = parse_resume("riya-resume.txt", base64.b64encode(resume.encode()).decode())
        self.assertEqual("Riya Shah", candidate["name"])
        self.assertEqual("riya@example.com", candidate["email"])
        self.assertIn("aws", candidate["skills"])
        self.assertIn("kubernetes", candidate["skills"])
        self.assertEqual(5, candidate["years_experience"])
        self.assertEqual("Riya Shah", Candidate.from_dict(candidate).name)

    def test_scanned_or_empty_resume_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Could not extract enough text"):
            parse_resume("empty.txt", base64.b64encode(b"short").decode())


if __name__ == "__main__":
    unittest.main()
