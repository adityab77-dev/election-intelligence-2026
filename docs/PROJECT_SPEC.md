Solo one-week build
Oct 28, 2026 · @AD
Recommendation
Build it as one plain Python process plus one dashboard process, sharing a single DuckDB file. Use one direct Claude API call for narration. Leave LangGraph out of the numeric pipeline entirely. Optionally add a tiny read-only MCP server so you can question the live model from Claude Desktop on election night.
The reason is simple: the forecasting loop is deterministic math on a fixed schedule (fetch, project, simulate, compare, alert). It has no branching decisions for an agent to make. Every extra framework adds a failure point you'll be debugging alone at 1 am.
Time is the real constraint. Today is Oct 28, so you have about four build days before Nov 2. That favors tools you already know (Python, pytest, Playwright) over learning a graph runtime.
Target: 5 moving parts, 1 machine, 1 data file.
Comparison: plain Python vs. LangGraph + MCP
Plain Python wins on almost every axis that matters for a one-week, one-person run. LangGraph + MCP wins only on interactive, open-ended questioning.
Dimension	1. Plain Python services	2. LangGraph + MCP
Moving parts	2 processes (worker + dashboard), 1 DB file	Graph runtime, checkpointer store, 1+ MCP servers per data domain, LLM in most steps, plus dashboard
Build time for you	~3-4 days	~6-8 days, including learning the graph's state, checkpoint and MCP transport details
Determinism	Same inputs give the same numbers; seeded simulations replay exactly	Any LLM node adds run-to-run variation; graph retries can re-order work
Latency per refresh	Under 2 s (fetch-bound)	Adds 2-20 s per LLM hop; MCP adds a process boundary on every call
Debugging at 1 am	Stack trace, a log line, pytest	Trace across graph nodes, tool calls, model output; needs LangSmith or similar to see well
Failure modes	Feed down, bad data	Same, plus model timeouts, rate limits, tool-schema mismatches, MCP server crashes
Cost	Near zero plus a few dollars of narration calls	LLM cost on every node that uses one, every refresh
Testing	Normal unit and replay tests	Replay tests become fuzzy because LLM outputs vary
Ad-hoc analyst questions ("what if Democrats lose Maine?")	You write a query or a function call	Natural-language questions answered by an agent calling the simulator: genuinely better
Narrative with self-checking	One API call plus a Python validator and one retry	A small generate, validate, revise loop is clean in a graph
Human approval before publishing	A "pending" flag and a button in the dashboard	Built-in interrupt and resume: nice, but more than a solo dev needs
Reuse after Nov 8	Simple scripts, easy to archive	Better foundation if this grows into a multi-agent product
Where LangGraph adds value, and where it doesn't
Use an agent framework where the work is open-ended language and judgment. Keep it away from anything that produces a number.
Real value:
•	Analyst Q&A agent. "If Republicans hold Texas and Iowa, what are Democrats' odds?" An agent that turns the question into a conditional simulator call and explains the answer is a genuinely useful election-night tool. LangGraph handles the tool-call loop and conversation memory well.
•	Narrative self-check loop. Write, validate numbers against the attribution record, revise on failure, give up after two tries. This is a clean three-node graph.
•	News triage. Classifying wire headlines ("lawsuit filed," "polling hours extended") into event flags is a fair LLM job, and a graph can route by event type.
•	Interrupts for approval. Pausing before a projection is published is built in, if you ever add teammates.
Unnecessary complexity:
•	Ingestion. Polling a JSON feed every 60 seconds is a loop, not a graph. MCP servers wrapping each feed add processes and a protocol layer with nothing gained.
•	Projection and simulation. These must be deterministic, fast and replayable. An LLM step here is a correctness risk, not just overhead.
•	Scheduling and state. LangGraph checkpointers duplicate what one DuckDB table of runs already gives you.
•	Alerting. Threshold rules are if statements. An agent deciding whether to alert you is slower and less predictable.
Where MCP fits. Not as plumbing between your own components. Its real job here is a thin read-only server over your DuckDB file, exposing a few tools (current control odds, state table, run a conditional scenario, explain last change). Then you can ask questions from Claude Desktop without building a chat UI. Treat it as an optional sixth part, outside the critical path: if it breaks, the forecast keeps running.
Rule of thumb: if a step's output is a number someone might quote, it's plain Python. If its output is words for a human, an LLM may help.
Recommended solo architecture
One worker is the only writer; the dashboard and the optional MCP server only read. A crash in either reader never touches the forecast.
 
