"""
Script: 05b_relabel_missing.py

A targeted Flask web app to speed up manual labelling of the remaining unlabelled rows in the golden dataset.
Filters out any row that is already fully labelled.
"""

import os
import sys
import pandas as pd
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

SAVE_CSV = "golden_set.csv"

# Intent list for the dropdown
INTENTS = [
    "Delivery Tracking",
    "Damaged/Wrong Item",
    "Refund Inquiry",
    "Account Access",
    "Order Cancellation",
    "Other"
]

def load_data():
    """Loads golden_set.csv."""
    df = pd.read_csv(SAVE_CSV)
    # Ensure columns exist
    for col in ["true_intent", "true_action", "good_reply_notes"]:
        if col not in df.columns:
            df[col] = ""
    # Fill NaN values with empty string for JS/JSON compatibility
    df.fillna("", inplace=True)
    return df

def get_unlabelled_indices(df):
    """Returns the original dataframe indices of rows that are not fully labelled."""
    mask_labelled = (
        (df["true_intent"] != "") &
        (df["true_action"] != "") &
        (df["good_reply_notes"] != "")
    )
    return df[~mask_labelled].index.tolist()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Missing Labels Relabeller</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --surface: rgba(30, 41, 59, 0.7);
            --border: rgba(255, 255, 255, 0.1);
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --accent: #8b5cf6;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            width: 100%;
            max-width: 900px;
            background: var(--surface);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 24px;
            font-weight: 700;
            background: -webkit-linear-gradient(45deg, var(--primary), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .progress {
            font-weight: 600;
            color: var(--text-muted);
            background: rgba(0,0,0,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            border: 1px solid var(--border);
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        .card {
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }
        .card h3 {
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 12px;
        }
        .text-content {
            font-size: 15px;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        .provisional {
            display: inline-block;
            margin-top: 15px;
            padding: 6px 12px;
            background: rgba(59, 130, 246, 0.1);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 6px;
            font-size: 13px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-size: 14px;
            font-weight: 600;
            color: var(--text-muted);
        }
        select, textarea {
            width: 100%;
            background: rgba(0,0,0,0.3);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 12px;
            border-radius: 8px;
            font-family: inherit;
            font-size: 15px;
            transition: all 0.3s ease;
        }
        select:focus, textarea:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
        }
        select option {
            background: var(--bg);
            color: var(--text-main);
        }
        textarea {
            resize: vertical;
            min-height: 100px;
        }
        .controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 15px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .btn-nav {
            background: rgba(255,255,255,0.1);
            color: var(--text-main);
            border: 1px solid var(--border);
        }
        .btn-nav:hover:not(:disabled) {
            background: rgba(255,255,255,0.2);
            transform: translateY(-2px);
        }
        .btn-nav:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .btn-save {
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: white;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
        }
        .btn-save:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
        }
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #10b981;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        }
        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }
    </style>
</head>
<body>

    <div class="container">
        <div class="header">
            <h1>Missing Labels Relabeller</h1>
            <div class="progress" id="progress">Loading...</div>
        </div>
        
        <div class="card" style="margin-bottom: 20px;">
            <h3>Thread ID: <span id="thread_id" style="color:var(--text-main); font-weight:normal; text-transform:none;"></span></h3>
        </div>

        <div class="grid">
            <!-- Left Column: Context -->
            <div class="context-panel">
                <div class="card" style="margin-bottom: 20px;">
                    <h3>Inbound Customer Text</h3>
                    <div class="text-content" id="inbound_text">Loading...</div>
                    <div class="provisional" id="provisional_intent">Provisional: -</div>
                </div>
                <div class="card">
                    <h3>Historical Brand Reply (Ref)</h3>
                    <div class="text-content" id="outbound_text" style="color: var(--text-muted);">Loading...</div>
                </div>
            </div>

            <!-- Right Column: Labelling Form -->
            <div class="labelling-panel">
                <div class="form-group">
                    <label>True Intent</label>
                    <select id="true_intent">
                        <option value="" disabled selected>Select an intent...</option>
                        {% for intent in intents %}
                        <option value="{{ intent }}">{{ intent }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group">
                    <label>Good Reply Notes</label>
                    <textarea id="good_reply_notes" placeholder="What should a good synthesized reply look like for this?"></textarea>
                </div>
                <div class="form-group">
                    <label>True Action</label>
                    <select id="true_action">
                        <option value="" disabled selected>Select an action...</option>
                        <option value="AUTO_HANDLE">AUTO_HANDLE</option>
                        <option value="ESCALATE">ESCALATE</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="controls">
            <button class="btn-nav" id="btn_prev" onclick="navigate(-1)">&#8592; Previous</button>
            <button class="btn-save" onclick="saveData(false)">Save Progress</button>
            <button class="btn-nav" id="btn_next" onclick="navigate(1)">Next &#8594;</button>
        </div>
    </div>

    <div class="toast" id="toast">Saved to golden_set.csv!</div>

    <script>
        let currentIndex = 0;
        let totalRows = 0;
        
        // Show completion message
        function showComplete() {
            document.body.innerHTML = `
            <div class="container" style="text-align: center;">
                <h1 style="color: var(--primary); margin-bottom: 20px;">All Done!</h1>
                <p>No more unlabelled rows remaining. You can close this window.</p>
            </div>
            `;
        }

        async function loadRow(index) {
            const res = await fetch(`/api/row/${index}`);
            const data = await res.json();
            
            if (data.total === 0) {
                showComplete();
                return;
            }
            
            totalRows = data.total;
            // Cap index
            if (index >= totalRows) index = totalRows - 1;
            if (index < 0) index = 0;
            currentIndex = index;

            document.getElementById('progress').innerText = `Row ${currentIndex + 1} of ${totalRows} remaining`;
            document.getElementById('thread_id').innerText = data.row.thread_id;
            document.getElementById('inbound_text').innerText = data.row.inbound_text;
            document.getElementById('outbound_text').innerText = data.row.outbound_text || "N/A";
            document.getElementById('provisional_intent').innerText = `Provisional: ${data.row.provisional_intent || "N/A"}`;

            // Reset inputs to empty explicitly as requested, do not load previous partial state
            document.getElementById('true_intent').value = "";
            document.getElementById('good_reply_notes').value = "";
            document.getElementById('true_action').value = "";

            document.getElementById('btn_prev').disabled = (currentIndex === 0);
            document.getElementById('btn_next').disabled = (currentIndex === totalRows - 1);
        }

        async function saveData(silent = false) {
            // Only save if at least one field has input
            const ti = document.getElementById('true_intent').value;
            const gr = document.getElementById('good_reply_notes').value;
            const ta = document.getElementById('true_action').value;
            
            if (!ti && !gr && !ta) {
                return; // Nothing to save
            }

            const payload = {
                true_intent: ti,
                good_reply_notes: gr,
                true_action: ta
            };

            await fetch(`/api/save/${currentIndex}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!silent) {
                const toast = document.getElementById('toast');
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 2000);
            }
        }

        async function navigate(direction) {
            // Auto-save before navigating
            await saveData(true);
            const nextIndex = currentIndex + direction;
            if (nextIndex >= 0 && nextIndex < totalRows) {
                loadRow(nextIndex);
            }
        }

        // Initialize
        loadRow(0);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, intents=INTENTS)

@app.route("/api/row/<int:index>")
def get_row(index):
    df = load_data()
    unlabelled_indices = get_unlabelled_indices(df)
    
    if not unlabelled_indices:
        return jsonify({"index": 0, "total": 0, "row": {}})
        
    if index < 0: index = 0
    if index >= len(unlabelled_indices): index = len(unlabelled_indices) - 1
        
    actual_df_index = unlabelled_indices[index]
    row_data = df.iloc[actual_df_index].to_dict()
    
    return jsonify({
        "index": index,
        "total": len(unlabelled_indices),
        "row": row_data
    })

@app.route("/api/save/<int:index>", methods=["POST"])
def save_row(index):
    df = load_data()
    unlabelled_indices = get_unlabelled_indices(df)
    
    if index < 0 or index >= len(unlabelled_indices):
        return jsonify({"error": "Index out of bounds"}), 400
        
    actual_df_index = unlabelled_indices[index]
    data = request.json
    
    # Update manual fields
    if data.get("true_intent"):
        df.at[actual_df_index, "true_intent"] = data["true_intent"]
    if data.get("good_reply_notes"):
        df.at[actual_df_index, "good_reply_notes"] = data["good_reply_notes"]
    if data.get("true_action"):
        df.at[actual_df_index, "true_action"] = data["true_action"]
    
    # Save back to CSV
    df.to_csv(SAVE_CSV, index=False, encoding="utf-8")
    return jsonify({"status": "success"})

if __name__ == "__main__":
    print(f"\\n{'='*60}\\nStarting Missing Labels Relabeller...\\nOpen http://127.0.0.1:5001 in your browser.\\n{'='*60}\\n")
    app.run(debug=False, host='127.0.0.1', port=5001)
