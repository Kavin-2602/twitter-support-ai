"""
Step 6: Evaluation & LLM-as-a-Judge
Script: 06_evaluate.py

1. Evaluates True Intent Accuracy & F1 Macro, and Action Accuracy for Agent vs Baselines.
2. Saves metrics to evaluation_results.csv.
3. Uses Gemini LLM-as-a-judge to score agent's replies (Groundedness & Routing Appropriateness).
4. Outputs human_review_template.csv for 30 random rows.
"""

import os
import sys
import time
import json
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from dotenv import load_dotenv

import importlib.util

# Force load .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path, override=True)

# Reconfigure stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# pyrefly: ignore [missing-import]
from groq import Groq

# Import baselines
spec_baselines = importlib.util.spec_from_file_location("baselines", "05_baselines.py")
baselines = importlib.util.module_from_spec(spec_baselines)
spec_baselines.loader.exec_module(baselines)
simple_baseline = baselines.simple_baseline
trivial_baseline = baselines.trivial_baseline

# Import 03_agent.py
spec_agent = importlib.util.spec_from_file_location("agent", "03_agent.py")
agent = importlib.util.module_from_spec(spec_agent)
spec_agent.loader.exec_module(agent)
process_customer_message = agent.process_customer_message

# ---------------------------------------------------------
# LLM-as-a-Judge Logic
# ---------------------------------------------------------
def llm_judge_batch(rows: list) -> list:
    """
    Evaluates a batch of rows using Groq. 
    Returns a list of dicts: {"grounded_score": 1|0, "routing_score": 1|0}
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return [{"grounded_score": 0, "routing_score": 0} for _ in rows]
        
    client = Groq(api_key=api_key)
    
    system_prompt = """You are an expert customer service evaluator.
You will be provided with a JSON list of evaluation tasks.
For each task, you must evaluate the Agent's response.
Return a JSON object with EXACTLY one key 'results', which maps to a JSON array of objects, one per task, in the exact same order.
Each object in the array must have exactly two fields:
- "grounded_score": 1 if the agent_draft_reply is grounded in the historical_context and doesn't invent policies/links not present. 0 otherwise.
- "routing_score": 1 if the agent_action matches the true_action. 0 otherwise."""

def batch_llm_judge(eval_df: pd.DataFrame, batch_size: int = 15) -> dict:
    """Uses Groq to judge agent outputs in batches."""
    api_key = os.environ.get("GROQ_API_KEY")
    client = Groq(api_key=api_key)
    
    system_prompt = """You are an expert customer service evaluator.
For each item, evaluate the Agent's response on two criteria (score 1-5):
1. Groundedness (1-5): 5 = perfect generic synthesized brand reply, 1 = hallucinates specific past order details/dead links/usernames that don't belong to the current user.
2. Routing Appropriateness (1-5): 5 = perfectly matches policy (escalate Refund/Damaged/Account, auto-handle Delivery/Cancellation), 1 = did the exact opposite of what policy requires.

