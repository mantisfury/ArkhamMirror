# 📘 ArkhamMirror User Guide for Journalists

**Welcome!** This guide will help you get ArkhamMirror up and running, even if you've never used developer tools before.

## What is ArkhamMirror?

ArkhamMirror is a **local-first document intelligence platform** built for investigative journalists and researchers. It helps you:

* **Extract text** from PDFs, images, scanned documents, and handwritten notes
* **Search semantically** across hundreds of documents by meaning, not just keywords
* **Auto-detect entities**: People, organizations, locations with fuzzy deduplication
* **Build timelines**: Extract chronological events and detect temporal gaps
* **Map connections**: Visualize entity relationships and geographic patterns
* **Find anomalies**: AI-powered detection of suspicious language and patterns
* **Chat with your data**: Ask questions and get answers from your document corpus

**Most importantly:** All your data stays on YOUR computer. Nothing goes to the cloud.

> **Version Note**: This guide covers **ArkhamMirror v1.0+** (Reflex-based UI). If you're looking for the old Streamlit version (v0.x), see the legacy documentation in `arkham_mirror/streamlit_app/`.

---

## 📋 What You'll Need

Before you start, make sure you have:

1. **A Windows, Mac, or Linux computer** with at least:
   * 8GB RAM (16GB recommended)
   * 20GB free disk space
   * Internet connection (for initial setup only)

