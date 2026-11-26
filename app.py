
import re
import streamlit as st

from job_agent.db import (
    init_db,
    upsert_jobs,
    get_jobs,
    update_application,
)

from job_agent.sources import fetch_all, get_search_portals

from job_agent.matching import (
    score_job,
    ai_explanation,
    employment_details,
    currency_details,
    india_eligibility,
)


# ==================================================
# PAGE SETUP
# ==================================================

st.set_page_config(
    page_title="Kabir | Remote Job Hunter",
    page_icon="🎯",
    layout="wide",
)

init_db()


# ==================================================
# STRICT JOB TITLE FILTER
# ==================================================

RELEVANT_TITLE_PATTERNS = [
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
    r"\bbenefits director\b",
    r"\bcompensation and benefits\b",
    r"\bcompensation & benefits\b",
    r"\bcomp & ben\b",
    r"\btotal rewards\b",
    r"\bglobal rewards\b",
    r"\binternational health insurance\b",
    r"\bglobal health insurance\b",
    r"\binternational private medical insurance\b",
    r"\bIPMI\b",
    r"\bhealth benefits\b",
    r"\bhealth insurance consultant\b",
    r"\bemployee wellbeing benefits\b",
]

EXCLUDED_TITLE_PATTERNS = [
    r"\bsoftware engineer\b",
    r"\bsoftware developer\b",
    r"\bfrontend developer\b",
    r"\bbackend developer\b",
    r"\bfull stack developer\b",
    r"\bdata engineer\b",
    r"\bdevops engineer\b",
    r"\bcloud engineer\b",
    r"\bmachine learning engineer\b",
    r"\bweb developer\b",
    r"\bpython developer\b",
    r"\bjava developer\b",
    r"\bfield solutions engineer\b",
    r"\bprocurement\b",
    r"\bpurchasing\b",
    r"\bsupply chain\b",
    r"\bwarehouse\b",
    r"\btechnician\b",
]


def is_target_job(job):
    """Only allow jobs whose titles match the target professions."""

    title = str(job.get("title") or "").strip().lower()

    if not title:
        return False

    if any(
        re.search(pattern, title, re.I)
        for pattern in EXCLUDED_TITLE_PATTERNS
    ):
        return False

    return any(
        re.search(pattern, title, re.I)
        for pattern in RELEVANT_TITLE_PATTERNS
    )


def remote_status(job):
    text = " ".join([
        str(job.get("title") or ""),
        str(job.get("location") or ""),
        str(job.get("description") or ""),
    ]).lower()

    remote_terms = [
        "remote",
        "fully remote",
        "100% remote",
        "work from anywhere",
        "distributed team",
        "remote worldwide",
    ]

    if any(term in text for term in remote_terms):
        return "Remote indicated - verify"

    return "Remote not confirmed"


def employer_market_status(job):
    """
    Do not mistake the candidate's permitted location
    for the employer's country.
    """

    market = job.get("employer_market")

    if market and market != "Not verified - check original listing":
        return str(market)

    return "Not verified - check original listing"


def safe_text(value, fallback="Not specified"):
    if value is None:
        return fallback

    value = str(value).strip()

    return value if value else fallback


# ==================================================
# HEADER
# ==================================================

st.title("🎯 Remote Job Hunter")

st.caption(
    "International Employee Benefits, Compensation & Benefits, "
    "Total Rewards and IPMI opportunities"
)


# ==================================================
# SIDEBAR SEARCH PROFILE
# ==================================================

with st.sidebar:

    st.header("Search profile")

    role_text = st.text_area(
        "Target roles",
        value=(
            "Global Compensation & Benefits\n"
            "Total Rewards\n"
            "Global Employee Benefits\n"
            "Employee Benefits Consultant\n"
            "International Benefits Consultant\n"
            "Employee Benefits Advisor\n"
            "Global Benefits Specialist\n"
            "Compensation & Benefits Manager\n"
            "IPMI\n"
            "International Health Insurance"
        ),
        height=180,
    )

    st.caption("Target employer markets")

    target_markets = st.multiselect(
        "Employer countries",
        ["USA", "Canada", "UK"],
        default=["USA", "Canada", "UK"],
    )

    remote_only = st.checkbox(
        "Fully remote only",
        value=True,
    )

    india_eligible = st.checkbox(
        "Prioritize India eligibility",
        value=True,
    )

    preferred_currencies = st.multiselect(
        "Preferred compensation currencies",
        ["USD", "GBP", "EUR"],
        default=["USD", "GBP", "EUR"],
    )

    min_score = st.slider(
        "Minimum match score",
        0,
        100,
        50,
    )

    run_search = st.button(
        "Search for jobs",
        type="primary",
        use_container_width=True,
    )