solo architecture · worker, data file, dashboard, Slack, optional MCP
The worker runs the same five steps on every tick. Its run is triggered by the scheduler (every 60 s on election night, 15 min otherwise) or by a new snapshot in a Tier-1 state. Each run is one row in DuckDB with its inputs hash and seed, so any number on screen can be reproduced.
What gets cut from the full design
The methodology stays the same; only the plumbing shrinks.
Full design	Solo replacement	What you give up
Kafka / Kinesis event log	Append-only snapshots table in DuckDB	Multi-consumer streaming (not needed)
Postgres hot store + warehouse	Same DuckDB file, Parquet export nightly	Concurrent writers (only one writer exists)
Prefect / Dagster	APScheduler inside the worker	Workflow UI
Stan / PyMC hierarchical model	Precision-weighted poll + fundamentals blend, fixed state correlations from a covariance matrix	Partial pooling for thinly polled states; widen their variance by hand
County-level live model for every state	County model for Tier-1 states only; state-level for the rest	Some accuracy in low-leverage states
Dual result feeds everywhere	One primary feed + manual SoS spot-checks for Tier-1	Automatic cross-feed reconciliation
Grafana, Prometheus, Sentry	A feed-health panel in the dashboard + Slack on errors	Historical metrics
PagerDuty, SMS tiers	One Slack channel with phone push for P1	Escalation policy
Analyst review queue	Projections shown as "pending" until you click approve	Multi-person workflow
LLM narration on every move	Narrate only moves of 3+ points, or label changes	Commentary on small wiggles
Keep, no matter what: correlated Monte Carlo, the vote-method model for outstanding ballots, stale-feed widening, and the replay test. Those are where forecasts actually go wrong.
Build plan and solo runbook
Four build days are enough only if each day ends with something runnable.
Build (Oct 29 to Nov 1).
1.	Oct 29: DuckDB schema (races, units, snapshots, polls, runs, alerts); poll and fundamentals loader; pre-election blend; Monte Carlo with national + 2 demographic factors. End of day: a control probability prints.
2.	Oct 30: results adapter for one feed; county projection for Tier-1 states; prior fade; stale-feed widening. End of day: replay of a 2022 night runs end to end.
3.	Oct 31: Streamlit dashboard (gauge, seat histogram, Tier-1 board, change log, feed health); Slack alerts; attribution by state swap.
4.	Nov 1: narration call + validator; House rating simulation; optional MCP server; full replay at 5× speed; fix whatever breaks. Freeze code at midnight.
Run (Nov 2 to 8).
•	Run the worker on a small cloud VM (one vCPU and 2 GB is plenty) inside tmux, with systemd restart on crash. Run the dashboard on the same box. Keep your laptop as a cold standby with the same code and a copy of the DuckDB file.
•	Back up the DuckDB file to object storage every 15 minutes on election night.
•	Nov 3 evening: stay at the dashboard from first poll closings (7 pm ET) through about 2 am ET. Set phone push only for P1 alerts, so you can step away.
•	Nov 4 to 8: sleep at night; the worker keeps polling every 5 minutes, and Slack pings you only on label changes or control moves over 5 points.
•	Keep a one-page "break glass" note: how to pin a state, mute a feed, restart the worker, and switch to the laptop.
Pre-flight checks before Nov 2:
•	☐ Replay a 2022 night with no manual help
•	☐ Kill the worker mid-replay; confirm it resumes cleanly from the DuckDB state
•	☐ Feed returns garbage; confirm quarantine and a Slack alert
•	☐ Narration validator rejects a planted wrong number
•	☐ Results feed license terms confirmed for your intended use

