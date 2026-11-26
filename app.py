import streamlit as st
import pandas as pd

from job_agent.db import init_db, upsert_jobs, get_jobs, update_application
from job_agent.sources import fetch_all
from job_agent.matching import (
    score_job,
    ai_explanation,
    employment_details,
    currency_details,
    india_eligibility,
)

st.set_page_config(
    page_title="Kabir | Remote Job Hunter",
    page_icon="🎯",
    layout="wide"
)

init_db()


def remote_status(job):
    """Identify remote-work evidence without assuming eligibility."""
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


st.title("🎯 Remote Job Hunter")
st.caption("International remote opportunities and application workspace")

with st.sidebar:
    st.header("Search profile")

    role_text = st.text_area(
        "Target roles",
        "Global Compensation & Benefits\n"
        "Total Rewards\n"
        "Global Employee Benefits\n"
        "Employee Benefits Consultant\n"
        "International Benefits Consultant\n"
        "IPMI\n"
        "International Health Insurance\n"
        "Insurtech\n"
        "Benefits Technology"
    )

    remote_only = st.checkbox(
        "Fully remote only",
        value=True
    )

    india_eligible = st.checkbox(
        "Must accept candidates based in India",
        value=True
    )

    preferred_currencies = st.multiselect(
        "Preferred compensation currencies",
        ["USD", "GBP", "EUR"],
        default=["USD", "GBP", "EUR"]
    )

    min_score = st.slider(
        "Minimum match score",
        0,
        100,
        50
    )

    run_search = st.button(
        "Search for jobs",
        type="primary",
        use_container_width=True
    )


profile = {
    "roles": [
        x.strip()
        for x in role_text.splitlines()
        if x.strip()
    ],
    "background": (
        "Experienced professional with 10+ years across compensation "
        "and benefits, global benefits, employee benefits, international "
        "private medical insurance (IPMI), insurance, insurtech, EOR, "
        "business development and partnerships."
    ),
    "remote_only": remote_only,
    "india_eligible": india_eligible,
    "currencies": preferred_currencies,
}


if run_search:
    with st.spinner("Collecting public job listings and scoring matches..."):
        fresh, errors = fetch_all()

        for job in fresh:
            job["match_score"] = score_job(job, profile)
            job["ai_assessment"] = ai_explanation(job, profile)

        upsert_jobs(fresh)

    st.success(
        f"Search complete. Collected {len(fresh)} listings."
    )

    for err in errors:
        st.warning(err)


jobs = get_jobs()

if jobs:

    for job in jobs:
        if not job.get("match_score"):
            job["match_score"] = score_job(job, profile)

        # Add screening information to every listing.
        details = employment_details(job)

        job["employment_type"] = details["employment_type"]
        job["priority"] = details["priority"]
        job["salary_currency"] = currency_details(job)
        job["india_status"] = india_eligibility(job)
        job["remote_status"] = remote_status(job)

    df = pd.DataFrame(jobs)

    df["match_score"] = pd.to_numeric(
        df["match_score"],
        errors="coerce"
    ).fillna(0).astype(int)

    filtered = df[
        df["match_score"] >= min_score
    ].copy()

    # Keep only listings with evidence of remote work
    # when the remote-only preference is selected.
    if remote_only:
        filtered = filtered[
            filtered["remote_status"] == "Remote indicated - verify"
        ]

    # Prioritize part-time and contract opportunities.
    priority_order = {
        "High priority": 0,
        "Verify": 1,
        "Lower priority": 2,
    }

    filtered["priority_order"] = (
        filtered["priority"].map(priority_order).fillna(3)
    )

    filtered = filtered.sort_values(
        ["priority_order", "match_score"],
        ascending=[True, False]
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("Jobs collected", len(df))
    c2.metric("Matching jobs", len(filtered))

    applications_started = int(
        (
            df.get(
                "application_status",
                pd.Series("Not applied", index=df.index)
            ) != "Not applied"
        ).sum()
    )

    c3.metric("Applications started", applications_started)

    st.subheader("Recommended opportunities")

    if filtered.empty:
        st.info(
            "No jobs meet the current filters. "
            "Try lowering the match score or temporarily switching off "
            "the fully remote filter."
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
                            or "Keyword-based profile match. "
                            "Verify role and location details."
                        )
                    )

                    if row.get("url"):
                        st.link_button(
                            "View original job",
                            row["url"]
                        )

                with right:

                    st.metric(
                        "Match",
                        f"{int(row.get('match_score', 0))}%"
                    )

                    current = (
                        row.get("application_status")
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
                            if current in options else 0
                        ),
                        key=f"status_{row['id']}"
                    )

                    if selected != current:
                        update_application(row["id"], selected)
                        st.rerun()

else:
    st.info(
        "No listings saved yet. Select "
        "**Search for jobs** in the sidebar to begin."
    )


st.divider()

st.subheader("Application workflow")

st.write(
    "This version discovers and ranks jobs, identifies employment "
    "type and screening details, and tracks your application decisions. "
    "It does not submit applications. Tailored CV and cover-letter "
    "drafting with your approval will be added in a later step."
)

st.caption(
    "Remote status and India eligibility are screening indicators, "
    "not guarantees. Always verify hiring locations, salary, closing "
    "dates and application requirements on the employer's website."
)
