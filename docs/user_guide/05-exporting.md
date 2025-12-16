# Exporting & Reporting

Journalism ends with a story. ArkhamMirror helps you package your proof.

## 📦 Investigation Packages

![Export Page](../assets/images/export.png)

Create a portable zip file containing the state of your investigation.

1. Go to the **Export** page.
2. Select what to include:
    * **Entities**: Profiles of key players.
    * **Timeline**: The chronological event list.
    * **Sensitive Data**: A list of PII needing redaction.
3. Click **Create Package**.

The resulting zip includes:

* `REPORT.md`: A high-level Executive Summary formatted for reading.
* `timeline.json` / `entities.json`: Raw data for data journalism teams.
* `sensitive_data.json`: The audit log of PII found.

## 📄 Quick CSV Exports

Every data table in the app (Search Results, timelines, etc.) has a "Download CSV" button for use in Excel or Google Sheets.
