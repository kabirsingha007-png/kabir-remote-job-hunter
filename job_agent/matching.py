import os
import re
import streamlit as st
from openai import OpenAI


def _normalize(text):
    """Convert text to lowercase words for matching."""
    return set(re.findall(r"[a-z0-9+#.]+", str(text or "").lower()))


def score_job(job, profile):
    """Calculate a keyword-based match score from 0 to 100."""
    title = str(job.get("title", ""))
    description = str(job.get("description", ""))
    location = str(job.get("location", ""))

    job_words = _normalize(title + " " + description)
    role_words = _normalize(" ".join(profile.get("roles", [])))
    background_words = _normalize(profile.get("background", ""))

    role_match = len(job_words & role_words) / max(len(role_words), 1)
    background_match = len(job_words & background_words) / max(len(background_words), 1)

    score = min(role_match * 55, 55) + min(background_match * 25, 25)

    if profile.get("remote_only"):
        remote_text = (title + " " + description + " " + location).lower()
        if any(term in remote_text for term in ["remote", "work from anywhere", "distributed"]):
            score += 10

    if profile.get("india_eligible"):
        india_text = (description + " " + location).lower()
        if any(term in india_text for term in ["india", "worldwide", "global", "anywhere", "apac"]):
            score += 10

    return max(0, min(100, round(score)))


def ai_explanation(job, profile):
    """Generate an optional AI assessment of a job match."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            try:
                api_key = st.secrets.get("OPENAI_API_KEY")
            except Exception:
                api_key = None

        if not api_key:
            return "Keyword-based match. Add an OpenAI API key to enable AI assessments."

        client = OpenAI(api_key=api_key)

        prompt = f"""
Assess this job opportunity against the candidate profile.

Candidate profile:
{profile}

Job title: {job.get('title', 'Not provided')}
Company: {job.get('company', 'Not provided')}
Location: {job.get('location', 'Not provided')}
Description: {str(job.get('description', ''))[:5000]}

In 3-4 concise sentences, explain:
1. Why the role matches or does not match.
2. Which experience is relevant.
3. Whether remote work and India eligibility need verification.

Do not invent missing information.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=180,
        )

        return response.choices[0].message.content.strip()

    except Exception as error:
        return f"AI assessment unavailable. Keyword-based score is still available."
