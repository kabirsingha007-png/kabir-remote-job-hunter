import streamlit as st
import pandas as pd
from job_agent.db import init_db, upsert_jobs, get_jobs, update_application
from job_agent.sources import fetch_all
from job_agent.matching import score_job, ai_explanation

st.set_page_config(page_title="Kabir | Remote Job Hunter", page_icon="🎯", layout="wide")
init_db()

st.title("🎯 Remote Job Hunter")
st.caption("A private job discovery and application workspace")

with st.sidebar:
    st.header("Search profile")
    role_text = st.text_area(
        "Target roles",
        "Global Compensation & Benefits\nTotal Rewards\nGlobal Employee Benefits\nIPMI\nInsurtech\nBenefits Technology\nGlobal Partnerships"
    )
    remote_only = st.checkbox("Fully remote only", value=True)
    india_eligible = st.checkbox("Must accept candidates based in India", value=True)
    preferred_currencies = st.multiselect("Preferred compensation currencies",
        ["USD", "GBP", "EUR", "INR"], default=["USD", "GBP", "EUR"])
    min_score = st.slider("Minimum match score", 0, 100, 50)
    run_search = st.button("Search for jobs", type="primary", use_container_width=True)

profile = {
    "roles": [x.strip() for x in role_text.splitlines() if x.strip()],
    "background": (
        "Experienced professional with 10+ years across compensation and benefits, "
        "global benefits, employee benefits, international private medical insurance "
        "(IPMI), insurance, insurtech, EOR, business development and partnerships."
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
    st.success(f"Search complete. Collected {len(fresh)} listings.")
    for err in errors:
        st.warning(err)

jobs = get_jobs()
if jobs:
    for job in jobs:
        if not job.get("match_score"):
            job["match_score"] = score_job(job, profile)
    df = pd.DataFrame(jobs)
    df["match_score"] = pd.to_numeric(df["match_score"], errors="coerce").fillna(0).astype(int)
    filtered = df[df["match_score"] >= min_score].sort_values("match_score", ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("Jobs collected", len(df))
    c2.metric("Matching jobs", len(filtered))
    c3.metric("Applications started", int((df.get("application_status", pd.Series(dtype=str)) != "Not applied").sum()))

    st.subheader("Recommended opportunities")
    if filtered.empty:
        st.info("No jobs meet the selected score. Lower the threshold or run another search.")
    else:
        for _, row in filtered.iterrows():
            with st.container(border=True):
                left, right = st.columns([5, 1])
                with left:
                    st.markdown(f"**{row.get('title','Untitled role')}**")
                    st.write(f"{row.get('company','Company not listed')} · {row.get('location','Location not specified')}")
                    st.caption(f"Source: {row.get('source','Unknown')} · Posted: {row.get('posted_at','Not provided')}")
                    st.write(str(row.get("ai_assessment") or "Keyword-based profile match. Verify location eligibility and role details."))
                    if row.get("url"):
                        st.link_button("View original job", row["url"])
                with right:
                    st.metric("Match", f"{int(row.get('match_score',0))}%")
                    current = row.get("application_status") or "Not applied"
                    options = ["Not applied", "Saved", "Preparing application", "Applied", "Interview", "Rejected"]
                    selected = st.selectbox("Status", options,
                        index=options.index(current) if current in options else 0,
                        key=f"status_{row['id']}")
                    if selected != current:
                        update_application(row["id"], selected)
                        st.rerun()
else:
    st.info("No listings saved yet. Select **Search for jobs** in the sidebar to begin.")

st.divider()
st.subheader("Application workflow")
st.write("This version discovers and ranks jobs and tracks your decisions. It does **not** submit applications. We will add tailored CV and cover-letter drafts next, with your approval required before any submission.")
st.caption("Job feeds may have coverage limits. Always verify eligibility, salary, closing date and application details on the employer's website.")