2026 Senate Control Intelligence System — Design & Methodology
Oct 28, 2026 · @AD
Executive summary
The system's core output is one number with a story behind it: P(Republican Senate control), updated continuously from Nov 2 to Nov 8, plus the ranked paths that produce each majority. Race calls are an input, not the product.
Design principles:
•	Chamber first, seats second. Every seat probability is consumed by a correlated Monte Carlo layer; the headline is the share of simulations where each party controls the chamber (Republicans need 50 seats because they hold the VP tiebreak; Democrats need 51).
•	Correlation is the model. Polling and turnout errors are shared across states. A model that treats seats as independent will badly overstate a favorite's control odds.
•	Two regimes, one engine. A pre-election prior regime (polls, fundamentals, markets) hands off to a live regime (reported votes vs. expected vote) that steadily overwhelms the prior as counts mature.
•	Explainability is a requirement, not a feature. Every probability change is decomposed into named drivers (which state, which data, how many points) so the narrative layer can say why in plain English.
•	Probabilistic language only. No "will win." Outputs carry intervals and calibrated rating labels.
Standing outputs, refreshed on every model run:
Output	Example form
Senate control probability	R 61% / D 39% (80% interval on R seats: 49 to 54)
Most likely combined outcome	R Senate + D House (joint probability shown)
Critical states	Top 3 by control leverage, recomputed each run
Seat distribution	Histogram of R seats across simulations
Path list	Top 5 seat combinations that deliver each majority
Change log	Last move in control odds and its top 3 drivers
The example numbers above illustrate format only; they are not a forecast.
Senate math and current landscape
Republicans enter at 53-47, so Democrats need a net gain of four seats; Republicans keep control at 50 because the vice president breaks ties (Newsweek, Political Wire / Crystal Ball). 35 seats are up, including specials in Florida and Ohio (270toWin). Election Day is Nov 3, 2026.
Your framing of the two paths matches the arithmetic: Republicans win by defending; Democrats must hold everything and flip several red seats. One update to the tier list, though. The battlefield has moved since spring, so tiers should be an output of the model, not a fixed input.
•	As of Oct 14, Sabato's Crystal Ball listed five toss-ups, all Republican-held: Kansas, Iowa, Maine, Ohio and Texas (Political Wire).
•	North Carolina was moved to Lean Democratic in June (Newsweek), so it is now more of a Democratic must-hold pickup than a toss-up.
•	Cook had Texas, Iowa and Alaska as toss-ups by September, alongside North Carolina, Maine and Ohio as GOP seats at risk (Political Wire / NY Post).
•	Prediction markets were pricing Republican control around 54 to 56% in August (Octagon market summary); treat that as stale until re-pulled.
Recommended starting tiers (re-derived nightly by the leverage metric in the decisive-states section):
Tier	States	Why
1: control-deciding	Maine, Ohio, Texas, Iowa, Alaska, Kansas	Rated toss-ups by at least one major rater, all R-held
1b: must-hold / must-flip anchors	North Carolina (R-held, leans D), Georgia, Michigan, New Hampshire (D-held)	A loss here collapses the trailing party's paths
2: watch	Nebraska, Florida special, Minnesota	Tail scenarios; promote if leverage rises
Counting rules that matter inside the Nov 2-8 window:
•	Georgia requires 50% plus one; a runoff would push that seat past Nov 8. Model it as a third state: "unresolved, goes to December runoff."
•	Maine uses ranked-choice voting. If no one clears 50% on first choices, the final tabulation can take about a week. Model first-round vote and RCV transfer separately.
•	Alaska uses ranked-choice and accepts mailed ballots arriving days after Election Day, so its final result usually lands after Nov 8. Expect Alaska to stay probabilistic at the end of the operating window.
The system must therefore report control as "decided" or "pending specific seats," not force a call.
Data sources, weights and refresh cadence
Weights are not fixed. They shift by phase: before polls close, polling and fundamentals dominate; once votes arrive, reported results plus expected-vote estimates dominate and everything else becomes a prior.
Source	Examples	Pre-election weight	Live weight (counts >50% in)	Refresh: Nov 2-3 day	Refresh: Nov 3 night	Refresh: Nov 4-8
Official results feeds	AP Elections API, Decision Desk HQ, state SoS / county result pages	n/a	Highest (0.6 to 0.85)	n/a	30-60 s	2-5 min
Expected-vote / turnout models	AP or DDHQ expected vote, own county model	n/a	High (drives uncertainty)	n/a	1-2 min	10 min
State polling	Rater-graded pollsters, poll averages	Highest (0.40 to 0.55)	Low, prior only	1 h	frozen at 6 pm local	frozen
Fundamentals	Generic ballot, presidential approval, 2024 margin, incumbency, candidate quality	0.15 to 0.25	Prior only	daily	frozen	frozen
Early / mail vote data	State absentee files, party-registration splits	0.05 to 0.10	Used to model late-count drift	2-4 h	n/a	daily
Prediction markets	Kalshi, Polymarket, PredictIt	0.05 to 0.10 (as a check)	Monitor only, never input	5 min	1 min	5 min
Expert ratings	Cook, Sabato, Inside Elections	0.05 (as a prior anchor)	none	daily	none	none
Fundraising	FEC quarterly and pre-general reports, ad spending	0.00 to 0.05 (folded into candidate quality)	none	static	none	none
Historical voting	County results 2016-2024, swing elasticity, vote-method shares	Structural, sets correlation and county baselines	Structural	static	static	static
Demographics	ACS county shares (education, age, race, density)	Structural, sets correlation	Structural	static	static	static
News / wire	AP, Reuters, state political reporters, SoS press	Event flags only	Event flags (lawsuits, extended hours)	5 min	1 min	5 min
Why this order:
•	Raw votes beat everything once they exist, but only interpreted against which votes are counted. 40% in from a rural county tells you little about the final margin. That is why the expected-vote model matters as much as the count itself.
•	Polls get the most pre-election weight because they are the only direct measure of the current race. Weight each pollster by historical error and house effect, and decay by age.
•	Markets are a calibration check, not an input. They react to the same data you have, plus noise and thin liquidity. Use divergence from markets as an alert, not a signal.
•	Fundraising is mostly already in the polls. Late money matters mainly as a candidate-quality proxy in low-information races.
•	Freeze pre-election inputs at each state's poll close. After that, any new poll or market move is contaminated by early results.
Architecture overview
Seven layers in one pipeline: every output, from the control gauge to an alert, is computed from the same simulation run, so numbers never disagree across screens.
 
