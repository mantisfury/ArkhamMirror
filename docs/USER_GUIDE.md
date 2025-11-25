# 📘 ArkhamMirror User Guide for Journalists

**Welcome!** This guide will help you get ArkhamMirror up and running, even if you've never used developer tools before.

## What is ArkhamMirror?

ArkhamMirror is a **local-first document intelligence platform** that helps you:
- Extract text from PDFs, images, and scanned documents
- Search hundreds of documents by meaning, not just keywords
- Find people, organizations, and locations automatically
- Detect suspicious language and anomalies
- Analyze documents with AI assistance

**Most importantly:** All your data stays on YOUR computer. Nothing goes to the cloud.

---

## 📋 What You'll Need

Before you start, make sure you have:

1. **A Windows, Mac, or Linux computer** with at least:
   - 8GB RAM (16GB recommended)
   - 20GB free disk space
   - Internet connection (for initial setup only)

2. **Basic software** (we'll help you install these):
   - Docker Desktop (runs databases)
   - Python 3.10+
   - LM Studio (runs AI models locally)

**Don't worry!** We'll walk you through installing everything step-by-step.

---

## 🚀 Quick Start (30 Minutes)

### Step 1: Install Docker Desktop

**What is Docker?** It's software that runs the databases ArkhamMirror needs.

1. **Download Docker Desktop**:
   - Go to [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
   - Click "Download for Windows" (or Mac/Linux)
   - Run the installer and follow the prompts

2. **Start Docker**:
   - Open Docker Desktop from your Start Menu
   - Wait for it to say "Docker is running" (green icon in system tray)
   - You don't need to create an account - just click "Continue without signing in"

**Stuck?** If Docker won't start, restart your computer and try again.

---

### Step 2: Install Python

**What is Python?** It's the programming language ArkhamMirror is built with.

1. **Download Python**:
   - Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
   - Click "Download Python 3.12" (or latest version)

2. **Install Python** (IMPORTANT!):
   - Run the installer
   - ✅ **Check the box** that says "Add Python to PATH"
   - Click "Install Now"

3. **Verify it worked**:
   - Open Command Prompt (search "cmd" in Start Menu)
   - Type: `python --version`
   - You should see: `Python 3.12.x`

---

### Step 3: Install LM Studio (Local AI)

**What is LM Studio?** It runs AI models on your computer (no cloud needed).

1. **Download LM Studio**:
   - Go to [https://lmstudio.ai/](https://lmstudio.ai/)
   - Click "Download for Windows" (or Mac/Linux)
   - Install and open it

2. **Download an AI Model**:
   - In LM Studio, click the **Search icon** (🔍)
   - Search for: `qwen2.5-14b-instruct`
   - Click **Download** (this may take 20-30 minutes - it's a large file)

3. **Start the Local Server**:
   - In LM Studio, click the **Server tab** (↔️ icon)
   - Click **"Start Server"**
   - Leave LM Studio running in the background

**Tip:** You only need to download the model once. After that, just start the server.

---

### Step 4: Download ArkhamMirror

1. **Download the code**:
   - Go to [https://github.com/mantisfury/ArkhamMirror](https://github.com/mantisfury/ArkhamMirror)
   - Click the green **"Code"** button
   - Click **"Download ZIP"**
   - Extract the ZIP file to a folder like `C:\ArkhamMirror`

**OR** if you have Git installed:
```bash
git clone https://github.com/mantisfury/ArkhamMirror.git
cd ArkhamMirror
```

---

### Step 5: Set Up ArkhamMirror

1. **Open Command Prompt in the ArkhamMirror folder**:
   - Navigate to where you extracted ArkhamMirror
   - Hold **Shift** and **right-click** in the folder
   - Click "Open PowerShell window here" or "Open Command Prompt here"

2. **Run the setup script** (Windows):
   ```bash
   cd arkham_mirror
   install.bat
   ```

   **OR manually** (all platforms):
   ```bash
   cd arkham_mirror
   python -m venv venv
   .\venv\Scripts\activate    # Windows
   # source venv/bin/activate  # Mac/Linux
   pip install -r requirements.txt
   ```

3. **Start the databases**:
   ```bash
   docker compose up -d
   ```

   This starts PostgreSQL, Qdrant (vector database), and Redis (task queue).

4. **Copy the environment file**:
   - In the `arkham_mirror` folder, find `.env.example`
   - Copy it and rename the copy to `.env`
   - Open `.env` in Notepad - it should already have the correct settings

---

### Step 6: Launch ArkhamMirror! 🎉

1. **Start the application**:
   ```bash
   streamlit run streamlit_app/Search.py
   ```

2. **Open your browser**:
   - ArkhamMirror will automatically open at `http://localhost:8501`
   - If not, manually open that URL in your browser

3. **You should see the ArkhamMirror interface!**

---

## 📚 How to Use ArkhamMirror

### Uploading Documents

1. **In the sidebar**, look for the **"Upload Files"** section
2. **Drag and drop** your documents (PDF, DOCX, images, etc.)
3. **Click "Process Documents"**
4. **Wait** for processing to complete (you'll see a progress bar)

**Supported formats:**
- PDF files
- Word documents (.docx)
- Images (PNG, JPG) with text
- Email files (.eml, .msg)
- Text files (.txt)

---

### Searching Documents

1. **Type your search query** in the search box
2. **Click "Search"**
3. **Results show**:
   - Matching text snippets
   - Which document they came from
   - A relevance score

**Search Tips:**
- Use natural language: "Who received payments in 2023?"
- ArkhamMirror understands meaning, not just keywords
- Try different phrasings if you don't find what you need

---

### AI-Powered Analysis

ArkhamMirror has three AI analysis modes:

1. **General Summary**: "What is this document about?"
2. **Motive Detective**: "What is the author trying to hide?"
3. **Timeline Analyst**: "Extract chronological events"

**How to use:**
1. Click on a search result
2. Choose an analysis mode
3. Read the AI's interpretation

**Note:** AI analysis requires LM Studio to be running!

---

### Finding People, Organizations, and Locations

1. Go to the **"Overview"** page (sidebar)
2. Scroll to **"Entities"**
3. See all extracted:
   - **People** (John Doe, Jane Smith, etc.)
   - **Organizations** (Acme Corp, FBI, etc.)
   - **Locations** (New York, 123 Main St, etc.)

Click on any entity to see which documents mention it.

---

### Viewing Anomalies

1. Go to the **"Anomalies"** page (sidebar)
2. See documents flagged for:
   - Suspicious keywords ("shred", "off the books", "confidential")
   - Unusual patterns detected by AI

**Use this to find** documents that might be hiding something.

---

### Visualizing Connections

1. Go to the **"Visualizations"** page (sidebar)
2. See how documents cluster together by topic
3. Explore the network graph of entities and their relationships

---

## 🛠️ Troubleshooting

### "Docker is not running"
**Solution:** Open Docker Desktop and wait for it to start. Look for the green icon in your system tray.

### "Port 5435 already in use"
**Solution:** Another program is using that port. Either:
- Stop the other program, OR
- Change the port in `docker-compose.yml`

### "LM Studio connection failed"
**Solution:**
1. Make sure LM Studio is open
2. Click the **Server tab**
3. Click **"Start Server"**
4. Check that it says "Server running on http://localhost:1234"

### "OCR isn't working"
**Solution:**
- ArkhamMirror uses two OCR engines:
  - **PaddleOCR** (fast, CPU-based) - works out of the box
  - **Qwen-VL** (smart, GPU-based) - requires LM Studio
- If Qwen-VL fails, it falls back to PaddleOCR automatically

### "Python not found"
**Solution:** Reinstall Python and make sure to check "Add Python to PATH" during installation.

### Processing is stuck
**Solution:**
1. Check the **worker logs** in the Streamlit sidebar
2. Click **"🚀 Spawn Worker"** to start a background worker
3. Wait a few minutes - large documents take time

---

## 💡 Tips for Investigators

### Best Practices

1. **Organize your documents** into folders before uploading
2. **Use descriptive filenames** (dates, sources, topics)
3. **Upload in batches** (don't upload 1,000 documents at once)
4. **Review entity extractions** - AI isn't perfect, manually verify important finds
5. **Save your searches** - write down useful queries

### Privacy & Security

- **ArkhamMirror never sends data to the internet** (except to check for updates)
- All processing happens on YOUR computer
- Your documents are stored in `data/` folder locally
- To delete everything: stop Docker, delete the `data/` folder

### Performance Tips

- **More RAM = faster processing**
- **GPU recommended** for smart OCR (but not required)
- **SSD storage** speeds up search significantly
- Close other programs while processing large batches

---

## 🆘 Getting Help

**Need assistance?**

1. **Check the README**: [README.md](../README.md)
2. **Open an issue**: [GitHub Issues](https://github.com/mantisfury/ArkhamMirror/issues)
3. **Ask a question**: Use the `question` label on GitHub
4. **Community discussions**: Coming soon!

**Found a bug?** Please report it! Open an issue and include:
- What you were trying to do
- What happened instead
- Your operating system and ArkhamMirror version

---

## 🚀 Next Steps

Once you're comfortable with the basics:

1. **Try the tutorial data**: Run `python scripts/generate_sample_data.py` for a practice investigation
2. **Explore advanced settings**: Check `config.yaml` to customize OCR and AI models
3. **Read the roadmap**: See what features are coming in [ROADMAP.md](../ROADMAP.md)
4. **Contribute**: Help improve ArkhamMirror! See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## 📖 Glossary

**Terms you'll see:**

- **OCR** (Optical Character Recognition): Converting images/scans to text
- **Vector Database**: Stores document "meanings" for semantic search
- **Embeddings**: Mathematical representations of text meaning
- **NER** (Named Entity Recognition): Finding people, places, organizations
- **LLM** (Large Language Model): AI that understands and generates text
- **Local-first**: Everything runs on your computer, not the cloud

---

**Happy investigating!** 🔍

If this guide helped you, consider [supporting the project](https://ko-fi.com/arkhammirror) to keep it free and open source.