# ==================================================
# CANDIDATE PROFILE
# ==================================================

profile = {
    "roles": [
        item.strip()
        for item in role_text.splitlines()
        if item.strip()
    ],
    "background": (
        "Experienced professional with 10+ years across "
        "compensation and benefits, global benefits, employee "
        "benefits, international private medical insurance, "
        "IPMI, insurance, insurtech, EOR and partnerships."
    ),
    "remote_only": remote_only,
    "india_eligible": india_eligible,
    "currencies": preferred_currencies,
}


# ==================================================
# COLLECT NEW JOBS
# ==================================================

if run_search:

    with st.spinner(
        "Searching job sources and checking relevant job titles..."
    ):

        try:
            fresh_jobs, errors = fetch_all()

            # Apply strict title filter before saving.
            relevant_fresh_jobs = [
                job for job in fresh_jobs
                if is_target_job(job)
            ]

            for job in relevant_fresh_jobs:

                job["match_score"] = score_job(
                    job,
                    profile,
                )

                job["ai_assessment"] = ai_explanation(
                    job,
                    profile,
                )

            upsert_jobs(relevant_fresh_jobs)

            st.success(
                f"Search finished. "
                f"{len(relevant_fresh_jobs)} relevant jobs found "
                f"out of {len(fresh_jobs)} collected."
            )

            for error in errors:
                st.warning(error)

        except Exception as exc:
            st.error(
                f"Job search failed: {exc}"
            )


# ==================================================
# LOAD SAVED JOBS
# ==================================================

saved_jobs = get_jobs()

# Keep only genuine target job titles.
# Hide obsolete listings from the removed Arbeitnow source.
relevant_jobs = []

for job in saved_jobs:

    if not is_target_job(job):
        continue

    if str(job.get("source") or "").lower() == "arbeitnow":
        continue

    job["match_score"] = score_job(
        job,
        profile,
    )

    details = employment_details(job)

    job["employment_type"] = details["employment_type"]
    job["priority"] = details["priority"]

    job["salary_currency"] = currency_details(job)

    job["india_status"] = india_eligibility(job)

    job["remote_status"] = remote_status(job)

    job["employer_market_status"] = employer_market_status(job)

    relevant_jobs.append(job)


# ==================================================
# FILTER JOBS
# ==================================================

filtered_jobs = []

for job in relevant_jobs:

    score = int(job.get("match_score") or 0)

    if score < min_score:
        continue

    if remote_only:
        if job["remote_status"] != "Remote indicated - verify":
            continue

    # Currency is a preference, not a reason to discard
    # a job when the employer has not disclosed salary.
    job_currency = job["salary_currency"]

    if (
        preferred_currencies
        and job_currency != "Not specified"
        and not any(
            currency in job_currency
            for currency in preferred_currencies
        )
    ):
        continue

    filtered_jobs.append(job)


# Prioritize part-time and contract opportunities.
priority_order = {
    "High priority": 0,
    "Verify": 1,
    "Lower priority": 2,
}

filtered_jobs.sort(
    key=lambda job: (
        priority_order.get(job.get("priority"), 3),
        -int(job.get("match_score") or 0),
    )
)


# ==================================================
# DASHBOARD METRICS
# ==================================================

applications_started = sum(
    1 for job in saved_jobs
    if job.get("application_status", "Not applied") != "Not applied"
)

col1, col2, col3 = st.columns(3)

col1.metric(
    "Jobs collected",
    len(saved_jobs),
)

col2.metric(
    "Relevant job titles",
    len(relevant_jobs),
)

col3.metric(
    "Applications started",
    applications_started,
)

st.divider()


# ==================================================
# RECOMMENDED OPPORTUNITIES
# ==================================================

st.subheader("Recommended opportunities")

st.caption(
    "Only job titles matching your target professional "
    "areas are displayed. Employer country and India eligibility "
    "must be verified against the original listing."
)

if not filtered_jobs:

    st.info(
        "No relevant jobs currently meet your filters. "
        "Try lowering the minimum match score or switching "
        "off the fully remote filter."
    )

