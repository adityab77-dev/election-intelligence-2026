# Source-Discovery Report — State Secretary-of-State Results Feeds

Prepared 2026-11-03 (election night). **Discovery only — no code.** Question: do ≥5 of the 8
battleground states publish **machine-readable** election results, warranting a
`SecretaryOfStateResultsSource` instead of Wikipedia?

## Method & a critical caveat
Probed each state's results system live tonight (status, content-type, embedded data markers), plus
established knowledge of each platform. **Important:** many state/Clarity endpoints returned **HTTP 403
to this automated client** (GA, OH, MI, ME, NH) — i.e. they **block non-browser / datacenter access**.
That is a *production* risk: a GitHub Action or Streamlit Cloud server fetching these may be blocked
even though the data exists for a human browser. Confidence is marked per row.

## Per-state findings

| State | Source | Format | Refresh rate | Feasibility |
|-------|--------|--------|--------------|-------------|
| **NC** | `dl.ncsbe.gov` ENRS (State Board of Elections) | **TSV/CSV/ZIP download** (`results_pct_*.zip`) | ~1–5 min | **High** — the cleanest SoS data feed; direct file download. *(ER dashboard reachable; download portal confirmed.)* |
| **GA** | **Clarity/Scytl** (`results.enr.clarityelections.com/GA/…`) | **JSON + XML + CSV** (`summary.json`, `detail.xml`, `detail.zip`) | ~1–2 min | **Medium-High** — structured, but needs per-cycle election-ID discovery and **403-blocked** to automated clients. |
| **OH** | OH SoS results/data portal | **CSV/XML download** | periodic (min) | **Medium-High** — downloadable files, but **403-blocked**; live host `results.ohiosos.gov` did not resolve tonight (activates election night / different host). |
| **MI** | `mielections.us` / `miboecfr.nictusa.com` | **Tab-delimited TXT** download | periodic | **Medium** — machine-readable files, but **403 / timeout** to automated clients. |
| **TX** | Texas Election Night Returns (`results.texas-election.com`) | **JSON** behind a SPA | ~5–10 min | **Medium** — reachable (browser UA); underlying JSON endpoint needs discovery. |
| **IA** | `electionresults.iowa.gov` | SPA → JSON (undocumented) | ? | **Low-Medium** — reachable but a JS app; data endpoint must be reverse-engineered. |
| **NH** | NH SoS | HTML / PDF (some CSV) | slow | **Low** — little structured data; host guesses did not resolve. |
| **ME** | Maine SoS | HTML / PDF | slow | **Low** — weak machine-readability; RCV Senate adds complexity; **403**. |

### Probe evidence (tonight)
- **Reachable (200):** TX `results.texas-election.com` (SPA shell), IA `electionresults.iowa.gov` (SPA
  shell), NC `er.ncsbe.gov` (dashboard, "download/enr" markers) and `dl.ncsbe.gov` portal.
- **403 (bot-blocked):** GA Clarity, OH SoS portal, MI MVIC/BOE, ME, NH.
- **DNS fail / wrong host:** `results.ohiosos.gov`, `electionresults.sos.nh.gov` (hosts vary per cycle).

## Machine-readable count
**Machine-readable results exist for at least 5 of 8:** **NC, GA, OH, MI, TX** (with **IA** a likely
sixth once its endpoint is found). NH and ME are weak (HTML/PDF). **The ≥5 threshold is met.**

> Architectural note: **GA uses Clarity/Scytl**, a shared platform several states use — one Clarity
> adapter can cover every Clarity state, reducing the per-state count. NC/OH/MI/TX each need their own.

## Recommendation
**Yes — build a `SecretaryOfStateResultsSource`, incrementally, as an upgrade over Wikipedia.** SoS
feeds are **official and fresher** (minutes vs Wikipedia's editor lag). But commit with eyes open:

1. **Heterogeneous:** ~5 bespoke adapters (NC TSV, GA Clarity JSON/XML, OH CSV, MI TXT, TX JSON) — a
   real, ongoing-maintenance build, not a single source.
2. **Bot-blocking is the #1 risk:** GA/OH/MI returned 403 to automated access tonight. Before building,
   **verify each endpoint is reachable from the actual deployment environment** (GitHub Action /
   Streamlit Cloud IPs) — if they 403 there, the adapter is dead on arrival regardless of the data.
3. **No official calls:** states don't call races; calls must be inferred.
4. **Per-cycle discovery:** Clarity election IDs and SPA JSON endpoints change each cycle.

**Suggested path:** start with **NC** (cleanest, direct file download, most likely to work
programmatically), prove the end-to-end SoS → blend → dashboard path, then add **GA (Clarity)**,
**OH**, **MI**, **TX**. Keep **Wikipedia as the fallback** for states that block automated access or
lack a feed (NH, ME). This makes `ResultsSource` genuinely multi-source: SoS where it works, Wikipedia
where it doesn't, DDHQ if licensed.

### Verification step before coding (recommended "Step E-0.5")
Confirm, from a browser and ideally from the deployment environment: NC `results_pct` file URL for
2026-11-03; GA Clarity base + current election ID; OH live-results host + download URL; MI results data
URL; TX ENR JSON endpoint. Any that 403 from the deploy environment drop to the Wikipedia fallback.