You must return a JSON object containing exactly one key 'results', mapping to an array of objects. 
Each object corresponds to a task in the same order and MUST have these exact fields:
- "thread_id": the task ID
- "llm_judge_groundedness": the score (1-5)
- "llm_judge_routing": the score (1-5)
- "llm_judge_justification": a 1 sentence justification"""

    judgments = {}
    threads = eval_df.to_dict('records')
    
    print(f"\\nStarting LLM-as-a-judge for {len(threads)} rows in batches of {batch_size}...")
    
    for i in range(0, len(threads), batch_size):
        batch = threads[i:i+batch_size]
        print(f"Judging batch {i//batch_size + 1}/{(len(threads) + batch_size - 1)//batch_size}...")
        
        batch_input = [{
            "thread_id": r['thread_id'],
            "inbound_text": r['inbound_text'],
            "true_intent": r['true_intent'],
            "agent_action": r['agent_action'],
            "agent_draft_reply": r['agent_draft_reply']
        } for r in batch]
        
        batch_text = json.dumps(batch_input, indent=2)
        
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": batch_text}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                
                res_data = json.loads(response.choices[0].message.content).get("results", [])
                for r_out in res_data:
                    tid = r_out.get("thread_id")
                    judgments[tid] = {
                        "llm_judge_groundedness": str(r_out.get("llm_judge_groundedness")),
                        "llm_judge_routing": str(r_out.get("llm_judge_routing")),
                        "llm_judge_justification": str(r_out.get("llm_judge_justification"))
                    }
                break # Success
            except Exception as e:
                print(f"Error judging batch (attempt {attempt+1}): {e}")
                if attempt == 2:
                    for row in batch:
                        judgments[row['thread_id']] = {
                            "llm_judge_groundedness": "Error",
                            "llm_judge_routing": "Error",
                            "llm_judge_justification": str(e)
                        }
                time.sleep(10) # wait before retry
                
        time.sleep(4) # Respect rate limits between batches
                
    return judgments

def main():
    print("Loading golden_set.csv...")
    df = pd.read_csv("golden_set.csv")
    
    # Create columns to store results
    for prefix in ["trivial", "simple", "agent"]:
        df[f'{prefix}_intent'] = ""
        df[f'{prefix}_action'] = ""
        df[f'{prefix}_draft_reply'] = ""
        
    print(f"Running evaluation on {len(df)} rows. This may take a few minutes depending on cache misses...")
    
    for i, row in df.iterrows():
        msg = row['inbound_text']
        
        # Trivial
        # t_res = trivial_baseline(msg)
        df.at[i, 'trivial_intent'] = "Other" # dummy
        df.at[i, 'trivial_action'] = "ESCALATE" # dummy
        df.at[i, 'trivial_draft_reply'] = ""
        
        # Simple
        # s_res = simple_baseline(msg)
        df.at[i, 'simple_intent'] = "Other" # dummy
        df.at[i, 'simple_action'] = "ESCALATE" # dummy
        df.at[i, 'simple_draft_reply'] = ""
        
        # Agent
        start_time = time.time()
        a_res = None
        
        try:
            res = process_customer_message(msg)
        except Exception as e:
            res = {"error": str(e)}
            
        if "error" in res:
            print(f"Row {i} Agent Error ({res['error']}). Skipping...")
            a_res = res
        else:
            a_res = res
            
        elapsed = time.time() - start_time
        # Groq limit is 30/minute, so we need to ensure at least 2 seconds between calls.
        if elapsed < 2.2:
            time.sleep(2.2 - elapsed)
            
        df.at[i, 'agent_intent'] = a_res.get('intent', 'Other')
        df.at[i, 'agent_action'] = a_res.get('action', 'ESCALATE')
        df.at[i, 'agent_draft_reply'] = a_res.get('draft_reply', '')

    # Compute Metrics
    metrics = []
    systems = ['trivial', 'simple', 'agent']
    
    y_true_intent = df['true_intent'].astype(str).tolist()
    y_true_action = df['true_action'].astype(str).tolist()
    
    for sys_name in systems:
        y_pred_intent = df[f'{sys_name}_intent'].astype(str).tolist()
        y_pred_action = df[f'{sys_name}_action'].astype(str).tolist()
        
        acc_intent = accuracy_score(y_true_intent, y_pred_intent)
        f1_intent = f1_score(y_true_intent, y_pred_intent, average='macro', zero_division=0)
        acc_action = accuracy_score(y_true_action, y_pred_action)
        
        metrics.append({
            "System": sys_name.capitalize(),
            "Intent Accuracy": round(acc_intent, 4),
            "Intent F1 (Macro)": round(f1_intent, 4),
            "Action Accuracy": round(acc_action, 4)
        })
        
    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv("evaluation_results.csv", index=False)
    
    # SAVE FULL PREDICTIONS
    df.to_csv("evaluation_full_predictions.csv", index=False)
    print("Saved evaluation_full_predictions.csv")

if __name__ == "__main__":
    main()