else:

    for job in filtered_jobs:

        job_id = str(job.get("id") or job.get("url") or "unknown")

        with st.container(border=True):

            left, right = st.columns([5, 1])

            with left:

                st.markdown(
                    f"**{safe_text(job.get('title'))}**"
                )

                st.write(
                    f"{safe_text(job.get('company'), 'Company not listed')} "
                    f"· {safe_text(job.get('location'))}"
                )

                st.caption(
                    f"Source: {safe_text(job.get('source'))} "
                    f"· Posted: {safe_text(job.get('posted_at'))}"
                )

                st.divider()

                st.write(
                    f"**Employer market:** "
                    f"{job['employer_market_status']}"
                )

                st.write(
                    f"**Employment type:** "
                    f"{job['employment_type']}"
                )

                st.write(
                    f"**Opportunity priority:** "
                    f"{job['priority']}"
                )

                st.write(
                    f"**Remote status:** "
                    f"{job['remote_status']}"
                )

                st.write(
                    f"**India eligibility:** "
                    f"{job['india_status']}"
                )

                st.write(
                    f"**Salary currency:** "
                    f"{job['salary_currency']}"
                )

                if job.get("salary_min") or job.get("salary_max"):

                    st.write(
                        f"**Published salary range:** "
                        f"{safe_text(job.get('salary_min'), '')} "
                        f"- {safe_text(job.get('salary_max'), '')} "
                        f"{safe_text(job.get('salary_currency'), '')}"
                    )

                assessment = job.get("ai_assessment")

                if assessment:
                    st.write(assessment)
                else:
                    st.write(
                        "Review the original job description "
                        "to confirm role requirements and eligibility."
                    )

                job_url = job.get("url")

                if (
                    isinstance(job_url, str)
                    and job_url.startswith("http")
                ):
                    st.link_button(
                        "View original job",
                        job_url,
                    )

            with right:

                st.metric(
                    "Match",
                    f"{int(job.get('match_score') or 0)}%",
                )

                current = (
                    job.get("application_status")
                    or "Not applied"
                )

                options = [
                    "Not applied",
                    "Saved",
                    "Preparing application",
                    "Applied",
                    "Interview",
                    "Rejected",
                ]

                selected = st.selectbox(
                    "Status",
                    options,
                    index=(
                        options.index(current)
                        if current in options
                        else 0
                    ),
                    key=f"status_{job_id}",
                )

                if selected != current:
                    update_application(
                        job["id"],
                        selected,
                    )
                    st.rerun()


# ==================================================
# ADDITIONAL JOB SEARCH WEBSITES
# ==================================================

st.divider()

with st.expander(
    "Search additional job websites",
    expanded=False,
):

    st.write(
        "Use these websites to find additional opportunities. "
        "These are direct search links, not automatically collected listings."
    )

    search_role = st.selectbox(
        "Choose a role",
        [
            "Employee Benefits Consultant",
            "Global Employee Benefits",
            "Compensation and Benefits",
            "Total Rewards",
            "International Health Insurance",
            "IPMI",
            "Benefits Manager",
        ],
    )

    search_country = st.selectbox(
        "Choose employer market to search",
        ["USA", "Canada", "UK"],
    )

    market_query = {
        "USA": "United States",
        "Canada": "Canada",
        "UK": "United Kingdom",
    }[search_country]

    from urllib.parse import quote_plus

    query = quote_plus(
        f'"{search_role}" remote {market_query} India'
    )

    search_links = [
        (
            "LinkedIn Jobs",
            f"https://www.linkedin.com/jobs/search/?keywords={query}",
        ),
        (
            "Indeed",
            (
                "https://www.indeed.com/jobs?q=" + query
                if search_country == "USA"
                else (
                    "https://ca.indeed.com/jobs?q=" + query
                    if search_country == "Canada"
                    else "https://uk.indeed.com/jobs?q=" + query
                )
            ),
        ),
        (
            "Glassdoor",
            f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}",
        ),
        (
            "Google Jobs Search",
            f"https://www.google.com/search?q={query}+jobs",
        ),
    ]

    for label, url in search_links:
        st.link_button(
            f"Search on {label}",
            url,
        )


# ==================================================
# APPLICATION WORKFLOW
# ==================================================

st.divider()

st.subheader("Application workflow")

st.write(
    "This application discovers and ranks jobs, identifies "
    "employment type and screening information, and tracks "
    "application decisions. It does not submit applications. "
    "CV and cover-letter tailoring will be added in a later version."
)

st.caption(
    "Remote status, employer market and India eligibility "
    "are screening indicators, not guarantees. Always verify "
    "the original employer listing before applying."
)
