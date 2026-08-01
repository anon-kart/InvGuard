# InvGuard mid-level benchmark (10 contracts) + 5-RQ ICSE plan

## 1. The 10 contracts (what they are and why)

Mid-level (36–56 LOC each), no comments (so the LLM isn't influenced), 2 per
vulnerability class. Every contract is **value-moving** so the exploit executor
can measure concrete impact, and every one is shaped to match what your
pipeline's attack templates extract.

| Contract | Class | Target fn | Template | LOC |
|---|---|---|---|---|
| bench_re_etherbank_withdraw     | Reentrancy (SWC-107)        | withdraw     | T1 | 56 |
| bench_re_rewardvault_redeem     | Reentrancy (SWC-107)        | redeem       | T1 | 48 |
| bench_ac_ownablevault_withdrawAll | Access control (SWC-105)  | withdrawAll  | T2 | 46 |
| bench_ac_configbank_setManager  | Access control (SWC-105)    | sweep        | T2 | 49 |
| bench_ur_refundpool_refund      | Unchecked return (SWC-104)  | refund       | T3 | 43 |
| bench_ur_payoutledger_payout    | Unchecked return (SWC-104)  | payout       | T3 | 47 |
| bench_of_tokensale_buy          | Overflow/underflow (SWC-101)| transfer     | T4 | 36 |
| bench_of_bonusvault_addBonus    | Overflow/underflow (SWC-101)| addBonus     | T4 | 42 |
| bench_to_piggybank_withdraw     | tx.origin auth (SWC-115)    | withdraw     | T5 | 40 |
| bench_to_guardedwallet_send     | tx.origin auth (SWC-115)    | send         | T5 | 40 |

These are exactly the **5 vulnerability classes your pipeline targets** — I read
the code: it has dedicated attack templates T1–T5 and (after the small patch
below) class-aware FixMaker repair for all five. Nothing here relies on a class
the pipeline can't handle (no delegatecall, no front-running, no bad-randomness
contracts — those would just produce empty results).

## 2. Your pipeline is class-specific, not generic — and what was missing

The attack side already supports all 5 (T1 reentrancy, T2 access-control,
T3 unchecked-return, T4 overflow, T5 tx.origin). The **repair** side
(class-aware FixMaker) only had instructions for 3: access_control,
unchecked_call, denial_of_service/bad_randomness (reentrancy uses the CEI
default). **tx.origin and overflow had attacks but no fix** — so I wrote
`patch_fixmaker_classes.py` to add those two branches (≤12 lines total). Apply it
or all four T4/T5 contracts will land in gate_rejected.

## 3. Install + run

```bash
cd "/home/kartik/Downloads/InvGuard-main (1)/InvGuard-main/InvGuard"

# a) drop the contracts in
cp bench_contracts/*.sol contracts/          # (from the unzipped folder)

# b) drop manifest + the fixmaker patcher next to run_batch.py
cp manifest_bench10.json .
cp patch_fixmaker_classes.py .

# c) add the two missing repair branches (tx.origin + overflow)
python patch_fixmaker_classes.py

# d) sanity-compile the contracts (optional but recommended)
for f in contracts/bench_*.sol; do echo "$f"; solc --bin "$f" >/dev/null || echo "  COMPILE FAIL"; done
#   note: bench_of_tokensale_buy.sol needs solc 0.7.6 (pragma ^0.7.6);
#   if your default solc is 0.8.x it will flag that one — that's expected,
#   the pipeline picks the pragma-matching solc itself.

# e) run the batch
python run_batch.py --manifest manifest_bench10.json --tag bench10
python reclassify.py --tag bench10
```

Paste me the grouped `reclassify` output. Target: most contracts in `ok`.
Whatever lands in `gate_rejected` / `flow1_no_verified_invariants` we fix
per-bucket — these are simple contracts, so failures are diagnosable fast.

---

## 4. The 5-RQ plan (down from 7)

Your FSE draft had 7 RQs. Three of them (RQ4 fine-tuning strategy, RQ5 LLM
architecture, RQ6 prompting strategy) are *internal-configuration* studies that
reviewers read as "tuning detail," not core contributions — and RQ5/RQ6 are the
ones reviewers explicitly found weak. Collapse to **5 RQs** that each map to a
concrete result and a reviewer complaint you're answering:

### RQ1 — Invariant quality
*How effectively does InvGetter synthesize security invariants that pass SMT
validation?*
- Metric: per-class, # candidate invariants, # SMT-verified (VU/VM), precision,
  false-positive rate.
- Result source: **hallucination funnel, invariant row** + Flow-1 summaries.
- Answers: "is the invariant layer real or hand-waved?"

### RQ2 — Exploit generation
*Can the AttackModule produce executable exploits that confirm real impact, and
how does k affect coverage?*
- Metric: exploit success rate per class; **k-sensitivity** (k∈{1,3,5,10}).
- Result source: executor_results + **Result #6 k-sweep** (needs Hook A).
- Answers Reviewer A's "why k=5?" and "do attacks actually execute?"

### RQ3 — End-to-end repair quality (THE headline)
*Does InvGuard generate patches that compile, block the exploit, preserve benign
behavior, and satisfy invariants?*
- Metric: the **multi-metric patch-validation table** (Result #2) — Patch /
  Compiles / Exploit-blocked / Benign-pass / Invariants-hold / Gas / Time.
- Result source: validation_report gate verdicts + gas probe.
- Answers the metareview's #1 (over-reliance on LLM) head-on.

### RQ4 — Hallucination filtering (the rebuttal centerpiece)
*How much of the LLM's raw output is rejected by the non-LLM stages
(parser/compiler, SMT, Foundry replay)?*
- Metric: the 3-stage **funnel table** (Result #3): raw → rejected-by-each →
  accepted.
- Result source: **hallucination_funnel.py**.
- Answers Reviewer A Q1, Reviewer C concern #1, metareview #1 — converts
  "you just trust the LLM" into measured filtering.

### RQ5 — Ablation (component necessity)
*What does each component contribute, and is the gate doing real work?*
- Metric: accept-rate for full / direct_llm (no invariants) / no_smt /
  no_replay / no_fixchecker.
- Result source: **run_ablations.py** (Result #4).
- Answers Reviewer B ("is this just combining existing pieces?") and Reviewer C
  ("does FixChecker actually validate?").

**Dropped from the 7:** old RQ4 (fine-tuning sequential-vs-curriculum), old RQ5
(PaLM/GPT-3.5/GPT-4o-mini comparison), old RQ6 (prompting strategies). Keep these
as a short paragraph in the appendix or a single "configuration choices" subsection
if a reviewer asks — they're not load-bearing for the contribution.

### Mapping to your 1–6 result points
- Result #1 (real-world DApps) → the 22-contract RQ from before, kept as a
  **separate** generalization RQ or a subsection of RQ3. The 10 contracts here
  are for the *controlled* RQ1–RQ5 above.
- Result #2 → RQ3.  Result #3 → RQ4.  Result #4 → RQ5.
- Result #5 (runtime) → a column in RQ3's table (free).
- Result #6 (k-sensitivity) → part of RQ2.

So the six improvement points collapse cleanly into 5 RQs, each run once over the
10 contracts. That's 5 experiments (one batch run feeds RQ1/RQ3/RQ4/RQ5; the
k-sweep adds RQ2), exactly as you wanted.
