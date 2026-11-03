# Shareable Link Checklist

First public release of the 2026 Senate Control Intelligence dashboard.
Fill in the URLs after deployment, then run the verification checks and smoke tests.

> **Demo release.** The dashboard runs on **synthetic polling data**. The forecasting
> pipeline, aggregation, forecast engine, and Monte Carlo simulation are real; the polls
> are not. Do not share these numbers as a real forecast.

## Links

- **GitHub repository:** https://github.com/adityab77-dev/election-intelligence-2026
- **Streamlit app (public):** `https://<subdomain>.streamlit.app`  *(fill in after deploy)*

## Deployment verification checks

- [ ] GitHub repo is **public** and the latest commit is pushed to `main`.
- [ ] `streamlit_app.py` is present at the repo root.
- [ ] `requirements.txt` is present at the repo root.
- [ ] Streamlit Cloud build completed with **no errors** in the build log.
- [ ] Python version in Streamlit Cloud advanced settings is **3.11 or 3.12**.
- [ ] App status in the Streamlit Cloud dashboard shows **"running"**.
- [ ] Opening the public URL loads the app (no "Oh no" / crash screen).

## Smoke tests (open the public URL)

- [ ] The **⚠️ Demo Mode** banner is visible at the top.
- [ ] **Senate Control Probability** shows **R ≈ 78% / D ≈ 22%**.
- [ ] **Expected Seats** shows roughly **R ≈ 51.4 / D ≈ 48.6** with a seat-distribution chart.
- [ ] **State Forecasts** table has **8 rows** (GA, NC, ME, MI, NH, TX, OH, IA).
- [ ] **Poll Aggregates** table has **8 rows** with weighted margins and variances.
- [ ] **Most Influential States** lists **IA / TX / OH** at the top with a leverage chart.
- [ ] **Simulation Metadata** shows 50,000 sims, seed 2026, a timestamp, and a code version.
- [ ] The **Methodology** tab renders its sections.
- [ ] No red error boxes or "No simulation found" warnings anywhere.

## If a check fails

| Symptom | Fix |
|---------|-----|
| Build fails on a dependency | Check the Streamlit Cloud build log; confirm Python 3.12 is selected. |
| "No simulation found" / empty tables | Bootstrap didn't run — check the app logs (Manage app → Logs) for a traceback. |
| `ModuleNotFoundError: election_intelligence` | `streamlit_app.py` isn't the main file, or `src/` wasn't added to the path. |
| App sleeps / slow first load | Free-tier apps sleep after inactivity; the first visit wakes it (~30 s). |