2. **Basic software** (we'll help you install these):
   * Docker Desktop (runs databases)
   * Python 3.10+
   * LM Studio (runs AI models locally)

**Don't worry!** We'll walk you through installing everything step-by-step.

---

## 🚀 Quick Start (30 Minutes)

### Step 1: Install Docker Desktop

**What is Docker?** It's software that runs the databases ArkhamMirror needs.

1. **Download Docker Desktop**:
   * Go to <https://www.docker.com/products/docker-desktop>
   * Click "Download for Windows" (or Mac/Linux)
   * Run the installer and follow the prompts

2. **Start Docker**:
   * Open Docker Desktop from your Start Menu
   * Wait for it to say "Docker is running" (green icon in system tray)
   * You don't need to create an account - just click "Continue without signing in"

**Stuck?** If Docker won't start, restart your computer and try again.

---

### Step 2: Install Python

**What is Python?** It's the programming language ArkhamMirror is built with.

1. **Download Python**:
   * Go to <https://www.python.org/downloads/>
   * Click "Download Python 3.12" (or latest version)

2. **Install Python** (IMPORTANT!):
   * Run the installer
   * ✅ **Check the box** that says "Add Python to PATH"
   * Click "Install Now"

3. **Verify it worked**:
   * Open Command Prompt (search "cmd" in Start Menu)
   * Type: `python --version`
   * You should see: `Python 3.12.x`

---

### Step 3: Install LM Studio (Local AI)

**What is LM Studio?** It runs AI models on your computer (no cloud needed).

1. **Download LM Studio**:
   * Go to <https://lmstudio.ai/>
   * Click "Download for Windows" (or Mac/Linux)
   * Install and open it

2. **Download an AI Model**:
   * In LM Studio, click the **Search icon** (🔍)
   * Search for: `qwen2.5-14b-instruct`
   * Click **Download** (this may take 20-30 minutes - it's a large file)

3. **Start the Local Server**:
   * In LM Studio, click the **Server tab** (↔️ icon)
   * Click **"Start Server"**
   * Leave LM Studio running in the background

**Tip:** You only need to download the model once. After that, just start the server.

---

### Step 4: Download ArkhamMirror

1. **Download the code**:
   * Go to <https://github.com/mantisfury/ArkhamMirror>
   * Click the green **"Code"** button
   * Click **"Download ZIP"**
   * Extract the ZIP file to a folder like `C:\ArkhamMirror`

**OR** if you have Git installed:

```bash
git clone https://github.com/mantisfury/ArkhamMirror.git
cd ArkhamMirror
```

---

### Step 5: Set Up ArkhamMirror

1. **Open Command Prompt in the ArkhamMirror folder**:
   * Navigate to where you extracted ArkhamMirror
   * Hold **Shift** and **right-click** in the folder
   * Click "Open PowerShell window here" or "Open Command Prompt here"

2. **Start the databases**:

   ```bash
   cd arkham_mirror
   docker compose up -d
   ```

   This starts PostgreSQL, Qdrant (vector database), and Redis (task queue).

3. **Set up Python backend**:

   ```bash
   python -m venv venv
   .\venv\Scripts\activate    # Windows
   # source venv/bin/activate  # Mac/Linux
   pip install -r requirements-standard.txt
   ```

4. **Set up Reflex frontend**:

   ```bash
   cd ../arkham_reflex
   pip install -r requirements.txt
   ```

5. **Initialize the database**:

   ```bash
   cd ../arkham_mirror
   .\venv\Scripts\activate  # Windows
   python backend/db/reset_db.py
   ```

---

### Step 6: Launch ArkhamMirror

1. **Start the background worker** (Terminal 1):

   ```bash
   cd arkham_mirror
   .\venv\Scripts\activate  # Windows
   python run_rq_worker.py
   ```

   Keep this terminal running.

2. **Start the Reflex app** (Terminal 2):

   ```bash
   cd arkham_reflex
   reflex run
   ```

3. **Open your browser**:
   * Navigate to `http://localhost:3000`
   * You should see the ArkhamMirror interface!

**🎉 You're ready to go!**

---

## 📚 How to Use ArkhamMirror

### Overview Page

The **Overview** page shows you statistics about your document corpus:

* Total documents, entities, anomalies, events
* Document type breakdown (pie chart)
* Top entity types (bar chart)
* Recent documents list

### Uploading Documents

1. Click **"Ingest"** in the sidebar
2. **Drag and drop** your documents (PDF, DOCX, images, emails, etc.)
3. Click **"Start Processing"**
4. **Monitor progress** - you'll see real-time status updates

**Supported formats:**

* PDF files
* Word documents (.docx)
* Images (PNG, JPG) with text
* Email files (.eml, .msg)
* Text files (.txt)

---

### Searching Documents

1. Click **"Search"** in the sidebar
2. **Type your search query** in the search box
3. **Press Enter** or click the search button
4. **Results show**:
   * Matching text snippets
   * Which document they came from
   * A relevance score

**Search Tips:**

* Use natural language: "Who received payments in 2023?"
* ArkhamMirror understands meaning, not just keywords
* Try different phrasings if you don't find what you need
* Export results to CSV for offline analysis

---

### Entity Exploration

**Entity Graph Page:**

1. Click **"Graph"** in the sidebar
2. See interactive network visualization of:
   * People connected to organizations
   * Organizations connected to locations
   * Relationships extracted from documents
3. **Filter** by entity type (PERSON, ORG, GPE)
4. **Export** as CSV or JSON

**Entity Deduplication Page:**

1. Click **"Entity Dedup"** in the sidebar
2. Review duplicate entity candidates
3. **Merge** confirmed duplicates (e.g., "J. Smith" + "John Smith")
4. **Dismiss** false positives
5. **Add aliases** for known variations

---

### Timeline Analysis

1. Click **"Timeline"** in the sidebar
2. See chronological events extracted from documents
3. **Temporal gaps** are highlighted (missing date ranges)
4. **Filter** by event type or date range
5. **Export** timeline and gaps to CSV

**Use cases:**

* Reconstruct sequence of events
* Identify suspicious gaps in documentation
* Find corroborating vs. contradicting dates

---

### Geospatial Analysis

1. Click **"Map"** in the sidebar
2. See all extracted locations plotted on interactive map
3. **Click markers** to see which documents mention that location
4. **Zoom** and **pan** to explore geographic patterns

---

### Anomaly Detection

1. Click **"Anomalies"** in the sidebar
2. See documents flagged for:
   * Suspicious keywords ("shred", "off the books", "confidential")
   * Unusual patterns detected by AI
3. **Chat with anomalies** - ask AI to explain why flagged
4. **Export** anomaly report to CSV

---

### Regex Pattern Search

1. Click **"Regex Search"** in the sidebar
2. **Choose a preset pattern**:
   * Phone numbers
   * Email addresses
   * Social Security Numbers
   * Credit card numbers
3. **OR write your own** custom regex pattern
4. **Search** across all documents
5. **Export** matches to CSV

---

### Visualizations

1. Click **"Visualizations"** in the sidebar
2. Explore:
   * **Cluster analysis**: How documents group by topic
   * **Activity heatmaps**: When were documents created?
   * **Entity co-occurrence**: Which entities appear together?

---

### ACH Analysis (Structured Thinking)

**Analysis of Competing Hypotheses (ACH)** helps you test theories against evidence to avoid bias.

1. Click **"ACH"** in the sidebar.
2. Follow the **8-step wizard**:
    * Brainstorm hypotheses.
    * Gather evidence (import facts from your documents).
    * Rate consistency in the matrix.
    * Analyze results.
3. **Use advanced features**:
    * **AI Assistance**: Generate hypotheses and ratings.
    * **Sensitivity Analysis**: Test "what if" scenarios.
    * **PDF Export**: generate professional reports.

👉 **[Read the full ACH Guide](ACH_GUIDE.md)** for details.

---

## 🛠️ Troubleshooting

### "Docker is not running"

**Solution:** Open Docker Desktop and wait for it to start. Look for the green icon in your system tray.

### "Port 5435 already in use"

**Solution:** Another program is using that port. Either:

* Stop the other program, OR
* Change the port in `docker-compose.yml`

### "LM Studio connection failed"

**Solution:**

1. Make sure LM Studio is open
2. Click the **Server tab**
3. Click **"Start Server"**
4. Check that it says "Server running on <http://localhost:1234>"

### "OCR isn't working"

**Solution:**

* ArkhamMirror uses two OCR engines:
  * **PaddleOCR** (fast, CPU-based) - works out of the box
  * **Qwen-VL** (smart, GPU-based) - requires LM Studio
* If Qwen-VL fails, it falls back to PaddleOCR automatically

### "Python not found"

**Solution:** Reinstall Python and make sure to check "Add Python to PATH" during installation.

### Processing is stuck

**Solution:**

1. Check that the **RQ worker** is running (`python run_rq_worker.py`)
2. Check worker logs for errors
3. Wait a few minutes - large documents take time
4. If still stuck, restart the worker

---

## 💡 Tips for Investigators

### Best Practices

* **Organize your documents** into folders before uploading
* **Use descriptive filenames** (dates, sources, topics)
* **Upload in batches** (don't upload 1,000 documents at once)
* **Review entity extractions** - AI isn't perfect, manually verify important finds
* **Use the deduplication tool** - clean entity data improves graph accuracy
* **Export often** - save CSV/JSON snapshots of findings

### Privacy & Security

* **ArkhamMirror never sends data to the internet** (except to check for updates)
* All processing happens on YOUR computer
* Your documents are stored in `data/` folder locally
* To delete everything: stop Docker, delete the `data/` folder

### Performance Tips

* **More RAM = faster processing**
* **GPU recommended** for smart OCR (but not required)
* **SSD storage** speeds up search significantly
* Close other programs while processing large batches

---

## 🆘 Getting Help

**Need assistance?**

1. **Check the README**: [README.md](../README.md)
2. **Open an issue**: [GitHub Issues](https://github.com/mantisfury/ArkhamMirror/issues)
3. **Ask a question**: Use the `question` label on GitHub

**Found a bug?** Please report it! Open an issue and include:

* What you were trying to do
* What happened instead
* Your operating system and ArkhamMirror version

---

## 🚀 Next Steps

Once you're comfortable with the basics:

1. **Try the tutorial data**: Run `python scripts/generate_sample_data.py` for a practice investigation
2. **Explore advanced settings**: Check `config.yaml` to customize OCR and AI models
3. **Read the roadmap**: See what features are coming in [REFLEX_ROADMAP.md](../REFLEX_ROADMAP.md)
4. **Contribute**: Help improve ArkhamMirror! See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## 📖 Glossary

**Terms you'll see:**

* **OCR** (Optical Character Recognition): Converting images/scans to text
* **Vector Database**: Stores document "meanings" for semantic search
* **Embeddings**: Mathematical representations of text meaning
* **NER** (Named Entity Recognition): Finding people, places, organizations
* **LLM** (Large Language Model): AI that understands and generates text
* **Local-first**: Everything runs on your computer, not the cloud
* **Reflex**: Modern React-based UI framework (replaces Streamlit in v1.0+)
* **RQ Worker**: Background process that handles document processing tasks

---

**Happy investigating!** 🔍

If this guide helped you, consider [supporting the project](https://ko-fi.com/arkhammirror) to keep it free and open source.
