"""
Step 7b: Standalone Judge-Only Evaluation
Script: 07_judge_only.py

Reads cached agent responses from evaluation_full_predictions.csv and runs
ONLY the LLM-as-a-judge step over the 199-row golden set.
Does NOT re-run the agent, does NOT write to gemini_cache.json.

Prerequisites:
    Run 06_evaluate.py first so that evaluation_full_predictions.csv exists.

Usage:
    python 07_judge_only.py
    python 07_judge_only.py --input evaluation_full_predictions.csv --output judge_scores.csv --batch-size 15

DO NOT run until a fresh Groq quota window is available.
"""

import os
import sys
import json
import time
import argparse
import pandas as pd
from dotenv import load_dotenv

# Force load .env from the project directory
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path, override=True)

# Reconfigure stdout to UTF-8 for Windows compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------
DEFAULT_INPUT_CSV  = "evaluation_full_predictions.csv"
DEFAULT_OUTPUT_CSV = "judge_scores.csv"
DEFAULT_BATCH_SIZE = 15
JUDGE_MODEL        = "openai/gpt-oss-120b"
INTER_BATCH_SLEEP  = 4   # seconds between Groq batches (rate-limit guard)
RETRY_SLEEP        = 10  # seconds before retry on transient failure


# -----------------------------------------------------------------------
# LLM-as-a-judge  (quota-only step -- no agent calls here)
# -----------------------------------------------------------------------
def batch_llm_judge(eval_df: pd.DataFrame, client, batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """
    Sends agent predictions to the LLM judge in batches.
    Returns a dict keyed by thread_id with judge scores.
    Does NOT call the agent -- only consumes judge quota.
    """
    system_prompt = (
        "You are an expert customer service evaluator.\n"
        "For each item, evaluate the Agent's response on two criteria (score 1-5):\n"
        "1. Groundedness (1-5): 5 = perfect generic synthesised brand reply, "
        "1 = hallucinates specific past order details/dead links/usernames "
        "that don't belong to the current user.\n"
        "2. Routing Appropriateness (1-5): 5 = perfectly matches policy "
        "(escalate Refund/Damaged/Account, auto-handle Delivery/Cancellation), "
        "1 = did the exact opposite of what policy requires.\n\n"
        "You must return a JSON object containing exactly one key 'results', "
        "mapping to an array of objects.\n"
        "Each object corresponds to a task in the same order and MUST have these exact fields:\n"
        '- "thread_id": the task ID\n'
        '- "llm_judge_groundedness": the score (1-5)\n'
        '- "llm_judge_routing": the score (1-5)\n'
        '- "llm_judge_justification": a 1 sentence justification'
    )

    judgments: dict = {}
    threads = eval_df.to_dict("records")
    total_batches = (len(threads) + batch_size - 1) // batch_size
    print(f"\nStarting LLM-as-a-judge for {len(threads)} rows in batches of {batch_size}...")
    print(f"Estimated Groq calls: {total_batches}  |  Model: {JUDGE_MODEL}\n")

    for i in range(0, len(threads), batch_size):
        batch     = threads[i : i + batch_size]
        batch_num = i // batch_size + 1
        print(f"  Judging batch {batch_num}/{total_batches} ({len(batch)} rows)...")

        batch_input = [
            {
                "thread_id":         r["thread_id"],
                "inbound_text":      r["inbound_text"],
                "true_intent":       r["true_intent"],
                "agent_action":      r.get("agent_action", ""),
                "agent_draft_reply": r.get("agent_draft_reply", ""),
            }
            for r in batch
        ]

        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=JUDGE_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": json.dumps(batch_input, indent=2)},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                res_data = json.loads(response.choices[0].message.content).get("results", [])
                for r_out in res_data:
                    tid = r_out.get("thread_id")
                    judgments[tid] = {
                        "llm_judge_groundedness":  str(r_out.get("llm_judge_groundedness")),
                        "llm_judge_routing":       str(r_out.get("llm_judge_routing")),
                        "llm_judge_justification": str(r_out.get("llm_judge_justification")),
                    }
                break  # success -- exit retry loop
            except Exception as exc:
                print(f"    Attempt {attempt + 1}/3 failed: {exc}")
                if attempt == 2:
                    # All retries exhausted -- record error and continue
                    for row in batch:
                        judgments[row["thread_id"]] = {
                            "llm_judge_groundedness":  "Error",
                            "llm_judge_routing":       "Error",
                            "llm_judge_justification": str(exc),
                        }
                else:
                    time.sleep(RETRY_SLEEP)

        time.sleep(INTER_BATCH_SLEEP)  # rate-limit guard between batches

    return judgments


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Standalone judge-only script. "
            "Reads cached agent predictions from a CSV, runs ONLY the LLM judge, "
            "and writes per-row scores. Does NOT re-run the agent."
        )
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_CSV,
        help=f"CSV containing cached agent predictions (default: {DEFAULT_INPUT_CSV})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV for per-row judge scores (default: {DEFAULT_OUTPUT_CSV})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per Groq API call (default: {DEFAULT_BATCH_SIZE})",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Validate input file
    # ------------------------------------------------------------------
    if not os.path.exists(args.input):
        print(
            f"ERROR: Input file '{args.input}' not found.\n"
            "       Run 06_evaluate.py first to generate cached agent predictions\n"
            "       (produces 'evaluation_full_predictions.csv')."
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Load cached agent predictions (no agent calls)
    # ------------------------------------------------------------------
    print(f"Loading cached predictions from: {args.input}")
    df = pd.read_csv(args.input)
    print(f"  Loaded {len(df)} rows.")

    required_cols = {"thread_id", "inbound_text", "true_intent", "agent_action", "agent_draft_reply"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"ERROR: Input CSV is missing required columns: {missing}")
        sys.exit(1)

    # Filter to rows that have a valid agent prediction (skip error rows)
    df_valid = df[df["agent_intent"].notna() & (df["agent_intent"] != "")].copy()
    skipped  = len(df) - len(df_valid)
    if skipped:
        print(f"  Warning: Skipping {skipped} rows with missing agent_intent (error rows).")
    print(f"  Rows queued for judging: {len(df_valid)}")

    # ------------------------------------------------------------------
    # 3. Initialise Groq client  (judge quota only -- no agent calls)
    # ------------------------------------------------------------------
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set. Check your .env file.")
        sys.exit(1)

    # pyrefly: ignore [missing-import]
    from groq import Groq
    client = Groq(api_key=api_key, timeout=30.0)
    print(f"Groq client ready. Judge model: {JUDGE_MODEL}")

    # ------------------------------------------------------------------
    # 4. Run judge  (NO agent calls happen here)
    # ------------------------------------------------------------------
    judgments = batch_llm_judge(df_valid, client, batch_size=args.batch_size)

    # ------------------------------------------------------------------
    # 5. Merge scores back onto the full dataframe
    # ------------------------------------------------------------------
    df["llm_judge_groundedness"]  = df["thread_id"].map(
        lambda tid: judgments.get(tid, {}).get("llm_judge_groundedness",  "N/A")
    )
    df["llm_judge_routing"]       = df["thread_id"].map(
        lambda tid: judgments.get(tid, {}).get("llm_judge_routing",       "N/A")
    )
    df["llm_judge_justification"] = df["thread_id"].map(
        lambda tid: judgments.get(tid, {}).get("llm_judge_justification", "N/A")
    )

    # ------------------------------------------------------------------
    # 6. Print summary statistics
    # ------------------------------------------------------------------
    numeric_g = pd.to_numeric(df["llm_judge_groundedness"], errors="coerce")
    numeric_r = pd.to_numeric(df["llm_judge_routing"],      errors="coerce")

    judged_count = numeric_g.notna().sum()
    error_count  = (df["llm_judge_groundedness"] == "Error").sum()

    print(f"\n{'=' * 50}")
    print("Judge Run Summary")
    print(f"{'=' * 50}")
    print(f"  Rows judged successfully : {judged_count}")
    print(f"  Rows with errors         : {error_count}")
    if judged_count > 0:
        print(f"  Avg Groundedness score   : {numeric_g.mean():.2f} / 5")
        print(f"  Avg Routing score        : {numeric_r.mean():.2f} / 5")
    print(f"{'=' * 50}\n")

    # ------------------------------------------------------------------
    # 7. Save output
    # ------------------------------------------------------------------
    df.to_csv(args.output, index=False)
    print(f"Judge scores saved to: {args.output}")
    print("Done. No agent quota was consumed.")


if __name__ == "__main__":
    main()
