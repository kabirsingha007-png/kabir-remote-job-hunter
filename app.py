
import streamlit as st
import pandas as pd

from job_agent.db import (
    init_db,
    upsert_jobs,
    get_jobs,
    update_application,
)

from job_agent.sources import fetch_all

from job_agent.matching import (
    score_job,
    ai_explanation,
    employment_details,
    currency_details,
    india_eligibility,
)


# --------------------------------------------------
# PAGE SETUP
# --------------------------------------------------

st.set_page_config(
    page_title="Kabir | Remote Job Hunter",
    page_icon="🎯",
    layout="wide",
)

init_db()


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def remote_status(job):
    """Identify evidence of remote work."""

    text = (
        str(job.get("title", "")) + " " +
        str(job.get("location", "")) + " " +
        str(job.get("description", ""))
    ).lower()

    remote_terms = [
        "remote",
        "fully remote",
        "100% remote",
        "work from anywhere",
        "distributed",
        "remote worldwide",
    ]

    if any(term in text for term in remote_terms):
        return "Remote indicated - verify"

    return "Remote not confirmed"


# --------------------------------------------------
# APPLICATION HEADER
# --------------------------------------------------

st.title("🎯 Remote Job Hunter")

st.caption(
    "International remote opportunities and application workspace"
)


# --------------------------------------------------
# SEARCH PROFILE
# --------------------------------------------------

