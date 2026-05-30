import json
import os
from typing import Any
from urllib.request import Request, urlopen


def status() -> dict[str, Any]:
    endpoint = os.getenv("MERITRANK_LLM_ENDPOINT", "").strip()
    model = os.getenv("MERITRANK_LLM_MODEL", "").strip()
    return {
        "enabled": bool(endpoint and model),
        "mode": "llm" if endpoint and model else "evidence",
        "model": model or None,
        "notice": (
            "LLM analysis is enabled. Resume text and job description are sent to the "
            "configured model endpoint."
            if endpoint and model
            else "Running local evidence analysis. Configure MERITRANK_LLM_ENDPOINT and "
            "MERITRANK_LLM_MODEL to enable a background LLM reviewer."
        ),
    }


def analyze(job: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any] | None:
    config = status()
    if not config["enabled"]:
        return None
    endpoint = os.environ["MERITRANK_LLM_ENDPOINT"]
    api_key = os.getenv("MERITRANK_LLM_API_KEY", "")
    prompt = f"""Review this resume against the real job description. Use only evidence in
the supplied text. Do not invent experience. Return strict JSON with keys:
summary (string), strengths (array of strings), gaps (array of strings),
improvements (array of strings), interview_questions (array of strings).

Company: {job.get("company", "")}
Source URL: {job.get("source_url", "")}
Job title: {job["title"]}
Job description:
{job["description"]}

Resume:
{candidate["summary"]}
"""
    body = json.dumps({
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "You are an evidence-grounded resume reviewer. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read())
        content = payload["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as error:
        return {"error": f"Configured LLM analysis failed: {error}"}

