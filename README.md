# <img src="assets/logo.png" width="40" height="40" alt="ArkhamMirror Logo" style="vertical-align: middle;"> ArkhamMirror

![ArkhamMirror Banner](assets/banner.png)

> **Connect the dots without connecting to the cloud.**

**ArkhamMirror** is a local-first, air-gapped investigation platform for journalists. It ingests complex documents (PDFs, images, handwriting), extracts text using hybrid OCR (PaddleOCR + Qwen-VL), and enables semantic search, anomaly detection, and "chat with your data" capabilities—all running 100% locally on your hardware.

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
    pip install -r requirements.txt
    ```

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

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to report bugs, suggest features, and submit pull requests.

## 📜 License

This project is licensed under the MIT License.
