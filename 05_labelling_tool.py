"""
Step 5 Extension: Local UI Labelling Tool
Script: 05_labelling_tool.py

A lightweight local Flask web app to speed up manual labelling of the golden dataset.
Provides a beautiful, dark-mode, glassmorphism UI to iterate through the CSV, 
saving progress locally after every edit.
"""

import os
import sys
import pandas as pd
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

TEMPLATE_CSV = "golden_set_template.csv"
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
    """Loads golden_set.csv if it exists (for resuming), else the template."""
    if os.path.exists(SAVE_CSV):
        df = pd.read_csv(SAVE_CSV)
    else:
        df = pd.read_csv(TEMPLATE_CSV)
    
    # Fill NaN values with empty string for JS/JSON compatibility
    df.fillna("", inplace=True)
    return df

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Golden Set Labeller</title>
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
            <h1>Golden Set Labeller</h1>
            <div class="progress" id="progress">Row 1 of 200</div>
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

        async function loadRow(index) {
            const res = await fetch(`/api/row/${index}`);
            const data = await res.json();
            
            totalRows = data.total;
            currentIndex = data.index;

            document.getElementById('progress').innerText = `Row ${currentIndex + 1} of ${totalRows}`;
            document.getElementById('inbound_text').innerText = data.row.inbound_text;
            document.getElementById('outbound_text').innerText = data.row.outbound_text;
            document.getElementById('provisional_intent').innerText = `Provisional: ${data.row.provisional_intent}`;

            // Reset inputs to empty or load existing values
            // Force empty selection if there is no saved value
            const intentVal = data.row.true_intent || "";
            document.getElementById('true_intent').value = intentVal === "" ? "" : intentVal;
            
            document.getElementById('good_reply_notes').value = data.row.good_reply_notes || "";
            
            const actionVal = data.row.true_action || "";
            document.getElementById('true_action').value = actionVal === "" ? "" : actionVal;

            document.getElementById('btn_prev').disabled = (currentIndex === 0);
            document.getElementById('btn_next').disabled = (currentIndex === totalRows - 1);
        }

        async function saveData(silent = false) {
            const payload = {
                true_intent: document.getElementById('true_intent').value,
                good_reply_notes: document.getElementById('good_reply_notes').value,
                true_action: document.getElementById('true_action').value
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
            // Auto-save before navigating to prevent data loss
            await saveData(true);
            const nextIndex = currentIndex + direction;
            if (nextIndex >= 0 && nextIndex < totalRows) {
                loadRow(nextIndex);
            }
        }

        // Initialize by loading the first row
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
    if index < 0 or index >= len(df):
        return jsonify({"error": "Index out of bounds"}), 400
        
    row_data = df.iloc[index].to_dict()
    return jsonify({
        "index": index,
        "total": len(df),
        "row": row_data
    })

@app.route("/api/save/<int:index>", methods=["POST"])
def save_row(index):
    df = load_data()
    if index < 0 or index >= len(df):
        return jsonify({"error": "Index out of bounds"}), 400
        
    data = request.json
    
    # We only update the manual fields, and we don't copy provisional
    # If the user leaves the dropdown on default (empty string), we save empty string
    df.at[index, "true_intent"] = data.get("true_intent", "")
    df.at[index, "good_reply_notes"] = data.get("good_reply_notes", "")
    df.at[index, "true_action"] = data.get("true_action", "")
    
    # Save back to CSV immediately
    df.to_csv(SAVE_CSV, index=False, encoding="utf-8")
    return jsonify({"status": "success"})

if __name__ == "__main__":
    print(f"\\n{'='*60}\\nStarting Golden Set Labelling UI...\\nOpen http://127.0.0.1:5000 in your browser to start labelling.\\n{'='*60}\\n")
    app.run(debug=False, host='127.0.0.1', port=5000)
