import os
import sys
import time
import pandas as pd
from dotenv import load_dotenv
import importlib.util

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path, override=True)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Important! This setting avoids PyTorch tokenizers deadlock
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"

# Import agent directly
spec_agent = importlib.util.spec_from_file_location("agent", "03_agent.py")
agent = importlib.util.module_from_spec(spec_agent)
spec_agent.loader.exec_module(agent)
process_customer_message = agent.process_customer_message

def main():
    print("Loading golden_set.csv...")
    df = pd.read_csv("golden_set.csv")
    
    agent_intents = []
    agent_actions = []
    
    print(f"Fetching predictions for {len(df)} rows from cache...")
    for i, row in df.iterrows():
        msg = row['inbound_text']
        try:
            res = process_customer_message(msg)
            agent_intents.append(res.get("intent", "Other"))
            agent_actions.append(res.get("action", "ESCALATE"))
        except Exception as e:
            print(f"Row {i} error: {e}")
            agent_intents.append("Other")
            agent_actions.append("ESCALATE")
            
    df["agent_intent"] = agent_intents
    df["agent_action"] = agent_actions
    
    mismatches = df[
        (df["true_intent"] != df["agent_intent"]) |
        (df["true_action"] != df["agent_action"])
    ]
    
    print(f"Found {len(mismatches)} mismatches.")
    
    pattern_groups = mismatches.groupby(
        ["true_intent", "agent_intent", "true_action", "agent_action"]
    ).size().reset_index(name='count').sort_values('count', ascending=False)
    
    # Removed head(8) so we get all patterns
    top_patterns = pattern_groups
    output_rows = []
    
    for _, row in top_patterns.iterrows():
        t_int, a_int = row["true_intent"], row["agent_intent"]
        t_act, a_act = row["true_action"], row["agent_action"]
        count = row["count"]
        
        desc_parts = []
        if t_int != a_int:
            desc_parts.append(f"Intent mismatch: True='{t_int}', Agent='{a_int}'")
        if t_act != a_act:
            desc_parts.append(f"Action mismatch: True='{t_act}', Agent='{a_act}'")
        
        pattern_desc = " | ".join(desc_parts) + f" (Count: {count})"
        
        examples = mismatches[
            (mismatches["true_intent"] == t_int) &
            (mismatches["agent_intent"] == a_int) &
            (mismatches["true_action"] == t_act) &
            (mismatches["agent_action"] == a_act)
        ].head(3)
        
        examples_list = []
        for _, ex in examples.iterrows():
            examples_list.append(f"ID: {ex['thread_id']} | Text: {ex['inbound_text']}")
            
        output_rows.append({
            "pattern_description": pattern_desc,
            "true_intent": t_int,
            "agent_intent": a_int,
            "true_action": t_act,
            "agent_action": a_act,
            "examples": "\n\n".join(examples_list)
        })
        
    out_df = pd.DataFrame(output_rows)
    out_df.to_csv("failure_candidates.csv", index=False)
    print("failure_candidates.csv generated.")

if __name__ == "__main__":
    main()
