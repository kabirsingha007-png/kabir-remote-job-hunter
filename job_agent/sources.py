
import re
import requests
from html import unescape
from urllib.parse import quote_plus

HEADERS = {
    "User-Agent": "KabirRemoteJobHunter/1.0 (personal job discovery)",
    "Accept": "application/json",
}

TIMEOUT = 25

# Target professional roles
ROLE_SEARCH_TERMS = [
    "employee benefits",
    "global employee benefits",
    "international benefits",
    "employee benefits consultant",
    "employee benefits advisor",
    "global benefits manager",
    "compensation and benefits",
    "total rewards",
    "international health insurance",
    "IPMI",
    "health insurance consultant",
    "benefits broker",
]

# These are search destinations, not scraped feeds.
# They can be displayed in the app in a later app.py update.
SEARCH_PORTALS = {
    "LinkedIn": "https://www.linkedin.com/jobs/search/?keywords={query}&f_WT=2",
    "Indeed USA": "https://www.indeed.com/jobs?q={query}&fromage=14",
    "Indeed Canada": "https://ca.indeed.com/jobs?q={query}&fromage=14",
    "Indeed UK": "https://uk.indeed.com/jobs?q={query}&fromage=14",
    "Glassdoor": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}",
    "Google Jobs": "https://www.google.com/search?q={query}+remote+jobs",
    "Wellfound": "https://wellfound.com/jobs",
    "FlexJobs": "https://www.flexjobs.com/search?search={query}",
    "We Work Remotely": "https://weworkremotely.com/remote-jobs/search?term={query}",
    "Working Nomads": "https://www.workingnomads.com/jobs?search={query}",
}


