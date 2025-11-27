# <img src="assets/logo.png" width="40" height="40" alt="ArkhamMirror Logo" style="vertical-align: middle;"> ArkhamMirror

![ArkhamMirror Banner](assets/banner.png)

> **Connect the dots without connecting to the cloud.**

### The insane part

I am not a developer. I can't read code. I can't write code. I honestly have no idea what I'm doing.

About a week ago I got angry that pretty much every investigative document tool forces journalists to upload sensitive leaks to the cloud, most of them cost money, and most of them kill your privacy.  

So I opened free-tier Claude, Gemini, Qwen, GPT, and Grok tabs and said: “I don't want to pay for cloud services.  I don't want to be rate limited. You are my dev team. Build me a 100% local version. MIT license. Oh yeah, one more thing. $0 budget.”  

A few days into seeing just how far I could go with the tools I had, this exists.  It started as a personal project to use and keep for myself, but my "AI dev team" convinced me that it needed to be shared with the world, so here we are.

If a complete non-coder can ship this in a week, imagine what you can do.

**ArkhamMirror** is a local-first, air-gapped investigation platform for journalists or anyone else looking for the truth in documents. It ingests complex documents (PDFs, images, handwriting), extracts text using hybrid OCR (PaddleOCR + Qwen-VL), and enables semantic search, anomaly detection, and "chat with your data" capabilities—all running 100% locally on your hardware.

![ArkhamMirror Demo](assets/ArkhamMirrorDemo.gif)

[![Watch the Deep Dive](https://img.youtube.com/vi/HcjcKnEzPww/0.jpg)](https://www.youtube.com/watch?v=HcjcKnEzPww)
> *Listen to the AI-generated Deep Dive (via NotebookLM) explaining how ArkhamMirror works and why it matters.*

## 🚀 Features

* **Hybrid OCR Engine**: Automatically switches between fast CPU-based OCR (PaddleOCR) and smart GPU-based Vision LLMs (Qwen-VL) for complex layouts and handwriting.
* **Multi-Format Ingestion**: Supports **PDF, DOCX, TXT, EML, MSG, and Images**. Automatically converts all formats to standardized PDFs for processing.
* **Semantic Search**: Find documents based on meaning, not just keywords, using hybrid vector search (Dense + Sparse embeddings).
* **Entity Extraction (NER)**: Automatically identifies People, Organizations, and Locations, with noise filtering and deduplication.
* **Local-First Privacy**: Designed to run with local LLMs (via LM Studio) and local vector stores. No data leaves your machine.
* **Anomaly Detection**: Automatically flags suspicious language ("confidential", "shred", "off the books") and visual anomalies.
* **Resilient Pipeline**: Includes "Retry Missing Pages" functionality to recover from partial failures without re-processing entire documents.
* **Investigative Lens**: AI-powered analysis modes:
  * **General Summary**: What is this document about?
  * **Motive Detective**: What is the author trying to hide?
  * **Timeline Analyst**: Extract chronological events.
* **Cluster Analysis**: Visualize how documents group together by topic.

## 🛠️ Tech Stack

* **Frontend**: Streamlit
* **Backend**: Python, SQLAlchemy
* **Database**: PostgreSQL (Metadata), Qdrant (Vectors), Redis (Queue)
* **AI/ML**:
  * **OCR**: PaddleOCR, Qwen-VL-Chat (via LM Studio)
  * **NER**: Spacy (en_core_web_sm)
  * **Embeddings**: BAAI/bge-large-en-v1.5
  * **LLM**: Qwen-VL-Chat / Llama 3 (via LM Studio)

## 📦 Installation

**👉 New to ArkhamMirror?** Check out our [User Guide for Journalists](docs/USER_GUIDE.md) - a step-by-step tutorial with screenshots and troubleshooting tips!

### Prerequisites

* **Docker Desktop** (for DB, Redis, Qdrant)
* **Python 3.10+**
* **LM Studio** (for local LLM inference) running Qwen-VL-Chat

### Quick Start

1. **Clone the Repository**

    ```bash
    git clone https://github.com/YourUsername/ArkhamMirror.git
    cd ArkhamMirror/arkham_mirror
    ```

2. **Start Infrastructure**

    ```bash
    docker compose up -d
    ```

3. **Setup Python Environment**

    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    # source venv/bin/activate # Linux/Mac
    # Option 1: Standard Installation (Recommended)
    # Includes BGE-M3 (multilingual) and all features
    pip install -r requirements-standard.txt

    # Option 2: Minimal Installation
    # Lightweight (English-only), saves ~2GB disk space
    # pip install -r requirements-minimal.txt
    ```

    **Note**: If you choose the Minimal installation, you must update `config.yaml` to use the `minilm-bm25` provider. See [EMBEDDING_PROVIDERS.md](docs/EMBEDDING_PROVIDERS.md) for details.

4. **Configure Environment**
    Copy `.env.example` to `.env` (or create one):

    ```env
    DATABASE_URL=postgresql://anom:anompass@localhost:5435/anomdb
    QDRANT_URL=http://localhost:6343
    REDIS_URL=redis://localhost:6380
    LM_STUDIO_URL=http://localhost:1234/v1
    ```

5. **Run the Application**

    ```bash
    streamlit run streamlit_app/Search.py
    ```

6. **Start Background Workers**
    Click the **"🚀 Spawn Worker"** button in the Streamlit sidebar to launch workers.

## 📚 Tutorial Data

New to ArkhamMirror? We've included a "Phantom Shipping" tutorial case to help you get started.

1. **Generate Data**:
    Run the generator script:

    ```bash
    python scripts/generate_sample_data.py
    ```

    This creates a set of realistic evidence files (PDF, DOCX, EML, Image) in `data/tutorial_case`.

2. **Ingest**:
    Drag and drop these files into the **"Upload Files"** area in the Streamlit sidebar.

3. **Investigate**:
    Search for "C-999" or "Captain Silver" to see how the system links information across different file types.

## ⚙️ Configuration

ArkhamMirror uses a `config.yaml` file for system settings. You can configure:

* **OCR Engine**: Choose between `paddle` (fast) or `qwen` (smart).
* **LLM Provider**: Connect to LM Studio, OpenAI, or local models.
* **Hardware**: Toggle GPU usage for OCR and Embeddings.

See `config.yaml` for all available options.

## 💖 Support This Project

ArkhamMirror is **free and open source**, built to empower journalists, researchers, and investigators. Your support helps us:

* 🖥️ Cover GPU compute costs for AI/OCR processing
* 🔧 Maintain and improve the platform
* ✨ Build new features requested by the community
* 📚 Create better documentation and tutorials

### Ways to Support

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-EA4AAA?style=for-the-badge&logo=github)](https://github.com/sponsors/mantisfury)
[![Ko-fi](https://img.shields.io/badge/Support-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/arkhammirror)

* **[GitHub Sponsors](https://github.com/sponsors/mantisfury)** - Zero fees, recurring or one-time support
* **[Ko-fi](https://ko-fi.com/arkhammirror)** - Quick one-time donations

**Every contribution matters!** Even $5 helps keep the servers running and the code flowing.

Thank you to our amazing sponsors! [View all sponsors →](SPONSORS.md)

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to report bugs, suggest features, and submit pull requests.

## 📜 License

This project is licensed under the MIT License.
