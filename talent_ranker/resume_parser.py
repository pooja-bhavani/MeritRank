import base64
import os
import re
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from .text import ATS_KEYWORDS, SKILL_ALIASES, normalize_skill

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d() .-]{8,}\d)")
YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)", re.IGNORECASE)
ROLE_WORDS = (
    "engineer", "developer", "architect", "scientist", "analyst", "manager",
    "consultant", "specialist", "administrator", "designer", "lead", "intern",
)
COMMON_SKILLS = {
    *ATS_KEYWORDS,
    *SKILL_ALIASES.keys(),
    *SKILL_ALIASES.values(),
    "ansible", "azure", "bash", "c", "c++", "css", "django", "flask", "git",
    "github actions", "gitlab", "grafana", "html", "java", "javascript",
    "jenkins", "linux", "mongodb", "mysql", "node.js", "numpy", "pandas",
    "prometheus", "pytorch", "redis", "rest api", "scikit-learn", "spark",
    "spring boot", "terraform", "typescript",
}
ROOT = Path(__file__).resolve().parent.parent
PDF_EXTRACT_SOURCE = ROOT / "scripts" / "pdf_extract.swift"
PDF_EXTRACT_BINARY = Path("/private/tmp/meritrank-pdf-extract")


def parse_resume(filename: str, content_base64: str) -> dict[str, object]:
    data = base64.b64decode(content_base64, validate=True)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise ValueError("Resume upload supports PDF, TXT, and MD files")
    text = _extract_text(data, suffix)
    if len(text.strip()) < 40:
        raise ValueError(
            "Could not extract enough text from this resume. If it is a scanned PDF, "
            "run OCR first or upload a TXT version."
        )
    return _candidate_from_text(filename, text)


def _extract_text(data: bytes, suffix: str) -> str:
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"resume-{uuid4().hex}.pdf"
        path.write_bytes(data)
        cache_root = Path("/private/tmp/meritrank-pdfkit-cache")
        cache_root.mkdir(exist_ok=True)
        environment = dict(os.environ)
        environment["CLANG_MODULE_CACHE_PATH"] = str(cache_root / "clang")
        environment["SWIFT_MODULECACHE_PATH"] = str(cache_root / "swift")
        binary = _pdf_extract_binary(environment)
        for command in (
            [str(binary), str(path)] if binary else [],
            ["/usr/bin/mdls", "-raw", "-name", "kMDItemTextContent", str(path)],
            ["/usr/bin/textutil", "-convert", "txt", "-stdout", str(path)],
        ):
            if not command:
                continue
            try:
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=15, env=environment
                )
            except subprocess.TimeoutExpired:
                continue
            text = result.stdout.strip()
            if result.returncode == 0 and text not in {"", "(null)"} and len(text) >= 40:
                return text
    return ""


def _pdf_extract_binary(environment: dict[str, str]) -> Path | None:
    if PDF_EXTRACT_BINARY.exists():
        return PDF_EXTRACT_BINARY
    try:
        subprocess.run(
            ["/usr/bin/swiftc", str(PDF_EXTRACT_SOURCE), "-o", str(PDF_EXTRACT_BINARY)],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
            env=environment,
        )
        return PDF_EXTRACT_BINARY
    except (OSError, subprocess.SubprocessError):
        return None


def _candidate_from_text(filename: str, text: str) -> dict[str, object]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    lowered = text.lower()
    skills = sorted({
        normalize_skill(skill)
        for skill in COMMON_SKILLS
        if re.search(rf"(?<![\w+#.-]){re.escape(skill.lower())}(?![\w+#.-])", lowered)
    })
    roles = []
    for line in lines:
        if any(word in line.lower() for word in ROLE_WORDS) and len(line) <= 100:
            roles.append(line)
        if len(roles) == 4:
            break
    year_matches = [float(value) for value in YEARS_RE.findall(text)]
    return {
        "candidate_id": f"RES-{uuid4().hex[:8].upper()}",
        "name": lines[0][:100] if lines else Path(filename).stem,
        "email": _first_match(EMAIL_RE, text),
        "phone": _first_match(PHONE_RE, text),
        "headline": roles[0] if roles else (lines[1][:160] if len(lines) > 1 else ""),
        "summary": text[:5000],
        "skills": skills,
        "roles": roles,
        "years_experience": max(year_matches, default=0),
        "location": "",
        "open_to_remote": False,
        "activity": {
            "profile_completeness": 0.75,
            "response_rate": 0.5,
            "active_days_ago": 30,
        },
        "source_file": filename,
        "parser_notice": (
            "Resume text was extracted locally. Review detected fields before using "
            "the shortlist for a hiring decision."
        ),
    }


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""
