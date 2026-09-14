# Judge Agreement Report

## Core Finding: This Judge Cannot Be Trusted as a Reliable Proxy for Human Judgment

Our LLM-as-a-judge (`openai/gpt-oss-120b` via Groq) shows two distinct failure modes that make it unfit to serve as a reliable automated quality signal:

1. **Instability across runs:** Human-judge agreement varies between **47% and 83%** across two runs using word-for-word identical prompts, identical input data, and `temperature=0.0`. A 36-point spread on a 100-point scale from a supposedly deterministic configuration is not calibration noise — it is structural unreliability.

2. **Hallucinated justifications:** Spot-checking the lower-agreement run reveals the judge is not simply "stricter" — it is generating factually incorrect and internally contradictory reasoning. Several rows score routing=1 despite the agent taking the exact action the rubric prescribes, with justifications that directly contradict the scoring criteria.

This is a genuine limitation of the evaluation harness. **Any automated quality metrics in this project should be read with that caveat explicitly in mind.**

---

## Concrete Evidence: Three Examples of Judge Hallucination

### Example 1 — `amz_thread_0204`: Factually false justification

| Field | Value |
| :--- | :--- |
| Inbound | *"Didn't know I needed to. Is that really a thing?! But still Prime shipping should be 2 days, correct?"* |
| Agent reply | *"@118078 Yes, Release-Date Delivery is indeed a thing. Prime two-day shipping means your order should arrive within two business days..."* (150 characters) |
| Agent action | AUTO_HANDLE |
| Human score | 3.0 |

| Run | Routing score | Justification |
| :--- | :---: | :--- |
| Old run | 5 | "Generic explanation of Prime shipping, correct AUTO_HANDLE for Delivery Tracking." |
| New run | **1** | **"No response drafted; escalation is not appropriate for a Prime-shipping timing question."** |

**The judge stated "no response drafted" on a row with a 150-character reply.** This is not a strict interpretation — it is a hallucinated fact about the input. The routing=1 score is therefore untrustworthy regardless of whether the routing decision itself was correct.

---

### Example 2 — `amz_thread_0174`: Invented policy violation

| Field | Value |
| :--- | :--- |
| Inbound | *"I already chatted with help and am still not convinced i'll get the right item because clearly the warehouse workers can't read."* |
| True intent | Damaged/Wrong Item |
| Agent action | **ESCALATE** |
| True action | **ESCALATE** |
| Human score | 4.0 |

| Run | Routing score | Justification |
| :--- | :---: | :--- |
| Old run | 5 | "Both groundedness and routing are appropriate for a Damaged/Wrong Item intent." |
| New run | **1** | **"No hallucination present, but escalating a complaint about order accuracy is not the prescribed action."** |

**The rubric explicitly states: Damaged/Wrong Item → ESCALATE.** The agent escalated a Damaged/Wrong Item. The judge scored this routing=1 and invented a justification that directly contradicts the scoring criteria it was given. The old score (5) was correct; the new score is a confabulation.

---

### Example 3 — `amz_thread_0277`: Groundedness rubric misapplied

| Field | Value |
| :--- | :--- |
| Inbound | *"@AmazonHelp asm mentioned before. You all are just idiots."* |
| Agent reply | *"We're sorry you're upset. We'll review your previous inquiry and get back to you shortly. Thank you for your patience."* |
| Human score | 3.0 |

| Run | Groundedness | Justification |
| :--- | :---: | :--- |
| Old run | 5 | "Simple apology with no fabricated user or order information." |
| New run | **1** | **"Absent content means no grounding; a generic insult does not require escalation per policy."** |

**The groundedness rubric measures whether the reply hallucinates specific order details, dead links, or usernames.** A plain apology with zero fabricated content is groundedness=5 by definition. The judge is re-interpreting "grounding" to mean "substantive content," which is not what the rubric says. The old score (5) was correct.

---

## Full-Dataset Judge Averages (199 rows, fresh run)

| Metric | Score |
| :--- | :---: |
| Avg Groundedness | **3.43 / 5** |
| Avg Routing | **2.21 / 5** |

The low average routing score (2.21/5) is directionally consistent with the failure analysis finding that ~63% of errors stem from escalation-rule design flaws. Despite per-row misfires, the aggregate signal is plausible corroborating evidence — but it should not be cited as a precise measurement given the instability documented above.

---

## Aggregate Agreement Statistics (30-row overlap)

### Agreement range across runs

| Run | Within ±1 Point | Avg Groundedness (30 rows) | Avg Routing (30 rows) |
| :--- | :---: | :---: | :---: |
| Old partial run (`fix_errors.py` / `replace_duplicate.py`) | ~83% | 4.93 | 4.50 |
| Fresh 199-row run (`07_judge_only.py`) | 47% | 3.40 | 2.37 |

**The 36-point spread between runs is the finding** — not either individual number.

### Fresh run statistics

| Metric | Human vs Judge Combined | Human vs Groundedness | Human vs Routing |
| :--- | :---: | :---: | :---: |
| Pearson *r* | 0.19 | -0.04 | 0.28 |
| Cohen's kappa (binned Low/Med/High) | 0.02 | 0.03 | 0.15 |
| Mean Absolute Difference | 1.62 | 1.83 | 2.00 |
| Within ±1 point agreement | 47% | — | 47% |

*Bins: Low = 1-2, Medium = 3, High = 4-5.*

### Bin distribution (fresh run)

| Bin | Human | Judge (combined avg) |
| :--- | :---: | :---: |
| Low (1-2) | 3 | 7 |
| Medium (3) | 3 | 18 |
| High (4-5) | 24 | 5 |

---

## Diagnostic: Ruling Out a Bug

All three alternative explanations were investigated and ruled out:

| Check | Finding |
| :--- | :--- |
| System prompt changed? | No — word-for-word identical across all 4 scripts |
| Input data scrambled? | No — 10 spot-checked + 5 batch-boundary rows all aligned correctly |
| New scores simply stricter but correct? | No — 3 of 5 examined examples have factually wrong or self-contradictory new justifications |

**Root cause:** `temperature=0.0` does not guarantee determinism on Groq-hosted models. The API load-balances across model shards/replicas, which can produce qualitatively different rubric interpretations from identical inputs across separate API calls.

---

## Note on Data Integrity
The `agent_draft_reply` values in `human_review_scored.csv` differ from those in `evaluation_full_predictions.csv` only in CSV quoting/escaping (extra quotes, escaped characters). The underlying text is identical, so the human scoring remains valid. This discrepancy is a harmless artifact of how the files were generated.
