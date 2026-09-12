import pandas as pd
import json
import os
import importlib.util
# pyrefly: ignore [missing-import]
from groq import Groq
from dotenv import load_dotenv

load_dotenv(override=True)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Import agent
spec = importlib.util.spec_from_file_location("agent", "03_agent.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

df_template = pd.read_csv("human_review_template.csv")
df_golden = pd.read_csv("golden_set.csv")

existing_threads = df_template['thread_id'].tolist()
valid_candidates = df_golden[
    (~df_golden['thread_id'].isin(existing_threads)) & 
    (df_golden['true_action'].notna())
]

if valid_candidates.empty:
    print("No valid candidates found.")
    exit(1)
    
new_row = valid_candidates.iloc[0].copy()
print(f"Running agent for new thread: {new_row['thread_id']}")
agent_out = agent.process_customer_message(new_row['inbound_text'])

new_row['agent_intent'] = agent_out['intent']
new_row['agent_action'] = agent_out['action']
new_row['agent_draft_reply'] = agent_out['draft_reply']

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

batch_input = [{
    "thread_id": new_row['thread_id'],
    "inbound_text": new_row['inbound_text'],
    "true_intent": new_row['true_intent'],
    "agent_action": new_row['agent_action'],
    "agent_draft_reply": new_row['agent_draft_reply']
}]

print("Running judge...")
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(batch_input)}
    ],
    response_format={"type": "json_object"},
    temperature=0.0
)

res = json.loads(response.choices[0].message.content).get("results", [])[0]

new_row['llm_judge_groundedness'] = str(res['llm_judge_groundedness'])
new_row['llm_judge_routing'] = str(res['llm_judge_routing'])
new_row['llm_judge_justification'] = str(res['llm_judge_justification'])
new_row['human_score'] = pd.NA

target_idx = df_template[df_template['thread_id'] == 'amz_thread_0167'].index[0]

for col in df_template.columns:
    df_template.at[target_idx, col] = new_row.get(col, pd.NA)

df_template.to_csv("human_review_template.csv", index=False)
print("Replaced amz_thread_0167 successfully.")