with st.sidebar:

    st.header("Search profile")

    role_text = st.text_area(
        "Target roles",
        "Global Compensation & Benefits\n"
        "Total Rewards\n"
        "Global Employee Benefits\n"
        "Employee Benefits Consultant\n"
        "International Benefits Consultant\n"
        "Employee Benefits Advisor\n"
        "Global Benefits Specialist\n"
        "Compensation & Benefits Manager\n"
        "IPMI\n"
        "International Health Insurance\n"
        "Insurtech\n"
        "Benefits Technology",
    )

    remote_only = st.checkbox(
        "Fully remote only",
        value=True,
    )

    india_eligible = st.checkbox(
        "Check for India eligibility",
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


# --------------------------------------------------
# CANDIDATE PROFILE
# --------------------------------------------------

profile = {
    "roles": [
        item.strip()
        for item in role_text.splitlines()
        if item.strip()
    ],

    "background": (
        "Experienced professional with 10+ years across "
        "compensation and benefits, global benefits, employee "
        "benefits, international private medical insurance "
        "(IPMI), insurance, insurtech, EOR, business development "
        "and partnerships."
    ),

    "remote_only": remote_only,
    "india_eligible": india_eligible,
    "currencies": preferred_currencies,
}


# --------------------------------------------------
# SEARCH AND COLLECT JOBS
# --------------------------------------------------

if run_search:

    with st.spinner(
        "Collecting public job listings and scoring matches..."
    ):

        fresh, errors = fetch_all()

        for job in fresh:

            job["match_score"] = score_job(
                job,
                profile,
            )

            job["ai_assessment"] = ai_explanation(
                job,
                profile,
            )

        upsert_jobs(fresh)

    st.success(
        f"Search complete. Collected {len(fresh)} listings."
    )

    for error in errors:
        st.warning(error)


# --------------------------------------------------
# LOAD AND RECALCULATE ALL SAVED JOBS
# --------------------------------------------------

jobs = get_jobs()

if jobs:

    for job in jobs:

        # Always recalculate using the latest matching rules.
        job["match_score"] = score_job(
            job,
            profile,
        )

        # Identify employment type and priority.
        details = employment_details(job)

        job["employment_type"] = details["employment_type"]
        job["priority"] = details["priority"]

        # Identify currency and eligibility information.
        job["salary_currency"] = currency_details(job)

        job["india_status"] = india_eligibility(job)

        job["remote_status"] = remote_status(job)

    df = pd.DataFrame(jobs)

    df["match_score"] = pd.to_numeric(
        df["match_score"],
        errors="coerce",
    ).fillna(0).astype(int)

    # Remove jobs that do not meet the score threshold.
    filtered = df[
        df["match_score"] >= min_score
    ].copy()

    # Apply remote-only filter.
    if remote_only:

        filtered = filtered[
            filtered["remote_status"]
            == "Remote indicated - verify"
        ]

    # Prioritize part-time and contract opportunities.
    priority_order = {
        "High priority": 0,
        "Verify": 1,
        "Lower priority": 2,
    }

    filtered["priority_order"] = (
        filtered["priority"]
        .map(priority_order)
        .fillna(3)
    )

    filtered = filtered.sort_values(
        ["priority_order", "match_score"],
        ascending=[True, False],
    )

    # --------------------------------------------------
    # DASHBOARD METRICS
    # --------------------------------------------------

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Jobs collected",
        len(df),
    )

    col2.metric(
        "Matching jobs",
        len(filtered),
    )

    application_status = df.get(
        "application_status",
        pd.Series("Not applied", index=df.index),
    )

    applications_started = int(
        (application_status != "Not applied").sum()
    )

    col3.metric(
        "Applications started",
        applications_started,
    )

    # --------------------------------------------------
    # RECOMMENDED OPPORTUNITIES
    # --------------------------------------------------

    st.subheader("Recommended opportunities")

    if filtered.empty:

        st.info(
            "No jobs meet the selected filters. "
            "Try lowering the minimum match score or "
            "switching off the fully remote filter."
        )

    else:

        for _, row in filtered.iterrows():

            with st.container(border=True):

                left, right = st.columns([5, 1])

                with left:

                    st.markdown(
                        f"**{row.get('title', 'Untitled role')}**"
                    )

                    st.write(
                        f"{row.get('company', 'Company not listed')} "
                        f"· {row.get('location', 'Location not specified')}"
                    )

                    st.caption(
                        f"Source: {row.get('source', 'Unknown')} "
                        f"· Posted: {row.get('posted_at', 'Not provided')}"
                    )

                    st.divider()

                    st.write(
                        f"**Employment type:** "
                        f"{row.get('employment_type', 'Not specified')}"
                    )

                    st.write(
                        f"**Opportunity priority:** "
                        f"{row.get('priority', 'Verify')}"
                    )

                    st.write(
                        f"**Remote status:** "
                        f"{row.get('remote_status', 'Not confirmed')}"
                    )

                    st.write(
                        f"**India eligibility:** "
                        f"{row.get('india_status', 'Not confirmed')}"
                    )

                    st.write(
                        f"**Salary currency:** "
                        f"{row.get('salary_currency', 'Not specified')}"
                    )

                    st.write(
                        str(
                            row.get("ai_assessment")
                            or "Keyword-based match. "
                            "Verify role and location details."
                        )
                    )

                    job_url = row.get("url")

                    if (
                        isinstance(job_url, str)
                        and job_url.startswith("http")
                    ):

                        st.link_button(
                            "View original job",
                            job_url,
                        )

                # --------------------------------------
                # MATCH SCORE AND APPLICATION STATUS
                # --------------------------------------

                with right:

                    st.metric(
                        "Match",
                        f"{int(row.get('match_score', 0))}%",
                    )

                    current = (
                        row.get("application_status")
                        or "Not applied"
                    )

                    if pd.isna(current):
                        current = "Not applied"

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
                        key=f"status_{row['id']}",
                    )

                    if selected != current:

                        update_application(
                            row["id"],
                            selected,
                        )

                        st.rerun()


else:

    st.info(
        "No listings saved yet. Select "
        "**Search for jobs** in the sidebar to begin."
    )


# --------------------------------------------------
# APPLICATION WORKFLOW
# --------------------------------------------------

st.divider()

st.subheader("Application workflow")

st.write(
    "This version discovers and ranks jobs, identifies "
    "employment type and screening details, and tracks "
    "application decisions. It does not submit applications. "
    "Tailored CV and cover-letter drafting with your approval "
    "will be added in a later version."
)

st.caption(
    "Remote status and India eligibility are screening indicators, "
    "not guarantees. Always verify hiring locations, salary, "
    "closing dates and application requirements on the employer's website."
)
