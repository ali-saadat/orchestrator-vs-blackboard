# Paper plan — "Same Agents, Different Deals: Isolating the Effect of Coordination Architecture on Outcomes in LLM Multi-Agent Negotiation"

*Drafted 2026-07-05 from a 5-agent research pass (novelty scan, venue deadlines
[all dates verified on official CFP pages], rigor standards, publishing logistics).
Working title intentionally states the claim; refine later.*

---

## 1. The honest novelty verdict

**Already taken (do not claim):**
- "Topology affects MAS performance" as a headline — MacNet (ICLR'25), GPTSwarm
  (ICML'24), DyLAN (COLM'24), AgentPrune (ICLR'25), MASS (ICLR'26).
- "First controlled blackboard vs supervisor comparison" — taken by
  arXiv:2510.01285 (Google/UMass; blackboard vs master-slave, identical helper
  agents, +13–57% on data-science tasks) and LbMAS (arXiv:2507.01701) on
  reasoning. Both on **verifiable, ground-truth tasks**.
- "Standardized harness across architectures" in generic form — MAFBench
  (arXiv:2602.03128).
- Orchestration-pattern benchmarking incl. supervisor + hybrid, multi-model,
  cost-accuracy — arXiv:2603.22651 (financial document processing).

**Still open (the paper lives here — a conjunction, defensible as a whole):**
1. **Mixed-motive / negotiation domain** × coordination topology. Every
   controlled topology comparison found is on cooperative verifiable tasks.
   MARBLE (ACL'25) has both ingredients but never crosses them under strict
   invariance, and reports milestone KPIs, not payoff distributions.
2. **Strict invariance protocol**: identical agent prompts, tools, decision
   authority and termination gate across topologies — stricter and more
   auditable than 2510.01285. Our FairnessContract already fingerprints this.
3. **The deterministic-rules control condition** (hard rules): proves the
   harness attributes ZERO outcome variance to topology by construction, so
   any free-mode outcome difference is caused by coordination. No published
   paper has this calibration step. This is our methodological signature.
4. **Outcome DISTRIBUTIONS as primary endpoint**: deal VALUE, surplus split,
   who-wins asymmetry, violation rate — not deal rate (TERMS-Bench,
   arXiv:2605.13909, shows deal rate saturates on frontier models).
5. **Crossed ablations nobody has**:
   - topology × transcript-window size (memory) → close rate, over-concession,
     self-contradiction/invalid-move rate ("hallucination"). Hallucination
     Cascade (arXiv:2606.07937) varied chain depth, not window, not topology.
   - topology × privacy leakage of private reservation values. AgentLeak
     (arXiv:2602.11510) found 68.8% internal-channel leakage but evaluated
     ONLY coordinator-worker and explicitly did not vary topology. Terrarium
     (arXiv:2510.14312) provides infrastructure, no systematic comparison.

**Threats reviewers will raise (pre-empt in the design):**
- *"Single-agent matches multi-agent on negotiation"* (arXiv:2502.16242
  reproducibility study) → include a single-LLM-simulates-all-parties baseline
  and a compute-matched comparison (per "Should we be going MAD?" ICML'24 and
  Kapoor et al. "AI Agents That Matter", TMLR'24).
- *"Prompts dominate topology"* (MASS) → the invariance protocol must be
  airtight and documented (prompt diffs = ∅ across topologies; publish the
  fingerprint check).
- *"n=1 anecdotes"* → 100 seeds per headline cell (field norm is 3–5 repeats;
  we exceed it by 20×; temperature fixed and reported, snapshots pinned).

## 2. Research questions & hypotheses

- **RQ1 (calibration/control).** Under deterministic decision rules, do
  topologies differ in outcome? *Expected: no (by construction) — differences
  appear only in turns/tokens/cost.* This validates the harness.
- **RQ2 (main effect).** Under free negotiation (model decides every move),
  does coordination topology shift the outcome distribution? Endpoints: deal
  rate; deal value (candidate surplus vs employer surplus); Pareto efficiency;
  constraint-violation rate; turns/tokens/cost.
- **RQ3 (memory).** Transcript window w ∈ {0, 2, 6, 12, full} × topology.
  Hypotheses: w=0 → near-zero closes (validated already, n≈5); moderate w →
  max closes; large/full w → more self-contradiction and anchoring drift
  (inverted-U). Metrics: close rate, invalid-move rate, own-constraint
  violations, concession asymmetry.
- **RQ4 (privacy/security).** Give each agent a PRIVATE brief (reservation
  values, BATNA). Measure leakage into other agents' visible context per
  topology (blackboard broadcasts by design; supervisor compartmentalizes but
  paraphrases). Optional adversarial arm: one persuasive bad-faith agent →
  outcome swing per topology (hierarchy damps influence per arXiv:2408.00989).
- **RQ5 (generalization).** Does the topology effect transfer across domains?
  ≥3 mixed-motive scenarios (below) + one cooperative verifiable anchor task.
  Analyze topology × domain interaction: is the effect case-specific or
  general? (This answers the "cases or domain or generalizable" question
  empirically rather than rhetorically.)

## 3. Experimental design

**Factors**
- Topology: orchestrator / blackboard / hybrid (+ single-LLM baseline).
- Rules: deterministic control / free negotiation.
- Transcript window: {0, 2, 6, 12, full} (free mode only; 6 = current default).
- Scenario: job-offer (ours) · buyer-seller price (NegotiationArena-comparable)
  · multi-issue resource split (LLM-Deliberation-style, scorable) ·
  [anchor: one cooperative task for continuity with prior work].
- Model: Haiku 4.5 · Sonnet 5 (pinned snapshots, temperature stated) · one
  open-weights model (e.g. Qwen or Llama via local/hosted) for reproducibility.

**Scale.** 100 seeds per headline cell (topology × scenario × model, free
mode); 25–50 for ablation cells; power analysis in appendix. Rough cost: a free
run ≈ 10–50 calls ≈ $0.005–0.02 (Haiku); full grid ≈ low hundreds of dollars.
Feasible on a personal budget; Sonnet cells dominate cost.

**Statistics** (per Miller, "Adding Error Bars to Evals", arXiv:2411.00640 —
the de-facto standard): mean ± SE with bootstrap 95% CIs; PAIRED comparisons
across topologies on identical seeds/scenarios; Mann-Whitney U / Kruskal-Wallis
+ Cliff's delta for distributional claims; Holm correction; report ALL runs
(no cherry-picking); WORM logs + cassettes published for every run.

**Repo build list** (≈2–3 weeks of evenings)
1. `ovb study` batch runner: config grid → parallel runs → JSONL results;
   resumable; seed-stamped.
2. Scenario registry (already on IMPROVEMENTS.md roadmap) + 2 new scenarios
   with deterministic-rule variants (the control condition requires each
   scenario to have a fixpoint protocol).
3. Metrics module: surplus/utility per agent, Pareto check, violation
   detector, leakage detector (regex + LLM-judge with human-validated sample,
   report agreement à la MAST's κ).
4. Private-brief support in KnowledgeSource (per-agent secret system-prompt
   section) + leakage instrumentation on every visible context.
5. Open-weights LLM client (OpenAI-compatible endpoint).
6. Transcript window as a config knob (currently hardcoded 6).
7. Analysis notebook → all figures reproducible from JSONL.

## 4. Venue ladder (dates verified on official pages, 2026-07-05)

| # | Venue | Deadline | Status | Role in plan |
|---|-------|----------|--------|--------------|
| 0 | ~~AAAI-27~~ | abstract **Jul 21, 2026**, paper Jul 28 | CONFIRMED | **Skip** — 3 weeks away; a rushed submission burns the idea at a 20%-acceptance venue |
| 1 | **NeurIPS 2026 workshop** (list announced **Jul 11, 2026**; agent/MAS workshop near-certain) | papers ~**Aug 29, 2026** | CONFIRMED (suggested date) | **First target**: 4–9 page non-archival paper = peer feedback without burning main-track eligibility; workshops Dec 11–12 (multi-site incl. San Diego + Mexico City) |
| 2 | **AAMAS 2027** (Hanoi, May 3–7) | abstract ~Oct 1, paper ~**Oct 8, 2026** | official says "Oct 2026 (TBC)"; est. from 2026 pattern | **Main submission, best topical fit** — THE multi-agent venue; full paper w/ rebuttal |
| 3 | **ICLR 2027** (West Coast NA) | ~Sep 19 abstract / **~Sep 24, 2026** paper | ESTIMATED (2026 pattern; CFP pending) | Main-track stretch goal if the study is done by mid-Sep; first-time-author reviewer-duty exemption confirmed |
| 4 | ARR **Oct 12, 2026** cycle | Oct 12, 2026 | CONFIRMED | NLP framing (negotiation dialogue) → NAACL/ACL 2027; ACL abolished the anonymity period (friendliest to our public repo) |
| 5 | **ICML 2027** | ~late Jan 2027 | ESTIMATED (2026: abstract Jan 23) | Full-rigor resubmission with workshop feedback folded in |
| 6 | **COLM 2027** | ~late Mar 2027 | ESTIMATED (2026: Mar 26/31) | LLM-native venue, strong fit, good acceptance culture |

**Recommended sequence:** Jul–Aug: build + run study → **NeurIPS'26 workshop
(Aug 29)** → incorporate feedback in Sep → **AAMAS 2027 (Oct 8)** as the
archival main submission (topical home; May Hanoi conference) — optionally
gamble on **ICLR 2027 (Sep ~24)** instead if results are strong and writing is
ready; if rejected, **ICML/COLM 2027** with the reviews addressed. Post to
arXiv under real name at workshop time (policy-safe everywhere; ACL has no
anonymity period at all).

## 5. Logistics facts (verified)

- **No affiliation required** anywhere; OpenReview profile with career history
  suffices. Precedent: Andreas Madsen, independent researcher → ICLR spotlight.
- **Double-blind vs our public repo/Medium post**: existing public artifacts
  are explicitly fine (NeurIPS: "will not result in rejection"; ICLR allows
  arXiv preprints; ACL abolished the anonymity period Feb 2024). Rules during
  review: submission PDF + code anonymized (anonymous GitHub copy, no
  real-name links), self-cite in third person, never say "under review at X",
  freeze promotion of the submission itself.
- **Costs**: submission free everywhere; on acceptance ~$375–1000 registration
  (NeurIPS requires one in-person author; ICML 2026 made attendance optional).
- **Reviewer duty**: ICLR requires a qualified author-reviewer per submission
  BUT first-time authors are exempt ("we encourage submissions from
  researchers new to ICLR").
- **Hiring calculus**: research-SCIENTIST roles (Meta/GDM) want first-author
  main-track papers and usually a PhD; research-ENGINEER roles don't require
  publications (they help). Anthropic explicitly values independent research
  and open-source. Workshop papers are "signal amplifiers, not signals";
  main-track NeurIPS/ICML/ICLR/ACL/AAMAS is the credential. Realistic framing:
  one strong main-track paper + this open-source harness + the write-ups is a
  credible applied-scientist/RE portfolio, not an RS shortcut.

## 6. Rigor checklist to build into the paper from day one

- Pin model snapshots + temperature in every table; 100 seeds/headline cell;
  mean ± SE + bootstrap CIs; paired stats; effect sizes.
- Single-agent AND compute-matched baselines (the two canonical MAS-paper
  killers if missing).
- NeurIPS-style reproducibility checklist even for AAMAS; publish WORM logs,
  cassettes, configs, and the exact FairnessContract fingerprints.
- LLM-judge components (leakage detector) validated against human labels with
  reported κ (MAST set the bar at κ≈0.8).
- Report negative results honestly — RQ1 finding "nothing" is the point.

## 7. Next actions (in order)

1. **Jul 11**: NeurIPS 2026 workshop list drops — pick the target workshop.
2. Build the study harness (§3 build list) — keep every run cassette-recorded.
3. Pilot: 10 seeds × 3 topologies × job-offer × Haiku → sanity-check metrics
   and variance; size the full grid from pilot variance.
4. Full grid + analysis + 4–9 page workshop paper by ~Aug 22 (buffer week).
5. Decide ICLR-vs-AAMAS by Sep 15 based on result strength + writing state.
