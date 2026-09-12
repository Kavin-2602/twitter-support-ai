# Failure Analysis

Based on the 119 mismatches identified during evaluation against the 199-row golden set, we have categorized the agent's failures into distinct patterns. Below is an analysis of the top 5 failure modes, followed by a summary of long-tail edge cases.

## Top 5 Failure Modes

### 1. The Sentiment Blindspot (Action mismatch: True='ESCALATE', Agent='AUTO_HANDLE')
**Count:** 40
**Pattern:** True Intent = Delivery Tracking | Agent Intent = Delivery Tracking 
**Hypothesis:** The agent's routing logic relies exclusively on intent classification and LLM confidence. Because it is explicitly instructed to auto-handle `Delivery Tracking` if confidence is high, it completely ignores customer sentiment, urgency, or frustration.
**Examples:**
- *ID: amz_thread_0098* | `To the person or persons that stole that big, heavy Amazon box of my porch today: enjoy 200 13 gallon garbage bags!`
- *ID: amz_thread_0202* | `@115821 where’s my damn nutribullet`

### 2. Escalating Trivial Chatter (Action mismatch: True='AUTO_HANDLE', Agent='ESCALATE')
**Count:** 21
**Pattern:** True Intent = Other | Agent Intent = Other
**Hypothesis:** The fallback routing rule dictates that any intent classified as "Other" should be escalated to a human. This fails to account for trivial, non-actionable chatter (like "thank you" or "all good"), burdening human agents with closing out completed conversations.
**Examples:**
- *ID: amz_thread_0039* | `@AmazonHelp My package just got here. All good, thank you!`
- *ID: amz_thread_0140* | `@AmazonHelp Thank you. Spoke with customer service who was very nice...`

### 3. Over-eager Delivery Classification (Intent mismatch: True='Other', Agent='Delivery Tracking')
**Count:** 13
**Pattern:** True Action = ESCALATE | Agent Action = AUTO_HANDLE
**Hypothesis:** The agent triggers on keywords related to logistics, carriers, or shipping, broadly misclassifying complex complaints or edge-case return workflows as standard `Delivery Tracking`. It then inappropriately attempts to auto-handle these nuanced issues.
**Examples:**
- *ID: amz_thread_0289* | `@AmazonHelp Yes, butvthey lied. Told me carrier and said they would contact and call me back.`
- *ID: amz_thread_0017* | `@AmazonHelp Already started the return. UPS gets it from my doorstep tomorrow.`

### 4. Missing Nuanced Delivery Complaints (Intent mismatch: True='Delivery Tracking', Agent='Other')
**Count:** 9
**Pattern:** True Action = ESCALATE | Agent Action = ESCALATE
**Hypothesis:** The agent misses delivery complaints if they lack standard tracking keywords, instead focusing on unrelated entities (like government services) or expressing general anger about fake replies.
**Examples:**
- *ID: amz_thread_0286* | `@115821 STOP USING THE @118706 They are a useless government entity.`
- *ID: amz_thread_0261* | `@AmazonHelp Nobody has called till now, why are you sending fake replies`

### 5. False Auto-handling of Non-Delivery Complaints
**Count:** 7
**Pattern:** True Intent = Other | Agent Intent = Delivery Tracking | True Action = AUTO_HANDLE | Agent Action = AUTO_HANDLE
**Hypothesis:** The agent correctly chooses to auto-handle these requests, but it misclassifies general driver complaints or missed promises as strict "Delivery Tracking" due to semantic overlap.
**Examples:**
- *ID: amz_thread_0295* | `@115821 it’s not nice to upset a kid (my daughter) on Halloween waitin’ for her dress...`
- *ID: amz_thread_0111* | `@115821 the more I order from you guys, the more I'm going to stop being a customer....YOUR DRIVERS ARE USELESS.`

---

## Long-tail errors

The remaining 18 mismatches consist of low-frequency edge cases (occurring 1 to 3 times each) where the agent struggled with semantic nuance. These long-tail patterns are briefly summarized below:

- **Refund Inquiry -> Delivery Tracking (3 cases):** Agent assumes refund demands for delayed packages are just standard delivery tracking questions, wrongly changing the action from ESCALATE to AUTO_HANDLE.
- **Delivery Tracking -> Other (2 cases):** Agent escalated questions about delivery fees instead of auto-handling them.
- **Damaged/Wrong Item -> Delivery Tracking (2 cases):** Customer reports a package was delivered but something is missing/damaged; agent auto-handles it as a successful delivery.
- **Order Cancellation ESCALATE -> AUTO_HANDLE (1 case):** An angry customer demanded to cancel an order after wasting time on the phone. The agent auto-handled it based on intent (Order Cancellation) and high confidence. **This directly reinforces Failure Mode 1**, proving that the agent's sentiment-blind escalation logic is a cross-category architectural flaw, not just limited to Delivery Tracking.
- **Other Isolated Edge Cases (10 cases, 1 occurrence each):** Various misclassifications such as mistaking website UI complaints for "Damaged/Wrong Item", or mistaking household linking queries for standard "Account Access". These cases mostly resulted in default escalations.
