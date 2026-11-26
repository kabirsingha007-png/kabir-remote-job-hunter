
import re
import requests
from html import unescape
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": "KabirRemoteJobHunter/1.0 (personal job discovery)",
    "Accept": "application/json",
}

TIMEOUT = 25

# Search terms are deliberately specific to your professional background.
ROLE_SEARCH_TERMS = [
    "employee benefits",
    "global benefits",
    "benefits consultant",
    "benefits specialist",
    "compensation and benefits",
    "total rewards",
    "international health insurance",
    "IPMI",
]

# Only accept genuine benefits / insurance / rewards job titles.
ROLE_TITLE_PATTERNS = [
    r"\bemployee benefits\b",
    r"\bglobal benefits\b",
    r"\binternational benefits\b",
    r"\bbenefits consultant\b",
    r"\bbenefits advisor\b",
    r"\bbenefits adviser\b",
    r"\bbenefits specialist\b",
    r"\bbenefits manager\b",
    r"\bbenefits analyst\b",
    r"\bbenefits broker\b",
    r"\bcompensation and benefits\b",
    r"\bcompensation & benefits\b",
    r"\bcomp ?& ?ben\b",
    r"\btotal rewards\b",
    r"\binternational health insurance\b",
    r"\bglobal health insurance\b",
    r"\binternational private medical insurance\b",
    r"\bIPMI\b",
    r"\bgroup health insurance\b",
]

# Exclude unrelated job families even if descriptions mention benefits.
EXCLUDED_TITLE_PATTERNS = [
    r"\bsoftware\b",
    r"\bdeveloper\b",
    r"\bengineer\b",
    r"\bprogrammer\b",
    r"\bdata scientist\b",
    r"\bdevops\b",
    r"\bproduct designer\b",
    r"\bprocurement\b",
    r"\bpurchasing\b",
    r"\bsupply chain\b",
    r"\bwarehouse\b",
    r"\bmechanic\b",
    r"\btechnician\b",
]


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
    value = unescape(str(value or ""))
    value = re.sub(
        r"<script.*?</script>",
        " ",
        value,
        flags=re.I | re.S,
    )
    value = re.sub(
        r"<style.*?</style>",
        " ",
        value,
        flags=re.I | re.S,
    )
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _is_relevant_role(title):
    title = str(title or "").lower()

    if any(
        re.search(pattern, title, re.I)
        for pattern in EXCLUDED_TITLE_PATTERNS
    ):
        return False

    return any(
        re.search(pattern, title, re.I)
        for pattern in ROLE_TITLE_PATTERNS
    )


def _india_status(location):
    text = str(location or "").lower()

    india_terms = [
        "india",
        "worldwide",
        "anywhere",
        "anywhere in the world",
        "global",
    ]

    if any(term in text for term in india_terms):
        return "India eligible - source location"

    return "Not confirmed"


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
    india_status="Not confirmed",
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
        "india_eligibility": india_status,

        # These APIs do not consistently provide employer country.
        # Do not confuse candidate eligibility with employer location.
        "employer_market": "Not verified - check original listing",
    }


def fetch_himalayas():
    results = []

    for keyword in ROLE_SEARCH_TERMS:
        try:
            for page in (1, 2):
                payload = _request(
                    "https://himalayas.app/jobs/api/search",
                    {
                        "q": keyword,
                        "country": "IN",
                        "sort": "recent",
                        "page": page,
                    },
                )

                jobs = payload.get("jobs", [])

                if not jobs:
                    break

                for item in jobs:
                    title = item.get("title", "")

                    if not _is_relevant_role(title):
                        continue

                    restrictions = item.get("locationRestrictions") or []

                    # Country=IN is the API's candidate-location filter.
                    # Keep only results consistent with that restriction.
                    if restrictions and "IN" not in [
                        str(country).upper()
                        for country in restrictions
                    ]:
                        continue

                    location = (
                        ", ".join(restrictions)
                        if restrictions
                        else "Worldwide"
                    )

                    posted = item.get("pubDate", "")

                    if isinstance(posted, (int, float)):
                        posted = datetime.fromtimestamp(
                            posted,
                            tz=timezone.utc,
                        ).isoformat()

                    results.append(
                        _normalize_job(
                            job_id=f"himalayas-{item.get('guid')}",
                            title=title,
                            company=item.get("companyName"),
                            location=location,
                            description=(
                                item.get("description")
                                or item.get("excerpt")
                            ),
                            url=item.get("applicationLink"),
                            source="Himalayas",
                            posted_at=posted,
                            employment_type=item.get("employmentType"),
                            salary_min=item.get("minSalary"),
                            salary_max=item.get("maxSalary"),
                            salary_currency=item.get("currency"),
                            salary_period=item.get("salaryPeriod"),
                            india_status="India eligible - Himalayas country filter",
                        )
                    )

        except Exception as exc:
            print(
                f"Himalayas search failed for '{keyword}': {exc}"
            )

    return results


