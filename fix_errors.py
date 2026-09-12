import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path, override=True)

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

system_prompt = """You are an expert customer service evaluator.
For each task, evaluate the Agent's response on two criteria (score 1-5):
1. Groundedness (1-5): 5 = perfect generic synthesized brand reply, 1 = hallucinates specific past order details/dead links/usernames that don't belong to the current user.
2. Routing Appropriateness (1-5): 5 = perfectly matches policy (escalate Refund/Damaged/Account, auto-handle Delivery/Cancellation), 1 = did the exact opposite of what policy requires.

You must return a valid JSON object containing exactly one key 'results', mapping to an array of objects. 
Each object corresponds to a task in the same order and MUST have these exact fields:
- "thread_id": the task ID
- "llm_judge_groundedness": the score (1-5)
- "llm_judge_routing": the score (1-5)
- "llm_judge_justification": a 1 sentence justification
"""

def main():
    df = pd.read_csv("human_review_template.csv")
    error_indices = df[df['llm_judge_groundedness'] == 'Error'].index
    
    if len(error_indices) == 0:
        print("No errors found.")
        return
        
    print(f"Found {len(error_indices)} rows with errors. Re-judging...")
    
    batch_input = []
    for i in error_indices:
        row = df.loc[i]
        batch_input.append({
            "thread_id": row['thread_id'],
            "inbound_text": row['inbound_text'],
            "true_intent": row['true_intent'],
            "agent_action": row['agent_action'],
            "agent_draft_reply": row['agent_draft_reply']
        })
        
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(batch_input)}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        output_text = response.choices[0].message.content
        parsed = json.loads(output_text.strip())
        results = parsed.get("results", [])
        
        for res in results:
            tid = res.get("thread_id")
            if tid:
                idx = df[df['thread_id'] == tid].index[0]
                df.at[idx, 'llm_judge_groundedness'] = str(res.get('llm_judge_groundedness'))
                df.at[idx, 'llm_judge_routing'] = str(res.get('llm_judge_routing'))
                df.at[idx, 'llm_judge_justification'] = str(res.get('llm_judge_justification'))
            
        df.to_csv("human_review_template.csv", index=False)
        print("Successfully re-judged and saved!")
    except Exception as e:
        print(f"Failed to re-judge: {e}")

if __name__ == "__main__":
    main()
