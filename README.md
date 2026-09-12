# Twitter Support AI Agent (Hiver SDE Intern Assignment)

An autonomous customer support agent for Twitter (`@AmazonHelp`) built with intent classification, RAG retrieval, automated escalation routing, baseline benchmarking, and evaluation frameworks.

---

## Quickstart & Reproducibility (< 15 Minutes)

### 1. Environment Setup

```bash
# Clone repository and enter directory
cd twitter-support-ai

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
# source venv/bin/activate

# Install dependencies
pip install pandas kagglehub faiss-cpu sentence-transformers python-dotenv scikit-learn langdetect flask
```

Set your API keys in a `.env` file:
```
GROQ_API_KEY=your_key_here
```

### 2. Step-by-Step Pipeline Execution

```bash
# Step 1: Extract and reconstruct AmazonHelp English support threads
python 01_extract_data.py --max_threads 300

# Step 2: Build FAISS vector index & run retrieval sanity check
python 02_rag_pipeline.py

# Step 3: Run the Agent to test drafting and routing
python 03_agent.py

# Step 5: (Skip) Stratified Sampling & Local UI Labelling Tool
# Note: golden_set.csv is already provided in the repository with 199 hand-labelled rows.
# python 05_golden_set.py
# python 05b_relabel_missing.py

# Step 6: Evaluate Agent against Baselines
python 06_evaluate.py
# Note: judge_agreement_report.md requires manual human_score input and is not part of the fully automated reproduction.

# Step 8: Generate Failure Candidates
python 08_failure_analysis.py
```

## Documentation

- `REPORT.md`: Comprehensive final report summarizing pipeline, architecture, evaluation results, and failure analysis.
- `DECISION_LOG.md`: Detailed log of design decisions, assumptions, and configuration choices.
- `failure_analysis.md`: Detailed hypotheses and breakdown of the agent's failure modes.
- `judge_agreement_report.md`: Evaluation of LLM-as-a-judge alignment with human annotations.
- `golden_set_notes.md`: Notes on the golden set labelling process and data loss incident.
