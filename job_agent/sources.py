import requests

HEADERS = {
    "User-Agent": "KabirRemoteJobHunter/1.0 (personal job discovery)"
}
TIMEOUT = 20


def _request(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def fetch_remotive():
    payload = _request(
        "https://remotive.com/api/remote-jobs",
        {"limit": 100}
    )

    results = []

    for item in payload.get("jobs", []):
        results.append({
            "id": f"remotive-{item.get('id')}",
            "title": item.get("title", ""),
            "company": item.get("company_name", ""),
            "location": item.get("candidate_required_location", "Remote"),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "source": "Remotive",
            "posted_at": item.get("publication_date", ""),
        })

    return results


def fetch_arbeitnow():
    payload = _request(
        "https://www.arbeitnow.com/api/job-board-api"
    )

    results = []

    for item in payload.get("data", []):
        results.append({
            "id": f"arbeitnow-{item.get('slug') or item.get('url')}",
            "title": item.get("title", ""),
            "company": item.get("company_name", ""),
            "location": item.get("location", ""),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "source": "Arbeitnow",
            "posted_at": item.get("created_at", ""),
        })

    return results


def fetch_all():
    all_jobs = []
    errors = []

    sources = [
        ("Remotive", fetch_remotive),
        ("Arbeitnow", fetch_arbeitnow)
    ]

    for source_name, fetcher in sources:
        try:
            all_jobs.extend(fetcher())
        except Exception as exc:
            errors.append(
                f"{source_name} feed could not be reached: {exc}"
            )

    deduped = {}

    for job in all_jobs:
        if job.get("url"):
            deduped[job["url"]] = job

    return list(deduped.values()), errors
