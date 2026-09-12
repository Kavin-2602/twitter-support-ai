"""
Step 3: Agent Routing & RAG Drafting (Gemini Version)
Script: 03_agent.py

Uses Gemini API (gemini-1.5-flash) to classify customer messages, fetch similar resolutions from the FAISS RAG index,
draft a grounded brand reply, and determine escalation routing based on intent confidence rules.
Includes a local file-based cache to avoid redundant API calls.
"""

import os
import sys
import json
import hashlib
import argparse
import importlib.util
from dotenv import load_dotenv
from groq import Groq

# Force load .env from the current directory
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path, override=True)

# Reconfigure stdout to UTF-8 for Windows compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Intent config
INTENTS = [
    "Delivery Tracking",
    "Damaged/Wrong Item",
    "Refund Inquiry",
    "Account Access",
    "Order Cancellation",
    "Other"
]

CACHE_FILE = "gemini_cache.json"

# Dynamically import get_similar_resolutions from 02_rag_pipeline.py
spec = importlib.util.spec_from_file_location("rag_pipeline", "02_rag_pipeline.py")
rag_pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag_pipeline)
get_similar_resolutions = rag_pipeline.get_similar_resolutions

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

def generate_cache_key(message: str, context_str: str) -> str:
    hash_input = f"{message}||{context_str}"
    return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

# Define expected keys for structured output
# intent, intent_confidence, draft_reply

def process_customer_message(message: str) -> dict:
    """
    Classifies the message, retrieves historical context, drafts a reply, and decides routing.
    Returns a dictionary matching the required JSON schema.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print(json.dumps({"error": f"GROQ_API_KEY is not set. Checked path: {env_path}"}))
        sys.exit(1)
        
    client = Groq(api_key=api_key, timeout=15.0)
    
    # 1. Retrieve historical resolutions (top 3)
    similar_resolutions = get_similar_resolutions(message, top_k=3)
    
    # 2. Prepare grounding context
    context_str = ""
    retrieved_examples_used = []
    for i, res in enumerate(similar_resolutions, 1):
        context_str += f"Example {i}:\n"
        context_str += f"Customer (Historical): {res['inbound_text']}\n"
        context_str += f"Brand Reply: {res['outbound_text']}\n\n"
        retrieved_examples_used.append(res['thread_id'])
        
    # Check cache
    cache = load_cache()
    cache_key = generate_cache_key(message, context_str)
    
    if cache_key in cache:
        output = cache[cache_key]
    else:
        # 3. Call LLM for intent classification, drafting, and confidence score
        system_prompt = f"""You are an expert customer support routing and drafting agent for @AmazonHelp.

Your task is to process an inbound customer message and return a JSON object with EXACTLY the following fields:
1. "intent": Classify the message into exactly one of these categories: {json.dumps(INTENTS)}.
2. "intent_confidence": A string indicating classification confidence, either "high" or "low".
3. "draft_reply": A drafted brand reply based ONLY on the provided historical examples. Do not copy any retrieved example verbatim. Synthesize a new reply in the brand's tone and typical resolution pattern from ALL retrieved examples, without including specific details (links, order numbers, usernames) that don't apply to this new customer's message. If the examples do not provide enough information to resolve the issue, draft a polite generic escalation reply asking for more details.

Ensure you respond with a valid JSON object only.

Historical Examples for Grounding:
{context_str}"""

        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Customer Message: {message}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            output_text = response.choices[0].message.content
            output = json.loads(output_text)
            
            # Save to cache
            cache[cache_key] = output
            save_cache(cache)
        except Exception as e:
            # Handle API errors gracefully
            return {
                "error": f"Groq API request failed: {str(e)}",
                "action": "ESCALATE",
                "escalation_reason": "API Failure",
                "intent": "Other",
                "draft_reply": "",
                "retrieved_examples_used": retrieved_examples_used
            }
            
    intent = output.get("intent", "Other")
    draft_reply = output.get("draft_reply", "")
    confidence = output.get("intent_confidence", "low").lower()
    
    # Validate intent is in the exact list
    if intent not in INTENTS:
        intent = "Other"
        confidence = "low"
        
    # 4. Determine Action and Escalation Reason
    action = "ESCALATE"
    escalation_reason = ""
    
    if intent in ["Refund Inquiry", "Damaged/Wrong Item", "Account Access"]:
        action = "ESCALATE"
        escalation_reason = f"Intent '{intent}' always requires human escalation."
    elif intent in ["Delivery Tracking", "Order Cancellation"]:
        if confidence == "high":
            action = "AUTO_HANDLE"
            escalation_reason = f"High confidence for auto-handle intent '{intent}'."
        else:
            action = "ESCALATE"
            escalation_reason = f"Low confidence for intent '{intent}'."
    else:
        action = "ESCALATE"
        escalation_reason = f"Intent '{intent}' defaults to human escalation."
        
    # 5. Return structured payload
    return {
        "intent": intent,
        "draft_reply": draft_reply,
        "action": action,
        "escalation_reason": escalation_reason,
        "retrieved_examples_used": retrieved_examples_used
    }

def main():
    parser = argparse.ArgumentParser(description="Process a single customer message via LLM agent.")
    parser.add_argument("message", type=str, nargs="*", help="The customer message to process")
    args = parser.parse_args()
    
    if args.message:
        # CLI Mode: single message
        msg = " ".join(args.message)
        result = process_customer_message(msg)
        print(json.dumps(result, indent=2))
    else:
        # Batch test mode
        test_messages = [
            "Where is my package? It was supposed to arrive 3 days ago.",
            "I want a refund, the product I received is completely broken.",
            "How do I reset my account password, I can't log in."
        ]
        
        for msg in test_messages:
            print(f"\nProcessing message: '{msg}'")
            print("-" * 50)
            result = process_customer_message(msg)
            print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
