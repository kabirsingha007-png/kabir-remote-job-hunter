
import os
import re
import streamlit as st
from openai import OpenAI


# Relevant job families
ROLE_TERMS = [
    "employee benefits",
    "global employee benefits",
    "international employee benefits",
    "employee benefits consultant",
    "employee benefits advisor",
    "employee benefits specialist",
    "employee benefits manager",
    "global benefits",
    "international benefits",
    "benefits consultant",
    "benefits advisor",
    "benefits specialist",
    "benefits manager",
    "compensation and benefits",
    "compensation & benefits",
    "total rewards",
    "global mobility",
    "international health insurance",
    "international private medical insurance",
    "ipmi",
    "health insurance consultant",
    "health benefits",
    "benefits broker",
    "benefits brokerage",
]

# Exclude unrelated technical job families
TECH_EXCLUSIONS = [
    "software engineer",
    "software developer",
    "frontend developer",
    "front end developer",
    "backend developer",
    "back end developer",
    "full stack developer",
    "data engineer",
    "devops engineer",
    "cloud engineer",
    "machine learning engineer",
    "mobile app developer",
    "web developer",
    "python developer",
    "java developer",
    "qa engineer",
    "automation tester",
]

PART_TIME_TERMS = [
    "part-time", "part time", "fractional"
]

CONTRACT_TERMS = [
    "contract", "contractor", "freelance",
    "freelancer", "consultant on contract"
]

FULL_TIME_TERMS = [
    "full-time", "full time", "permanent"
]

FIXED_TERM_TERMS = [
    "fixed-term", "fixed term", "temporary",
    "interim"
]

INTERNSHIP_TERMS = [
    "internship", "intern"
]


def _text(value):
    """Safely convert values to lowercase text."""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return str(value or "").lower()


def employment_details(job):
    """Identify employment type and priority without guessing."""
    title = _text(job.get("title"))
    description = _text(job.get("description"))
    supplied_type = _text(
        job.get("employment_type")
        or job.get("job_type")
        or job.get("type")
    )

    text = title + " " + supplied_type + " " + description[:2500]

    if any(term in text for term in PART_TIME_TERMS):
        employment_type = "Part-time"
        priority = "High priority"

    elif any(term in text for term in CONTRACT_TERMS):
        employment_type = "Contract / Freelance"
        priority = "High priority"

    elif any(term in text for term in INTERNSHIP_TERMS):
        employment_type = "Internship"
        priority = "Lower priority"

    elif any(term in text for term in FIXED_TERM_TERMS):
        employment_type = "Fixed-term / Temporary"
        priority = "Lower priority"

    elif any(term in text for term in FULL_TIME_TERMS):
        employment_type = "Full-time"
        priority = "Lower priority"

    else:
        employment_type = "Not specified"
        priority = "Verify"

    return {
        "employment_type": employment_type,
        "priority": priority,
    }


def currency_details(job):
    """Detect explicitly mentioned salary currencies."""
    text = (
        _text(job.get("title")) + " " +
        _text(job.get("description")) + " " +
        _text(job.get("salary"))
    )

    currencies = []

    if re.search(r"\bGBP\b|£", text):
        currencies.append("GBP")

    if re.search(r"\bUSD\b|\$", text):
        currencies.append("USD")

    if re.search(r"\bEUR\b|€", text):
        currencies.append("EUR")

    return ", ".join(currencies) if currencies else "Not specified"


def india_eligibility(job):
    """Identify India eligibility only when there is supporting wording."""
    text = (
        _text(job.get("location")) + " " +
        _text(job.get("description")) + " " +
        _text(job.get("title"))
    )

    positive_phrases = [
        "india",
        "based in india",
        "based anywhere",
        "work from anywhere",
        "worldwide",
        "any country",
        "any location",
        "global remote",
        "remote worldwide",
        "open globally",
    ]

    negative_phrases = [
        "us only",
        "united states only",
        "uk only",
        "europe only",
        "must be based in the us",
        "must reside in the uk",
        "not available in india",
    ]

    if any(term in text for term in negative_phrases):
        return "India eligibility not indicated"

    if any(term in text for term in positive_phrases):
        return "Potentially eligible - verify"

    return "Not confirmed - verify"


def is_relevant_role(job):
    """Check whether a job genuinely belongs to the target job families."""
    title = _text(job.get("title"))
    description = _text(job.get("description"))

    # Titles carry more weight than incidental description mentions.
    if any(term in title for term in TECH_EXCLUSIONS):
        return False

    title_match = any(term in title for term in ROLE_TERMS)

    description_match = any(
        term in description for term in ROLE_TERMS
    )

    # A benefits-related title is strongest evidence.
    if title_match:
        return True

    # Description-only matches need more than one benefits signal.
    signals = sum(
        1 for term in ROLE_TERMS if term in description
    )

    return description_match and signals >= 2


def score_job(job, profile):
    """Calculate a targeted match score from 0 to 100."""
    title = _text(job.get("title"))
    description = _text(job.get("description"))
    location = _text(job.get("location"))

    if not is_relevant_role(job):
        return 0

    score = 45

    # Stronger score for a direct title match.
    if any(term in title for term in ROLE_TERMS):
        score += 25

    # Relevant professional background.
    background = _text(profile.get("background"))
    background_terms = [
        "insurance",
        "employee benefits",
        "global benefits",
        "compensation",
        "total rewards",
        "ipmi",
        "health insurance",
        "global mobility",
    ]

    background_matches = sum(
        1 for term in background_terms
        if term in background and term in (title + " " + description)
    )

    score += min(background_matches * 3, 15)

    # Part-time and contract roles receive priority.
    employment = employment_details(job)["employment_type"]

    if employment in ["Part-time", "Contract / Freelance"]:
        score += 10

    # Remote evidence.
    remote_text = title + " " + description + " " + location

    if any(term in remote_text for term in [
        "remote",
        "work from anywhere",
        "distributed",
        "fully remote",
    ]):
        score += 5

    return min(100, max(0, round(score)))


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
            return (
                "Keyword-based assessment. Add an OpenAI API key "
                "to enable AI assessments."
            )

        client = OpenAI(api_key=api_key)

        employment = employment_details(job)
        currency = currency_details(job)
        eligibility = india_eligibility(job)

        prompt = f"""
Assess this job against the candidate profile.

Candidate profile:
{profile}

Job title: {job.get('title', 'Not provided')}
Company: {job.get('company', 'Not provided')}
Location: {job.get('location', 'Not provided')}
Employment type: {employment['employment_type']}
Employment priority: {employment['priority']}
Salary currency: {currency}
India eligibility: {eligibility}

Description:
{str(job.get('description', ''))[:4000]}

Explain:
1. Relevance to employee benefits, global benefits,
   compensation and benefits, total rewards or IPMI.
2. Relevant candidate experience.
3. Whether part-time or contract work is available.
4. Whether the role is remote and accepts applicants in India.
5. Salary currency, if explicitly disclosed.

Do not invent missing information.
Clearly identify anything that needs verification.
Keep the assessment concise.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=220,
        )

        return response.choices[0].message.content.strip()

    except Exception:
        return (
            "AI assessment unavailable. "
            "Keyword-based score is still available."
        )
