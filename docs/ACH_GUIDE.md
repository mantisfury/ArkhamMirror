# 🕵️ Analysis of Competing Hypotheses (ACH) User Guide

**Analysis of Competing Hypotheses (ACH)** is an analytic technique developed by the CIA to help analysts overcome cognitive biases. ArkhamMirror implements a modern, interactive version of ACH directly integrated with your document corpus.

---

## 🚀 Quick Start (Feature Highlights)

ArkhamMirror's ACH tool guides you through an 8-step process to rigorously test your theories against evidence.

### key Features

* **AI Assistance**: Generate hypotheses, find evidence, suggesting ratings, and challenge your thinking.
* **Corpus Integration**: Direct links to your uploaded documents.
* **Sensitivity Analysis**: "What if" scenarios to test the robustness of your conclusions.
* **Professional Export**: PDF, JSON, and Markdown reports.

---

## ⌨️ Keyboard Shortcuts

Speed up your analysis with these keyboard shortcuts (active on the Matrix Step):

| Key | Action |
| :--- | :--- |
| **Arrow Keys** | Navigate between rating cells |
| **Tab** | Move to the next rating cell |
| **1** | Rate as **Very Consistent (CC)** |
| **2** | Rate as **Consistent (C)** |
| **3** | Rate as **Neutral (N)** |
| **4** | Rate as **Inconsistent (I)** |
| **5** | Rate as **Very Inconsistent (II)** |
| **Cmd+K** / **Ctrl+K** | Open Global Search |

---

## 📋 The 8-Step Process

### Step 1: Brainstorm Hypotheses

Define the possible explanations for your problem.

* **AI Suggest**: Click the sparkles icon to have AI generate hypotheses based on your focus question.
* **Challenge**: Use the "Devil's Advocate" feature to find blind spots.

### Step 2: Gather Evidence

List significant items of evidence.

* **Import from Corpus**: Search your uploaded documents and import facts directly as evidence.
* **AI Suggest**: Find relevant evidence automatically from your data.

### Step 3: Create the Matrix

Cross-reference every piece of evidence against every hypothesis.

* **Ratings**:
  * **CC**: Very Consistent
  * **C**: Consistent
  * **N**: Neutral / Not Applicable
  * **I**: Inconsistent
  * **II**: Very Inconsistent (Disproving)
* **AI Ratings**: Use the sparkles icon on a row to get AI-suggested ratings based on document context.

### Step 4: Refine the Matrix (Diagnosticity)

Identify which evidence is actually useful.

* **Diagnostic Evidence**: Evidence that helps distinguish between hypotheses (rated differently across them).
* **Filter**: Use the filter dropdown to focus on "High Diagnostic" items.

### Step 5: Draw Conclusions

Review the **Inconsistency Scores**.

* **Logic**: ACH works by *disproving* hypotheses. The hypothesis with the **lowest** inconsistency score is the most likely winner.
* **Visualization**: View the color-coded score chart.

### Step 6: Sensitivity Analysis 🆕

Test how sensitive your conclusion is to specific evidence.

* **"Run Analysis"**: Automatically calculates what happens if key evidence is wrong or excluded.
* **Critical Evidence**: Items marked 🔴 **Critical** would change the winner if they were incorrect. Double-check these!

### Step 7: Report Conclusions

Document your findings.

* **Sensitivity Notes**: Record your key assumptions and critical vulnerabilities.

### Step 8: Export 🆕

Share your analysis.

* **PDF**: Professional report with color-coded matrix, rankings, and summary tables.
* **Markdown**: Clean text format for easy editing.
* **JSON**: Full data export for archival or programmatic use.
* **AI Disclosure**: Exports automatically flag AI-assisted content for transparency.

---

## 🧠 Methodology Notes

### Why Inconsistency Scores?

We count **inconsistencies** (negative evidence) rather than consistencies because confirmation bias makes it easy to find supporting evidence for almost any theory. It is much harder to explain away a flat contradiction.

### Cognitive Biases Addressed

* **Confirmation Bias**: Forcing you to look for disconfirming evidence.
* **Satisficing**: Preventing you from stopping at the first "good enough" explanation.
* **Groupthink**: Making the analytic process explicit and transparent.
