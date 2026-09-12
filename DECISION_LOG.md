# Decision Log - Twitter Support AI Agent

This document logs key design decisions, assumptions, and configurations made at each step of the assignment.

---

## Step 1: Setup & Data Ingestion

- **Target Brand**: Selected `@AmazonHelp` (or `author_id == 'AmazonHelp'`). Chosen because Amazon customer support on Twitter deals with a wide range of retail, delivery, digital, and account issues, providing rich variety for intent taxonomy and RAG retrieval.
- **Dataset Source**: `thoughtvector/customer-support-on-twitter` via `kagglehub`.
- **Subsampling & Efficiency**: To satisfy the constraint of fast execution (< 15 mins reproduction), dataset processing reads in chunks / filtered streams rather than loading full 3M-row dataset into unoptimized memory at once.
- **Thread Reconstruction Linkage**: Reconstructed inbound (customer tweet) -> outbound (AmazonHelp response tweet) pairs by matching `in_response_to_tweet_id` and `response_tweet_id` fields. Cleaned text by stripping trailing handles and redundant whitespace.
- **Target Extraction Count**: Set target clean thread count to ~300 threads (exceeding the 200+ requirement) to provide sufficient data for RAG indexing and stratified sampling.
- **Language Filtering**: Added automated language detection (`langdetect`) with a confidence threshold of >= 0.85 on `inbound_text`. Non-English tweets (e.g. Japanese `@AmazonHelp` posts) and unparseable noise are filtered out to ensure intent classification, RAG retrieval, and manual golden-set annotation are performed exclusively on high-quality English customer queries.

---

## Step 2: Build Retrieval & RAG Pipeline

- **Embedding Model Selection**: Selected `all-MiniLM-L6-v2` from `sentence-transformers`. Chosen because it is open-source, runs locally on CPU with minimal latency (~20ms per query), and produces dense 384-dimensional semantic embeddings optimized for short text retrieval.
- **FAISS Indexing Metric**: Used `faiss.IndexFlatIP` combined with L2 normalization (`faiss.normalize_L2`), converting inner product search into exact Cosine Similarity matching without boundary distortion.
- **Retrieval Depth**: Set default `top_k = 3` to balance prompt token economy with sufficient context diversity for grounded brand reply drafting.
- **Persistence & Caching Strategy**: Saved the FAISS index (`index.faiss`) and metadata payload (`rag_metadata.pkl`) to disk. Implemented an auto-rebuild check based on file modification timestamp comparison (`csv_mtime > index_mtime`) to avoid redundant embedding compute during iterative execution.

---

## Step 3: Agent Routing & RAG Drafting

- **LLM Selection**: Used `groq` API with `openai/gpt-oss-120b` (extremely fast and robust for high-volume inference) combined with `response_format={"type": "json_object"}` to guarantee valid JSON output and structure adherence.
- **System Prompt Design**: Explicitly supplied the `INTENTS` array, injected RAG retrieved historical threads as `Example [N]` context blocks, and instructed the model NOT to invent new policies or links (RAG grounding). Requested `intent_confidence` (high/low) in the schema to facilitate conditional routing logic.
- **Routing Logic**: Implemented deterministic script-level rule routing rather than letting the LLM decide the final action. Always escalated high-risk intents (Refund, Damaged, Account Access), conditional auto-handle for operations (Delivery, Cancellation) based on LLM confidence, and default fallback escalation for "Other".
- **Dynamic Imports**: Because `02_rag_pipeline.py` starts with numbers, standard Python imports fail. Used `importlib.util` to safely import `get_similar_resolutions` without modifying previous files.

---

## Step 5: Golden Set Stratified Sampling

- **Batch Classification**: To classify all 300 rows efficiently using the free Gemini tier without hitting RPM rate limits, implemented a batch classification function that bundles up to 50 messages per LLM call using structured JSON mapping.
- **Stratified Sampling**: Aimed for 200 samples total. Used a two-pass sampling approach: first ensuring each of the 6 intents has at least min(15, count) examples, then allocating the remaining capacity proportionally based on original category frequencies to maintain real-world distribution while avoiding minority class starvation.
- **Template Output**: Generated golden_set_template.csv with empty columns (`true_intent`, `good_reply_notes`, `true_action`) optimized for manual annotation workflows.

---

## Step 5 Extension: Local Labelling Tool

- **UI/UX Choices**: Built a Flask-based web server (`05_labelling_tool.py`) with a modern glassmorphism UI to accelerate the manual labelling of the 200-item golden dataset. Selected this over a pure JS/HTML solution to bypass browser local-storage security sandboxes, enabling direct read/write to the local filesystem.
- **State Management**: The backend loads golden_set_template.csv and auto-saves progress row-by-row into a new golden_set.csv. This ensures the user can pause and resume without data loss, and prevents the provisional LLM intent from polluting the true intent fields by strictly defaulting all inputs to empty on first view.

---

## Step 5b: Data Loss Incident & Relabelling

- **Data Loss Handling**: A mid-project file corruption incident wiped out a significant portion of the initial golden_set.csv. 132 rows had to be manually relabelled in a separate second session.
- **Annotator Drift**: Because the labelling spanned two discrete sessions under different conditions, annotator drift (shifting definitions of fuzzy categories like "Other") was acknowledged as a systemic risk. (One row was unrecoverable, capping the final golden set at 199 rows).

---

## Step 6: Evaluation Framework

- **Metric Selection**: Chose F1 Score as the primary evaluation metric for Intent Classification to balance Precision and Recall across imbalanced classes. Used standard Accuracy for Action Prediction (binary: ESCALATE vs. AUTO_HANDLE).
- **Baselines**: Implemented a Trivial Baseline (always intent='Other', always action='ESCALATE') and a Simple Heuristic Baseline (keyword matching) to prove the LLM Agent provides significant uplift.
- **API Strategy for Evaluation**: Avoided free-tier rate limit deadlocks by migrating to Groq API (openai/gpt-oss-120b) during evaluation, allowing rapid 199-row batch processing. Addressed PyTorch Windows deadlock by using cache files and tweaking parallelization env variables (TOKENIZERS_PARALLELISM="false").

---

## Step 7: LLM-as-a-Judge Validation

- **Judge Implementation**: Initially explored using an LLM to judge the quality of the agent's drafted replies. 
- **Validation Findings**: Validated the LLM judge against human annotations and found an 83% agreement rate. The LLM judge struggled heavily with detecting customer sarcasm and evaluating the subjective boundaries of the "Other" intent category. This indicated that our automated evaluation metrics carried a measurable margin of error and confirmed the necessity of the manual golden set.

---

## Step 8 & 9: Failure Analysis & Reporting

- **Failure Candidate Extraction**: Parsed mismatched predictions directly from the agent's cached outputs without re-triggering LLM inference to ensure deterministic reproduction of evaluation errors. Grouped mismatches by pattern (True vs. Agent).
- **Analysis Approach**: Highlighted a critical "Sentiment Blindspot" where the agent strictly follows logical routing rules (e.g. tracking issues = auto-handle) but ignores the human element of frustration or anger, leading to inappropriate auto-handling of issues that require a human touch.
