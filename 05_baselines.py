"""
Step 6: Baseline Models
Script: 05_baselines.py

Provides trivial_baseline and simple_baseline for comparison against the LLM agent.
"""

import importlib.util

# Dynamically import get_similar_resolutions
spec = importlib.util.spec_from_file_location("rag_pipeline", "02_rag_pipeline.py")
rag_pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag_pipeline)
get_similar_resolutions = rag_pipeline.get_similar_resolutions

def trivial_baseline(message: str) -> dict:
    """Always escalates and provides a generic fixed reply."""
    return {
        "intent": "Other",
        "draft_reply": "Thanks for reaching out, a team member will follow up shortly.",
        "action": "ESCALATE",
        "escalation_reason": "Default escalation - trivial baseline never auto-handles.",
        "retrieved_examples_used": []
    }

def simple_baseline(message: str) -> dict:
    """Uses basic keyword matching for intent and a fixed rule for action."""
    msg_lower = message.lower()
    intent = "Other"
    
    # 1. Keyword matching
    if any(k in msg_lower for k in ["refund", "money back", "charge"]):
        intent = "Refund Inquiry"
    elif any(k in msg_lower for k in ["password", "log in", "login", "account", "locked"]):
        intent = "Account Access"
    elif any(k in msg_lower for k in ["cancel"]):
        intent = "Order Cancellation"
    elif any(k in msg_lower for k in ["broken", "damaged", "wrong", "missing part"]):
        intent = "Damaged/Wrong Item"
    elif any(k in msg_lower for k in ["where is my", "tracking", "late", "arrive", "shipped", "delivery"]):
        intent = "Delivery Tracking"
        
    # 2. Rule for action
    if intent == "Delivery Tracking":
        action = "AUTO_HANDLE"
        escalation_reason = "Simple rule: Delivery Tracking is auto-handled."
    else:
        action = "ESCALATE"
        escalation_reason = "Simple rule: Escalate everything except Delivery Tracking."
        
    # 3. Retrieve top 1 historical reply without synthesis
    similar = get_similar_resolutions(message, top_k=1)
    if similar:
        draft_reply = similar[0]["outbound_text"]
        retrieved = [similar[0]["thread_id"]]
    else:
        draft_reply = "We will look into this."
        retrieved = []
        
    return {
        "intent": intent,
        "draft_reply": draft_reply,
        "action": action,
        "escalation_reason": escalation_reason,
        "retrieved_examples_used": retrieved
    }
