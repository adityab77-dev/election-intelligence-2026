# GitHub Source Audit — Live Election-Results Upstream Sources

Prepared 2026-11-03 (election night). **Audit only — no code.** Goal: find what *free, real-time*
data feeds active 2026 election-night projects actually consume (ignoring their UIs), and whether we
can legally reuse them.

Method: GitHub repo search → extracted real URLs from each repo's **source code** (not README prose)
→ **confirmed the key endpoints live** tonight.

## Repos audited

| Repo | Data Source (upstream) | Free? | Real-Time? | Reusable? |
|------|------------------------|:---:|:---:|:---:|
| `AyushMahajan06/ElectionNightViewer` | **NYT** elections JSON (`static01.nyt.com/elections-assets/…/results-senate.json`) | ✅ public CDN | ✅ | ❌ **No** — NYT ToS, AP-sourced |
| `earlsimms/mo-election-night-2026` | **State Clarity feeds** (`electionresults.<state>.gov/<ST>/<id>/…`) incl. `electionresults.iowa.gov/IA/127077/`; MN files | ✅ | ✅ | ✅ **Yes** — official state data |
| `Adam-Hubbs/utah-votes-2026` | **Utah SoS JSON API** (`electionresults.utah.gov/results/public/api/…` + CDN `export-*.json`) | ✅ | ✅ | ✅ Yes — official |
| `danieltheprompter/nv-election-2026` | **NV SoS "Vivid" JSON** (`nvsos.gov/vivid/data/*.json`) + Washoe county | ✅ | ✅ | ✅ Yes — official |
| `elawson360/indiana-results` | (no data endpoint found in source) | — | — | — |

## Confirmed upstream sources (exact endpoints)

### 1. Clarity / Scytl — the key find (free, official, legal, machine-readable)
Many states publish results on the **Clarity/Scytl** platform at a predictable JSON path:

```
https://electionresults.<state>.gov/<ST>/<electionID>/current_ver.txt   -> version
https://electionresults.<state>.gov/<ST>/<electionID>/<ver>/json/en/summary.json
   (also /xml/en/detail.xml, /reports/detail.zip for CSV)
```

**Confirmed live tonight — Iowa:** `electionresults.iowa.gov/IA/127077/current_ver.txt` → `384555`;
`.../384555/json/en/summary.json` → **HTTP 200, 225 KB JSON** whose first record is the
**"United States Senate"** race. **Not bot-blocked from an automated client.** One Clarity adapter
(parameterised by base URL + election ID) covers *every* Clarity state.

> Nuance: **state-hosted** Clarity (`electionresults.<state>.gov`) was reachable; the central Scytl
> host (`results.enr.clarityelections.com`, used by GA) returned **403** to automated clients earlier —
> prefer the state-hosted URL where one exists.

### 2. NYT elections feed — free & complete, but NOT reusable
`https://static01.nyt.com/elections-assets/pages/data/2026-11-03/results-senate.json` → **HTTP 200,
1.1 MB JSON, every Senate race.** Publicly reachable (CDN, no key, no bot-block) and real-time — but
it is **NYT's proprietary, AP-licensed compilation**; their Terms of Service prohibit scraping/reuse.
Use it only as a **private cross-check**, never in a public product.

### 3. State SoS JSON APIs (official, free, reusable, per-state format)
- Utah: `electionresults.utah.gov/results/public/api/elections/Utah/General11032026/data`
- Nevada: `nvsos.gov/vivid/data/ballot-seed.json`, `turnout-seed.json`
- (plus the Clarity states above, and NC's `dl.ncsbe.gov` files from the prior report)

## Legal assessment
- **Official government results** (Clarity state feeds, SoS JSON APIs, NC files) are **public-record
  facts** — freely reusable with attribution. ✅
- **NYT / AP** data is a **licensed, copyrighted compilation** under restrictive ToS — **not reusable**
  in a public product, regardless of being reachable. ❌
- Reachability ≠ permission: the hobby repos using NYT are technically violating ToS (tolerated only at
  hobby traffic).

## Mapping to our 8 battlegrounds

| State | Best free + legal source | Confirmed? |
|-------|--------------------------|:---:|
| **IA** | **Clarity** `electionresults.iowa.gov/IA/127077` | ✅ **live JSON, Senate present** |
| **GA** | Clarity (`results.enr.clarityelections.com/GA/<id>`) | Platform confirmed; central host may 403 → verify |
| **NC** | `dl.ncsbe.gov` result files | Portal reachable (prior report) |
| **OH / MI / TX** | Own systems (ohiosos / mielections / results.texas-election) | Per-state; not Clarity |
| **NH / ME** | Weak — fall back to Wikipedia | — |

## Recommendation
**Build a `ClarityResultsSource` first** — it is confirmed **free, official, legally reusable,
machine-readable JSON, and not bot-blocked** (Iowa proven tonight), and a *single* adapter covers
multiple states (IA now; GA and others via the same JSON shape). Then add **NC** (file download).
Keep **Wikipedia as the fallback** for non-Clarity / weak states (NH, ME), and use **NYT only as a
private validation reference** (never shipped). This is a materially better path than Wikipedia for
the states it covers — and the Clarity discovery means it is far less per-state work than feared.

Suggested next step (no code): a short "Clarity probe" to pin the **election IDs** for each Clarity
battleground (IA = 127077 confirmed; find GA's), then build `ClarityResultsSource`.
