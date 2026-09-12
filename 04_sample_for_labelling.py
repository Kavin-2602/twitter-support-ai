"""
Step 5: Golden Set Stratified Sampling
Script: 04_sample_for_labelling.py

1. Loads amazon_support_data.csv (300 threads).
2. Uses Gemini API to perform lightweight batch classification of inbound_text to get provisional intents.
3. Performs stratified sampling across 6 intents (aiming for 200 total, minimum 15 per intent).
4. Outputs golden_set_template.csv for manual labeling.
"""

import os
import sys
import json
import pandas as pd
import argparse
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

# Force load .env from the current directory
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path, override=True)

# Reconfigure stdout to UTF-8 for Windows compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

INTENTS = [
    "Delivery Tracking",
    "Damaged/Wrong Item",
    "Refund Inquiry",
    "Account Access",
    "Order Cancellation",
    "Other"
]

CACHE_FILE = "intent_cache.json"

class IntentMapping(BaseModel):
    intents: dict[str, str]

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def batch_classify_intents(df: pd.DataFrame, batch_size: int = 50) -> dict:
    """Classifies inbound texts in batches to avoid rate limits."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set.")
        sys.exit(1)
        
    client = genai.Client(api_key=api_key)
    cache = load_cache()
    
    threads_to_classify = []
    for _, row in df.iterrows():
        tid = str(row['thread_id'])
        if tid not in cache:
            threads_to_classify.append((tid, row['inbound_text']))
            
    if not threads_to_classify:
        return cache
        
    print(f"Classifying {len(threads_to_classify)} new threads in batches of {batch_size}...")
    
    system_prompt = f"""You are an expert customer support routing agent for @AmazonHelp.
Classify each customer message into EXACTLY one of these categories: {json.dumps(INTENTS)}.
If a message is ambiguous, use "Other".

For each message, output a single line in the exact format:
[THREAD_ID]|INTENT
"""

    for i in range(0, len(threads_to_classify), batch_size):
        batch = threads_to_classify[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(threads_to_classify) + batch_size - 1)//batch_size}...")
        
        batch_text = "MESSAGES TO CLASSIFY:\n\n"
        for tid, text in batch:
            batch_text += f"[{tid}] {text}\n"
            
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=batch_text,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.0
                )
            )
            
            output_text = response.text
            for line in output_text.strip().split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = line.split('|', 1)
                    tid = parts[0].replace('[', '').replace(']', '').strip()
                    intent = parts[1].strip()
                    
                    if intent not in INTENTS:
                        intent = "Other"
                    cache[tid] = intent
                
            save_cache(cache)
            
        except Exception as e:
            print(f"Error classifying batch: {e}")
            print("Saving partial progress and continuing...")
            
    return cache

def stratified_sample(df: pd.DataFrame, target_n: int = 200, min_per_group: int = 15) -> pd.DataFrame:
    """Performs stratified sampling with minimums per intent."""
    counts = df['provisional_intent'].value_counts()
    
    sampled_indices = []
    remaining_n = target_n
    
    # First pass: satisfy minimums (or take all if < min)
    for intent in counts.index:
        intent_df = df[df['provisional_intent'] == intent]
        take_n = min(min_per_group, len(intent_df))
        
        sampled = intent_df.sample(n=take_n, random_state=42)
        sampled_indices.extend(sampled.index)
        remaining_n -= take_n
        
    # Second pass: proportional allocation for remaining slots
    remaining_df = df.drop(sampled_indices)
    if remaining_n > 0 and len(remaining_df) > 0:
        # Calculate weights based on original proportions
        weights = remaining_df['provisional_intent'].map(counts)
        additional_samples = remaining_df.sample(n=min(remaining_n, len(remaining_df)), weights=weights, random_state=42)
        sampled_indices.extend(additional_samples.index)
        
    return df.loc[sampled_indices].copy()

def main():
    print("Loading data...")
    df = pd.read_csv("amazon_support_data.csv")
    
    # 1. Batch Classify
    intent_map = batch_classify_intents(df)
    df['provisional_intent'] = df['thread_id'].astype(str).map(intent_map)
    df['provisional_intent'] = df['provisional_intent'].fillna("Other")
    
    # 2. Stratified Sampling
    print("\nPerforming stratified sampling (target 200 threads, min 15 per intent)...")
    sampled_df = stratified_sample(df, target_n=200, min_per_group=15)
    
    # 3. Output golden_set_template.csv
    sampled_df['true_intent'] = ""
    sampled_df['good_reply_notes'] = ""
    sampled_df['true_action'] = ""
    
    columns_order = [
        'thread_id', 'inbound_text', 'outbound_text', 
        'provisional_intent', 'true_intent', 'good_reply_notes', 'true_action'
    ]
    
    sampled_df = sampled_df[columns_order]
    sampled_df.to_csv("golden_set_template.csv", index=False, encoding="utf-8")
    
    # 4. Print Distribution
    print("\n" + "="*50)
    print("      SAMPLE DISTRIBUTION BY PROVISIONAL INTENT      ")
    print("="*50)
    print(sampled_df['provisional_intent'].value_counts().to_string())
    print("-" * 50)
    print(f"Total Threads Sampled: {len(sampled_df)}")
    print(f"Golden set template saved to: golden_set_template.csv")
    print("="*50)

if __name__ == "__main__":
    main()