system architecture · 7 layers
The forecasting engine hands its per-state prior to the live probability engine at each state's poll close; both feed the same Monte Carlo layer, whose results drive ratings, narration and alerts.
Data ingestion layer
Ingestion turns many noisy feeds into one versioned, county-level event stream that the engines can replay.
Pattern. One adapter per source, all writing to an append-only event log (Kafka or Kinesis), partitioned by state. Nothing is overwritten: every result snapshot, poll and market tick is kept with its source timestamp and ingest timestamp. This lets you replay election night and rebuild any past probability exactly.
Canonical entities.
Entity	Key	Main fields
Race	state + office + special flag	rating, candidates, counting rules (runoff, RCV)
Reporting unit	FIPS county (town for ME/NH)	registered voters, 2024 votes by method, demographics
Result snapshot	unit + source + timestamp	votes per candidate, ballots counted, vote method if given
Expected vote	unit + timestamp	expected total ballots, interval, source
Poll	pollster + field dates + population	margin, n, LV/RV, mode, sponsor
Market tick	venue + contract + timestamp	price, volume, spread
Event	type + state	lawsuit, extended hours, tabulator outage, AP call
Reconciliation rules.
•	Pull two independent result feeds per state (for example AP plus DDHQ or the SoS page). Prefer the feed with the most recent valid snapshot.
•	Reject a snapshot if vote totals go down without a correction flag, if a county exceeds 110% of registered turnout, or if the two feeds differ by more than a set tolerance. Quarantine it and alert.
•	Track vote method (Election Day, early in-person, mail) wherever the state reports it. Late-count drift ("blue shift" or "red shift") is driven by method mix, and it varies by state.
•	Make every adapter idempotent and record source lag. A stale feed must lower confidence, not freeze the number silently.
Storage. Hot store for current state (Redis or Postgres), columnar warehouse for history and backtests (BigQuery, Snowflake or DuckDB on Parquet), object store for raw payloads.
Resilience. Run warm standby adapters, a manual-entry path for county results scraped by analysts, and a kill switch that pins any one source to "ignored" without a deploy.
Forecasting engine: the composite pre-election model
The engine produces, for each race, a distribution of the two-party margin (D minus R, in points), not a single number. Model the margin, then derive win probability.
Step 1: Polling average per state. Each poll's weight is the product of four factors:
w_i = \underbrace{q_{\text{pollster}}}_{\text{historical accuracy}} \cdot \underbrace{\sqrt{n_i}}_{\text{sample size, capped}} \cdot \underbrace{e^{-\lambda \, \text{age}_i}}_{\text{recency}} \cdot \underbrace{\rho_{\text{LV}}}_{\text{likely-voter bonus}}
Subtract each pollster's estimated house effect first. Down-weight a single pollster so it cannot exceed about 25% of a state's average. Use a half-life of roughly 7 to 10 days this late in the race.
Step 2: Fundamentals prior per state. A regression fit on past midterms:
•	state partisan lean (2024 presidential margin vs. national),
•	national environment (generic ballot, presidential approval),
•	incumbency and candidate quality (prior office, scandal flags, fundraising share as a proxy),
•	midterm penalty for the president's party.
Step 3: Combine as a Bayesian blend. Treat the fundamentals as the prior and the polling average as the observation, each with its own variance. The posterior mean is a precision-weighted average:
\mu_{\text{state}} = \frac{\mu_{\text{poll}}/\sigma^2_{\text{poll}} + \mu_{\text{fund}}/\sigma^2_{\text{fund}}}{1/\sigma^2_{\text{poll}} + 1/\sigma^2_{\text{fund}}}
Thin polling (Kansas, Alaska) means a large poll variance, so fundamentals carry more weight automatically. Heavily polled states (Texas, Michigan, Georgia) lean on polls.
Step 4: Hierarchical pooling. Fit states jointly (a Stan or PyMC model) so a shift in Iowa polling nudges Kansas and Nebraska, which share demographics and lean. This is what lets thinly polled states borrow strength.
Step 5: Markets and ratings as checks. Don't average them in by default. Compute the gap between your seat probability and the market's. If it exceeds about 15 points in a Tier-1 state, flag it for analyst review. Either you know something the market doesn't, or your inputs are stale.
Step 6: Output. Per race, a margin mean and standard deviation, plus a list of named drivers and their contribution in points. The drivers feed the narrative layer.
Special cases:
•	Maine and Alaska (RCV): model first-round shares for each candidate, then a transfer matrix for eliminated candidates' ballots, with its own uncertainty.
•	Independents (for example in Nebraska): model them as a separate candidate and set a caucus-alignment probability for chamber counting.
•	Georgia: output P(any candidate over 50%) alongside P(win), because a runoff changes what "decided" means.
Probability engine: live updating on election night
The live engine estimates the final margin in each state from votes counted so far plus a model of the votes still out. The prior from the forecasting engine fades as the count matures.
County-level projection (the core loop). For every reporting unit c in a state:
1.	Estimate expected total ballots E_c and the share already counted r_c (from expected-vote feeds, checked against your own turnout model).
2.	For counted ballots, observe the margin m_c. For outstanding ballots, predict the margin of what's left, which is not the same as what's in. Base it on the vote method still out (mail vs. Election Day) and that county's 2024 method-level split, shifted by the swing observed so far in similar counties.
3.	Project the county's final margin as a weighted blend of the counted and predicted outstanding votes.
4.	Sum to the state level.
Learning the swing from early counties. As counties finish, compute swing vs. 2024 (or vs. the pre-election expectation) and regress it on demographics: education share, density, race, age. Apply that fitted swing to counties not yet reporting. This is the "needle" approach, and it is the single most informative live signal. Fit it nationally and per state, then partially pool the two.
Cross-state learning. States close at different times (Georgia and New Hampshire early; Texas and Iowa later; Alaska last). Feed the national swing estimate from early states into the prior for late states. This is how an early Georgia or New Hampshire result should move your Iowa and Texas numbers before they report a single vote.
Fading the prior. Let the prior's weight decay with expected-vote completeness, not with time:
\mu_{\text{final}} = (1 - \alpha) \, \mu_{\text{live}} + \alpha \, \mu_{\text{prior}}, \qquad \alpha = (1 - \text{pct\_expected\_in})^{k}
With k around 2, the prior still matters at 30% in and is nearly gone by 80% in. Tune k on backtests.
Uncertainty shrinks with the outstanding vote, not with the leader's lead. The live standard deviation should scale with the number of uncounted ballots and with the uncertainty in their composition. A 2-point lead with 40% of mail ballots outstanding in a state with heavy late mail is less safe than it looks.
Guardrails.
•	Never let a single snapshot move a state by more than a set amount (say 15 points of probability) without a second confirming snapshot.
•	Treat AP or DDHQ race calls as a near-certain observation (P set to 0.995, not 1.0), so a retracted call can still be absorbed.
•	If a feed goes stale for more than 10 minutes during active counting, widen that state's interval instead of holding it.
•	Recount thresholds: if the projected margin is inside a state's automatic-recount band, output "likely recount" as a third state.
Monte Carlo simulation layer
The simulator turns per-state margin distributions into chamber outcomes by drawing correlated errors, then counting seats.
Error structure. Each state's simulated margin is its mean plus three error terms:
M_s = \mu_s + \underbrace{\varepsilon_{\text{nat}}}_{\text{shared by all}} + \underbrace{\boldsymbol{\beta}_s^{\top}\boldsymbol{\eta}}_{\text{demographic factors}} + \underbrace{\varepsilon_s}_{\text{state-specific}}
•	National error (one draw per simulation): a common polling miss in the same direction everywhere. Historical midterm Senate polling misses have often run 3 to 5 points; set its standard deviation from backtests.
•	Demographic factors (a few draws per simulation): for example a non-college-white factor and a Hispanic-voter factor. Each state's loading (β) comes from its demographic mix, so Texas and Ohio miss differently from Maine and New Hampshire.
•	State error: candidate-specific noise, larger for thinly polled states.
•	Use a Student-t (around 5 degrees of freedom) rather than normal for the national term. Fat tails stop the model from treating a wave as impossible.
Per-simulation steps.
1.	Draw national, factor and state errors.
2.	Compute each state's margin; for RCV states apply a sampled transfer matrix; for Georgia check the 50% rule.
3.	Assign winners; add the seats not up (Republicans hold 30+ non-contested seats; read the exact holdover count from the canonical race table, don't hard-code it).
4.	Apply caucus-alignment draws for independents.
5.	Determine control: R ≥ 50 means Republican control (VP tiebreak); D ≥ 51 means Democratic control. Record "undetermined pending runoff" when a Georgia runoff could decide it.
Scale. 50,000 to 100,000 simulations per run. Vectorized NumPy or JAX runs this in well under a second on one machine, so you can re-run on every snapshot. Fix the random seed per run ID for reproducibility.
Live mode. The same simulator runs on election night; the inputs simply change to the live engine's posterior. Called states are pinned. Correlation still matters: an outstanding-vote error in Maricopa-style mail-heavy counties is correlated with similar counties elsewhere.
Outputs per run.
•	P(control) for each party, with Monte Carlo standard error (should be under 0.3 points at 100k draws).
•	Seat histogram and median.
•	Path table: the most frequent seat combinations, grouped by which Tier-1 states each party won.
•	Conditional probabilities: P(D control | D wins Maine), P(R control | R wins Texas), and so on, for every Tier-1 state.
Uncertainty, confidence intervals and calibration
Report three kinds of uncertainty separately, because they shrink at different rates and confuse readers when blended.
Kind	Source	What shrinks it
Model (epistemic)	Polling error, fundamentals fit, correlation assumptions	Nothing before polls close; real votes after
Count (aleatory, live)	Ballots not yet counted, unknown method mix	Counting progress
Simulation	Finite Monte Carlo draws	More draws (negligible at 100k)
What to publish.
•	Seat count: median plus an 80% interval (10th to 90th percentile of simulated R seats). 80% is easier for a lay audience than 95% and is still honest.
•	State margin: mean plus an 80% interval in points.
•	Control probability: a point estimate, plus an "input sensitivity" band from re-running with the national-error standard deviation at 0.75× and 1.25×. If the band is wide, say the forecast is sensitive to how big a polling miss you assume.
Calibration (do this before Nov 2).
•	Backtest on 2014, 2018 and 2022 Senate races (and 2024 for live-mode drift), using only data available at the time.
•	Check reliability: of races given 70%, roughly 70% should have been won. Use a Brier score and a log-loss per tier.
•	Check interval coverage: the 80% interval should contain the actual margin about 80% of the time. If it covers 95%, your intervals are too wide; if 60%, too narrow and probably missing correlation.
•	Replay past election nights through the live engine using archived county snapshots. Measure how early it would have been right, and how often it flipped.
Common failure modes to guard against.
•	Treating states as independent (overconfident favorite).
•	Ignoring late-count drift by vote method (a lead that evaporates overnight).
•	Letting markets leak into inputs (circular confidence).
•	Over-trusting one prolific pollster in a thinly polled state.
Identifying genuinely decisive states
A close race is not the same as a decisive race. Kansas can be a toss-up and still matter little if Democrats only reach 51 in simulations where they already won Kansas-like states. Rank states by how much control depends on them, computed from the simulations.
Metric	Definition	What it tells you
Control leverage	P(R control | R wins s) − P(R control | D wins s)	How much one state swings the chamber
Tipping-point probability	Share of sims where s is the seat that crosses 50/51 when states are sorted by margin	Which state is most likely to be the majority-maker
Criticality	Leverage × P(race is within 3 points)	Leverage that is actually live
Expected info gain	Expected drop in control-probability variance once s is resolved	Which result to watch first tonight
How to use them.
•	The "Current critical states" list in the headline output = the top 3 by criticality, recomputed every run.
•	Promote a Tier-2 state to Tier-1 when its tipping-point probability exceeds about 8%; demote when it falls below 3% for 24 hours (hysteresis stops flicker).
•	On election night, sort the watch list by expected info gain and by expected time-to-resolution. An early-closing state with high info gain (Georgia, New Hampshire) is the first place to look.
•	Publish the conditional table: "If Democrats lose North Carolina, their control odds fall to X%." It is the most intuitive way to show which states hold up each party's path.
Given the current map, expect the Democratic path to show many must-win states (North Carolina, Michigan, Georgia, New Hampshire held; then most of Maine, Ohio, Texas, Iowa, Alaska, Kansas). Expect the Republican path to show high leverage spread across several toss-ups, each of which can end the Democratic path alone. The model should confirm or refute that, not assume it.
Rating transitions: when a toss-up becomes Lean or Likely
Ratings are labels on the win-probability scale, with hysteresis so a race does not bounce between labels on noise.
Label	Enter when P(leader wins) is	Exit (back toward toss-up) when it falls below
Toss-up	under 60%	n/a
Lean	60% or more for 2 straight runs	57%
Likely	80% or more for 2 straight runs	77%
Safe	95% or more	93%
Projected (live only)	99.5% or more, and outstanding vote cannot cover the gap at a 3-sigma composition error	never auto-exits; manual review
Two extra gates before any upgrade is published:
•	Interval gate. The 80% interval on the margin must not cross zero for Likely or higher. This stops a high mean with very wide uncertainty from looking safe.
•	Data-quality gate. On election night, at least one of: 50% or more of expected vote counted, or 3 or more large counties fully reported. Don't upgrade on one early batch.
Pre-election, the same thresholds apply on daily runs, with a 2-day persistence rule instead of 2 runs. Log every label change with its drivers, because each one triggers an alert and a narrative line.
Narrative layer: explaining changes in plain English
Every headline move is explained by attribution first, then words. Never let the text layer invent a reason the numbers don't show.
Attribution method. Between run t−1 and run t, swap in each state's new margin distribution one at a time (holding the rest at t−1) and re-simulate. The change in P(control) from each swap is that state's contribution. Shapley-style averaging over swap order makes the contributions sum to the total move. Do the same by data source within a state (new poll, new county batch, expected-vote revision).
Template, filled from the attribution record.
Republican Senate odds moved from [61%] to [67%] in the last hour. Most of that ([+4 pts]) came from [Texas], where [Harris and Tarrant counties finished counting Election Day votes] and the margin came in [2 points] better for [Republicans] than expected. [Maine] moved slightly the other way. The race to watch next is [Iowa], where about [40%] of the expected vote is still out.
Writing rules.
•	Lead with the direction and size of the change, then the one or two states that caused it.
•	Say why the data moved, not just that it did: which counties, which vote type, how it compared to expectation.
•	Use frequencies for intuition: "67% means Republicans keep control in about two out of three plausible outcomes."
•	Never say "will win" or "locked up" below the Projected threshold. Use "favored," "slight edge," "too close to call."
•	Flag uncertainty drivers out loud: "Most of Alaska's mail ballots won't be counted for days."
•	Suppress narration for moves under 2 points unless a rating label changed.
•	Use the same wording and structure for both parties' movements, so tone never signals a side.
LLM use. An LLM can turn the structured attribution record into prose, but constrain it: give it only the record, require every number in the output to exist in the record, and run an automated check that rejects text with unmatched numbers or certainty words. Keep a human editor on Tier-1 narration during peak hours.
Election-night monitoring and alert system
The monitoring layer answers three questions at a glance: where control stands, what just changed, and what to watch next.
Dashboard panels.
•	Control gauge: P(R) / P(D) with a sparkline since 6 pm ET.
•	Seat histogram, live.
•	Tier-1 board: one row per state with margin, % expected vote in, vote type outstanding, rating label, leverage, feed health.
•	Path tracker: which of each party's top paths are still alive, crossed off as states resolve.
•	Change log: the last 20 narrated moves.
•	Data health: feed lag per source, quarantined snapshots, disagreements between feeds.
Alert rules.
Severity	Trigger	Audience	Channel
P1	Control probability moves 5+ points in 15 min; a Tier-1 race changes label; a race is projected; control is mathematically decided	Everyone	Push + Slack + SMS to on-call
P2	State probability moves 10+ points; model vs. market gap over 15 points in a Tier-1 state; a Tier-2 state promoted to Tier-1	Analysts	Slack
P3	Feed stale over 10 min during counting; feeds disagree; snapshot quarantined; vote totals decreased	Engineering on-call	PagerDuty
Info	New county batch over 5% of a Tier-1 state's expected vote	Analysts	Dashboard toast
Noise control. Deduplicate repeat alerts for the same state within 10 minutes, batch P3 alerts, and require two consecutive runs before a P1 on probability moves (projections and decisions fire immediately).
Human in the loop. Model-driven projections go to an analyst review queue before publication. The analyst can approve, hold, or pin a state's input, and every override is logged with a reason.
Run cadence. Event-driven: any accepted snapshot in a Tier-1 state triggers a re-run, with a 30-second debounce. A full re-run of all states every 2 minutes as a backstop.
House module (lightweight)
The House needs 218 seats for a majority. Cook currently lists 43 competitive districts, including 22 toss-ups (NPR via KUOW). Mid-decade redistricting in several states has changed seat-by-seat baselines, so load 2026 district lines, not 2024 ones.
Method: rating-based simulation, not a full model.
1.	Start from a consensus rating per district (Cook, Sabato, Inside Elections), mapped to probabilities: Safe 99%, Likely 90%, Lean 72%, Toss-up 50%.
2.	Add one national swing term per simulation, plus a small per-district term, so House outcomes correlate with each other and with the Senate national error. That gives you a credible joint "R Senate + D House" probability.
3.	On election night, replace a district's prior with the AP or DDHQ call when it comes; for uncalled competitive districts, shift the probability with a simple margin-vs-expected-vote rule.
Outputs.
Output	Content
Control status	P(D majority), P(R majority), "called" when 218 is reached
National totals	Called seats D / R, projected median and 80% interval
Competitive districts	Table of the ~45 rated races with rating, margin, % in, call status
Majority projection	Median seats and the "magic number" each party still needs from uncalled races
Battleground states	Roll-ups for New York, California, Pennsylvania, Arizona and Michigan
Battleground state notes.
•	California and Arizona count slowly and see late-count shifts; expect many of their districts to stay uncalled through Nov 8. Show them as "pending" with a probability rather than forcing a number.
•	Pennsylvania cannot process mail ballots before Election Day, so early returns can be skewed by vote type.
•	New York and Michigan report faster; use them as early national-swing signals for the House roll-up.
Operating runbook (Nov 2-8), risks and validation
Runbook.
1.	Before Nov 2: finish backtests and calibration; dry-run the full stack on archived 2022 election-night snapshots at 1× and 5× speed; load final candidate lists, counting rules and 2026 House lines.
2.	Nov 2 (Mon): hourly pre-election runs; final poll and market pulls; publish the baseline forecast and the conditional table.
3.	Nov 3, day: freeze each state's pre-election inputs at its poll close; switch Tier-1 states to live mode one by one as they close; staff peaks from first closings through about 2 am ET.
4.	Nov 4: shift to late-count mode; re-weight by remaining vote type; begin tracking Maine RCV, Alaska mail and any Georgia runoff scenario.
5.	Nov 5-8: runs on every new batch plus a 15-minute backstop; daily written summary; explicitly report any seat expected to resolve after Nov 8.
Key risks.
Risk	Mitigation
Correlated polling miss larger than history	Fat-tailed national error; publish sensitivity band
Expected-vote estimates wrong (turnout surprise)	Two independent expected-vote sources; widen intervals when they disagree
Vote-method drift misread as swing	Model counted and outstanding ballots by method separately
Feed outage or bad data	Dual feeds, quarantine rules, manual entry, stale-feed widening
Control undecided at Nov 8 (Alaska, Maine RCV, Georgia runoff)	First-class "pending" state in outputs and narration
Narrative overstates certainty	Certainty-word filter, number-check, human editor
Perceived partisan tilt	Symmetric wording and alert thresholds; publish methodology
Validation checklist.
•	☐ Backtests show calibrated reliability curves per tier
•	☐ 80% interval coverage within 75-85% on backtests
•	☐ Full election-night replay completes without manual intervention
•	☐ Attribution contributions sum to the total move on every run
•	☐ Alert volume in replay stays under an agreed per-hour cap
•	☐ Holdover seat count and caucus rules verified against the official Senate roster
Sources (landscape facts in this doc; re-pull before Nov 2):
•	Political Wire: five Senate toss-ups, Oct 14, 2026
•	Political Wire: Crystal Ball rating changes, Jun 11, 2026
•	Newsweek: Ohio and Alaska move to toss-up
•	Newsweek: Democrats need net four seats
•	Political Wire: more GOP seats in play, Sep 6, 2026
•	270toWin: 2026 Senate forecasts
•	Octagon: Senate control market summary
•	NPR via KUOW: reading the 2026 House map