def fetch_jobicy():
    results = []

    for keyword in ROLE_SEARCH_TERMS:
        try:
            payload = _request(
                "https://jobicy.com/api/jobs",
                {
                    "count": 100,
                    "geo": "india",
                    "tag": keyword,
                },
            )

            if payload.get("success") is False:
                raise RuntimeError(
                    payload.get("error", "Jobicy API error")
                )

            for item in payload.get("jobs", []):
                title = item.get("jobTitle", "")

                if not _is_relevant_role(title):
                    continue

                job_types = item.get("jobType") or []

                results.append(
                    _normalize_job(
                        job_id=f"jobicy-{item.get('id')}",
                        title=title,
                        company=item.get("companyName"),
                        location=item.get("jobGeo") or "India",
                        description=(
                            item.get("jobDescription")
                            or item.get("jobExcerpt")
                        ),
                        url=item.get("url"),
                        source="Jobicy",
                        posted_at=item.get("pubDate"),
                        employment_type=", ".join(job_types),
                        salary_min=item.get("salaryMin"),
                        salary_max=item.get("salaryMax"),
                        salary_currency=item.get("salaryCurrency"),
                        salary_period=item.get("salaryPeriod"),
                        india_status="India eligible - Jobicy India filter",
                    )
                )

        except Exception as exc:
            print(
                f"Jobicy search failed for '{keyword}': {exc}"
            )

    return results


def fetch_remotive():
    results = []

    payload = _request(
        "https://remotive.com/api/remote-jobs",
        {"limit": 100},
    )

    for item in payload.get("jobs", []):
        title = item.get("title", "")

        if not _is_relevant_role(title):
            continue

        candidate_location = (
            item.get("candidate_required_location") or ""
        )

        # Remotive must explicitly allow India or worldwide applicants.
        location_lower = candidate_location.lower()

        india_allowed = (
            "india" in location_lower
            or "worldwide" in location_lower
            or "anywhere" in location_lower
        )

        if not india_allowed:
            continue

        results.append(
            _normalize_job(
                job_id=f"remotive-{item.get('id')}",
                title=title,
                company=item.get("company_name"),
                location=candidate_location,
                description=item.get("description"),
                url=item.get("url"),
                source="Remotive",
                posted_at=item.get("publication_date"),
                employment_type=item.get("job_type"),
                india_status="India eligible - listing location",
            )
        )

    return results


def get_search_portals():
    """
    Direct search links for additional job websites.
    These are search destinations, not scraped job feeds.
    """

    searches = [
        ("LinkedIn", "https://www.linkedin.com/jobs/search/?keywords={query}"),
        ("Indeed USA", "https://www.indeed.com/jobs?q={query}"),
        ("Indeed Canada", "https://ca.indeed.com/jobs?q={query}"),
        ("Indeed UK", "https://uk.indeed.com/jobs?q={query}"),
        ("Glassdoor", "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}"),
        ("Google Jobs", "https://www.google.com/search?q={query}+jobs"),
    ]

    from urllib.parse import quote_plus

    links = []

    for keyword in ROLE_SEARCH_TERMS:
        query = quote_plus(
            keyword + " remote India eligible"
        )

        for site, template in searches:
            links.append({
                "site": site,
                "keyword": keyword,
                "url": template.format(query=query),
            })

    return links


def fetch_all():
    """
    Return (jobs, errors).
    This keeps compatibility with the existing app.py.
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

    # Final relevance check and URL-based deduplication.
    deduped = {}

    for job in all_jobs:
        if not _is_relevant_role(job.get("title")):
            continue

        url = job.get("url", "").strip()

        if not url:
            continue

        deduped[url] = job

    return list(deduped.values()), errors