def _request(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _clean_html(value):
    """Remove HTML tags and normalize text."""
    value = unescape(str(value or ""))
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _india_eligibility(location, description):
    """
    Conservative classification.
    A job is not marked India-eligible just because it says remote.
    """
    text = f"{location} {description}".lower()

    india_terms = [
        "india",
        "based in india",
        "located in india",
        "india only",
        "applicants in india",
        "candidates in india",
        "work from india",
    ]

    worldwide_terms = [
        "worldwide",
        "anywhere in the world",
        "anywhere globally",
        "global remote",
        "remote worldwide",
        "work from anywhere",
        "any location",
    ]

    india_restrictions = [
        "must be based in the us",
        "must be located in the us",
        "us residents only",
        "usa only",
        "must be based in canada",
        "canada residents only",
        "canada only",
        "must be based in the uk",
        "uk residents only",
        "uk only",
    ]

    if any(term in text for term in india_restrictions):
        return "Not India eligible"

    if any(term in text for term in india_terms):
        return "India eligible"

    if any(term in text for term in worldwide_terms):
        return "Worldwide - likely eligible"

    return "Not confirmed - verify"


def _normalize_job(
    job_id,
    title,
    company,
    location,
    description,
    url,
    source,
    posted_at="",
    employment_type="",
    salary_min=None,
    salary_max=None,
    salary_currency="",
    salary_period="",
):
    description = _clean_html(description)

    return {
        "id": str(job_id),
        "title": str(title or "").strip(),
        "company": str(company or "").strip(),
        "location": str(location or "").strip(),
        "description": description,
        "url": str(url or "").strip(),
        "source": source,
        "posted_at": str(posted_at or ""),
        "employment_type": str(employment_type or ""),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": str(salary_currency or "").upper(),
        "salary_period": str(salary_period or ""),
        "india_eligibility": _india_eligibility(
            location,
            description,
        ),
    }


def fetch_himalayas():
    """
    Search Himalayas for remote jobs that allow candidates in India.
    Himalayas requires visible source attribution and its applicationLink.
    """
    results = []

    for keyword in ROLE_SEARCH_TERMS:
        try:
            payload = _request(
                "https://himalayas.app/jobs/api/search",
                {
                    "q": keyword,
                    "country": "IN",
                    "sort": "recent",
                    "page": 1,
                },
            )

            for item in payload.get("jobs", []):
                restrictions = item.get("locationRestrictions") or []
                location = ", ".join(restrictions) if restrictions else "Worldwide"

                # The API's India country filter is the eligibility check.
                job = _normalize_job(
                    job_id=f"himalayas-{item.get('guid') or item.get('applicationLink')}",
                    title=item.get("title"),
                    company=item.get("companyName"),
                    location=location,
                    description=item.get("description") or item.get("excerpt"),
                    url=item.get("applicationLink"),
                    source="Himalayas",
                    posted_at=item.get("pubDate"),
                    employment_type=item.get("employmentType"),
                    salary_min=item.get("minSalary"),
                    salary_max=item.get("maxSalary"),
                    salary_currency=item.get("currency"),
                    salary_period=item.get("salaryPeriod"),
                )

                job["india_eligibility"] = "India eligible - source country filter"
                results.append(job)

        except Exception as exc:
            print(f"Himalayas search failed for '{keyword}': {exc}")

    return results


def fetch_jobicy():
    """
    Jobicy's public feed covers recent remote jobs.
    'Anywhere' is used here; USA/Canada/UK geo filters would mean
    candidate eligibility in those regions, not employer location.
    """
    results = []

    for keyword in ROLE_SEARCH_TERMS:
        try:
            payload = _request(
                "https://jobicy.com/api/jobs",
                {
                    "count": 100,
                    "geo": "anywhere",
                    "tag": keyword,
                },
            )

            for item in payload.get("jobs", []):
                job = _normalize_job(
                    job_id=f"jobicy-{item.get('id')}",
                    title=item.get("jobTitle"),
                    company=item.get("companyName"),
                    location=item.get("jobGeo") or "Anywhere",
                    description=(
                        item.get("jobDescription")
                        or item.get("jobExcerpt")
                    ),
                    url=item.get("url"),
                    source="Jobicy",
                    posted_at=item.get("pubDate"),
                    employment_type=", ".join(item.get("jobType") or []),
                    salary_min=item.get("salaryMin"),
                    salary_max=item.get("salaryMax"),
                    salary_currency=item.get("salaryCurrency"),
                    salary_period=item.get("salaryPeriod"),
                )

                results.append(job)

        except Exception as exc:
            print(f"Jobicy search failed for '{keyword}': {exc}")

    return results


def fetch_remotive():
    """
    Remotive public feed.
    Keep the original Remotive listing URL and visible source attribution.
    """
    results = []

    try:
        payload = _request(
            "https://remotive.com/api/remote-jobs",
            {"limit": 100},
        )

        for item in payload.get("jobs", []):
            job = _normalize_job(
                job_id=f"remotive-{item.get('id')}",
                title=item.get("title"),
                company=item.get("company_name"),
                location=item.get("candidate_required_location") or "Not specified",
                description=item.get("description"),
                url=item.get("url"),
                source="Remotive",
                posted_at=item.get("publication_date"),
                employment_type=item.get("job_type"),
                salary_currency="",
            )

            results.append(job)

    except Exception as exc:
        raise RuntimeError(f"Remotive feed failed: {exc}")

    return results


def get_search_portals():
    """
    Generate direct search links for major job websites.
    These links are not job listings and are not included in fetch_all().
    """
    links = []

    for keyword in ROLE_SEARCH_TERMS:
        encoded = quote_plus(keyword + " remote")

        for site, template in SEARCH_PORTALS.items():
            links.append({
                "site": site,
                "keyword": keyword,
                "url": template.format(query=encoded),
            })

    return links


def fetch_all():
    """
    Return (jobs, errors), preserving compatibility with app.py.
    """
    all_jobs = []
    errors = []

    sources = [
        ("Himalayas", fetch_himalayas),
        ("Jobicy", fetch_jobicy),
        ("Remotive", fetch_remotive),
    ]

    for source_name, fetcher in sources:
        try:
            all_jobs.extend(fetcher())
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")

    # Deduplicate using the original job URL.
    deduped = {}

    for job in all_jobs:
        url = job.get("url", "").strip()

        if not url:
            continue

        deduped[url] = job

    return list(deduped.values()), errors
