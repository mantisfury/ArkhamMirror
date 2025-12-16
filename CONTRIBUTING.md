# Contributing to ArkhamMirror

First off, thank you for considering contributing to ArkhamMirror! It's people like you that make open source software such an amazing place to learn, inspire, and create.

Whether you're a journalist with feature ideas, a developer who found a bug, or someone who wants to improve the docs - all contributions are welcome and valued.

---

## 🤝 How Can I Contribute?

### 1. Reporting Bugs

This section guides you through submitting a bug report for ArkhamMirror. Following these guidelines helps maintainers and the community understand your report, reproduce the behavior, and find related reports.

**Before Submitting a Bug Report:**

- Check the [existing issues](https://github.com/mantisfury/ArkhamMirror/issues) to see if the problem has already been reported
- Try the latest version from `main` branch - it might already be fixed
- Check the [FUTURE_TASKS.md](FUTURE_TASKS.md) to see if it's a known limitation

**How to Submit a Good Bug Report:**

- **Use a clear and descriptive title** for the issue to identify the problem
- **Describe the exact steps which reproduce the problem** in as many details as possible
- **Provide specific examples** to demonstrate the steps. Include:
  - Sample documents (if privacy allows) or document types
  - Screenshots of error messages
  - Relevant logs from `DataSilo/logs/`
- **Describe the behavior you observed** and what you expected to see
- **Include environment details**:
  - OS and version (Windows 11, Ubuntu 24.04, macOS 14, etc.)
  - Python version (`python --version`)
  - Docker version (`docker --version`)
  - ArkhamMirror version (git commit hash or release tag)

**Example Bug Report:**

```
Title: "OCR fails on multi-column PDFs with tables"

Environment:
- Ubuntu 24.04
- Python 3.11.9
- ArkhamMirror v1.0.0

Steps to reproduce:
1. Upload financial-report-2024.pdf (2-column layout with tables)
2. Wait for OCR processing
3. Check document viewer

Expected: Text extracted in reading order
Actual: Text scrambled, columns mixed together

Logs: (attach relevant error from DataSilo/logs/ocr_worker.log)
```

---

### 2. Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for ArkhamMirror, including completely new features and minor improvements to existing functionality.

**Before Submitting an Enhancement:**

- Check [FUTURE_TASKS.md](FUTURE_TASKS.md) - your idea might already be planned
- Check [docs/upcoming_features.md](docs/upcoming_features.md) - detailed plans for larger features in development
- Search existing issues to see if someone else suggested it
- Consider if it aligns with the project's core mission: **local-first, privacy-focused investigative tools**

**How to Submit a Good Enhancement Suggestion:**

- **Use a clear and descriptive title** for the issue to identify the suggestion
- **Provide a step-by-step description of the suggested enhancement** in as many details as possible
- **Explain why this enhancement would be useful** to investigative journalists, researchers, or OSINT analysts
- **Provide examples** of how it would be used in a real investigation
- **Consider privacy implications** - will it require cloud services? Can it work locally?

**Example Enhancement Request:**

```
Title: "Add export to Gephi format for network analysis"

Use case:
Investigators often need to analyze entity networks in specialized tools like Gephi.

Proposed feature:
Add "Export to Gephi" button on Entity Graph page that outputs:
- Nodes: entities with attributes (type, frequency, documents)
- Edges: relationships with weights

Why it's useful:
- Enables advanced network metrics (betweenness, clustering)
- Allows custom layouts and filtering
- Common workflow for OSINT analysts

Privacy: No cloud required, local file export only
```

---

### 3. Your First Code Contribution

**New to open source?** Look for issues labeled [`good first issue`](https://github.com/mantisfury/ArkhamMirror/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) - these are beginner-friendly tasks that are great for first-time contributors!

**What makes a good first issue?**

- Clear, well-defined scope (e.g., "Add CSV export to Tables page")
- Doesn't require deep knowledge of the entire codebase
- Has guidance or examples provided
- Usually takes 1-3 hours to complete
- Well-contained within one or two files

**Getting Familiar with the Codebase:**

1. Read [CLAUDE.md](CLAUDE.md) - comprehensive project overview
2. Review [WORK_LOG.md](WORK_LOG.md) - see recent changes and patterns
3. Check the architecture section in CLAUDE.md to understand:
   - Frontend: Reflex (React/Next.js)
   - Backend: Python workers (RQ)
   - Databases: PostgreSQL, Qdrant, Redis

---

### 4. Pull Requests

The process is straightforward:

1. **Fork** the repo on GitHub
2. **Clone** your fork to your local machine
3. **Create a branch** for your feature or fix:

   ```bash
   git checkout -b feature/add-gephi-export
   # or
   git checkout -b fix/ocr-multicolumn-pdfs
   ```

4. **Make your changes** (see Development Setup below)
5. **Test your changes** thoroughly
6. **Commit** with clear messages:

   ```bash
   git commit -m "Add Gephi export format to entity graph page"
   ```

7. **Push** to your fork:

   ```bash
   git push origin feature/add-gephi-export
   ```

8. Submit a **Pull Request** on GitHub

**Pull Request Guidelines:**

- **Keep PRs focused** on a single feature or bug fix
- **Write clear commit messages** (see commit message guidelines below)
- **Update documentation** if you're adding/changing features:
  - Update CLAUDE.md if you add pages/workers/models
  - Update README.md if you change installation/usage
  - Add docstrings to new functions
- **Test your changes** before submitting:
  - Does the app still start? (`reflex run`)
  - Does your feature work with sample data?
  - Did you check browser console for errors?
- **Add a WORK_LOG.md entry** describing your changes
- **Follow code style** (see Coding Style below)

**Commit Message Guidelines:**

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Keep first line under 72 characters
- Reference issues: "Fix OCR crash on PDFs (#123)"

**Example Good Commits:**

```
Add Gephi export to entity graph page

- Implement GEXF format writer
- Add export button to graph page UI
- Include entity attributes in node data
- Fixes #456
```

---

## 💻 Development Setup

ArkhamMirror has a streamlined setup process. Here's how to get started:

### Prerequisites

- **Python 3.11+** (3.12 or 3.13 recommended)
- **Docker Desktop** (for PostgreSQL, Qdrant, Redis)
- **Git**
- **16GB RAM recommended** (8GB minimum)
- **15GB free disk space**

### Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/mantisfury/ArkhamMirror.git
   cd ArkhamMirror
   ```

2. **Run the automated installer** (recommended for first-time setup)

   **Windows:**

   ```cmd
   setup.bat
   ```

   **Mac/Linux:**

   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

   This will:
   - Create a Python virtual environment
   - Install all dependencies
   - Start Docker containers (PostgreSQL, Qdrant, Redis)
   - Initialize the database
   - Download spaCy models

### Manual Setup (if you prefer)

1. **Create virtual environment**

   ```bash
   python -m venv venv

   # Windows
   .\venv\Scripts\activate

   # Mac/Linux
   source venv/bin/activate
   ```

2. **Install dependencies**

   ```bash
   cd app
   pip install -r requirements.txt

   # Or for minimal install (no large models):
   pip install -r requirements-minimal.txt
   ```

3. **Start Docker infrastructure**

   ```bash
   cd ../docker
   docker compose up -d
   ```

   This starts:
   - PostgreSQL (port 5435)
   - Qdrant (ports 6343, 6344)
   - Redis (port 6380)

4. **Initialize database**

   ```bash
   cd ../app
   python -c "from arkham.services.db.db_init import init_db; init_db()"
   ```

5. **Download spaCy model** (for entity extraction)

   ```bash
   python -m spacy download en_core_web_sm
   ```

### Running the Application

**Start the Reflex app:**

```bash
cd app
reflex run
```

This starts:

- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>

**Start background workers** (in a separate terminal):

```bash
cd app
python run_rq_worker.py

# Or use the worker manager:
python worker_manager.py start 3  # Start 3 workers
```

**Alternative: Use the system management tools:**

```bash
# Check status of all services
python system_status.py

# Start everything at once
python system_status.py --start-all

# Control individual components
python reflex_server.py start
python worker_manager.py start 2
```

### Environment Configuration

ArkhamMirror uses centralized configuration in `config/settings.py`.

**DO NOT** set environment variables directly. Instead:

1. Check `config/settings.py` for available settings
2. Override via `.env` file at project root if needed:

   ```
   DATABASE_URL=postgresql://anom:anompass@localhost:5435/anomdb
   QDRANT_URL=http://localhost:6343
   REDIS_URL=redis://localhost:6380/0
   LM_STUDIO_URL=http://localhost:1234
   ```

Most developers won't need to create a `.env` file - the defaults work out of the box.

---

## 🏗️ Project Architecture

Understanding the structure helps you navigate and contribute:

```
ArkhamMirror/
├── app/                              # Main application
│   ├── arkham/
│   │   ├── arkham.py                 # App entry point (34 pages)
│   │   ├── pages/                    # 34 Reflex pages
│   │   ├── state/                    # 38 state management classes
│   │   ├── components/               # Reusable UI components
│   │   ├── services/
│   │   │   ├── db/                   # Database (SQLAlchemy models, migrations)
│   │   │   ├── workers/              # 7 async RQ workers
│   │   │   ├── llm/                  # LM Studio integration
│   │   │   └── utils/                # Security, hashing, etc.
│   │   └── models/                   # Data models
│   ├── requirements.txt              # Full dependencies (with BGE-M3)
│   └── requirements-minimal.txt      # Minimal dependencies (MiniLM)
├── config/
│   └── settings.py                   # CENTRAL CONFIG (use this!)
├── docker/
│   └── docker-compose.yml            # Infrastructure services
├── DataSilo/                         # User data (NOT in git)
│   ├── documents/                    # Uploaded files
│   ├── pages/                        # Processed page images
│   ├── logs/                         # Application logs
│   └── temp/                         # Temporary processing files
├── scripts/                          # Utility scripts
├── docs/                             # User documentation
├── CLAUDE.md                         # AI assistant reference (READ THIS!)
├── WORK_LOG.md                       # Development log
└── FUTURE_TASKS.md                   # Roadmap and known issues
```

**Key Concepts:**

1. **Workers**: Background jobs for document processing
   - `ingest_worker.py` - Document ingestion
   - `splitter_worker.py` - Document splitting
   - `ocr_worker.py` - OCR processing
   - `parser_worker.py` - Entity extraction
   - `embed_worker.py` - Embedding generation
   - `clustering_worker.py` - Document clustering
   - `contradiction_worker.py` - Contradiction detection

2. **Pages**: Reflex pages in `app/arkham/pages/`
   - Each page has a corresponding state class in `state/`
   - Use `layout()` wrapper for consistent UI

3. **Database**: SQLAlchemy 2.0 with Alembic migrations
   - Models in `services/db/models.py`
   - Migrations in `services/db/migrations/`

4. **Config**: Centralized in `config/settings.py`
   - Import settings: `from config import DATABASE_URL, REDIS_URL`
   - Never use `os.getenv()` directly

---

## 🎨 Coding Style

### Python Code

**General:**

- Follow **PEP 8** guidelines
- Use type hints where helpful: `def process_document(doc_id: int) -> bool:`
- Add docstrings to functions and classes
- **NEVER USE EMOJIS IN CODE** (only in comments/docs if needed)

**Imports:**

- Use centralized config: `from config import DATABASE_URL`
- Not: `os.getenv("DATABASE_URL")`

**Security:**

- Always use `security_utils.py` functions:
  - `sanitize_filename()` - prevent path traversal
  - `sanitize_for_llm()` - prevent prompt injection
  - `safe_delete_file()` - restrict to DataSilo/
  - `escape_html()` - prevent XSS

**Database Sessions:**

- Use context managers: `with get_db_session() as session:`
- Never store sessions as instance variables
- Check [WORK_LOG.md 2025-12-11 entry](WORK_LOG.md) for session safety patterns

**Logging:**

- Use centralized logger: `from arkham.utils.logging import get_logger`
- Standardized format with context

**Example Good Code:**

```python
from typing import List
from config import DATABASE_URL
from arkham.services.db.models import Document, get_db_session
from arkham.services.utils.security_utils import sanitize_filename
from arkham.utils.logging import get_logger

logger = get_logger(__name__)

def process_documents(file_paths: List[str]) -> int:
    """
    Process multiple documents for ingestion.

    Args:
        file_paths: List of absolute file paths to process

    Returns:
        Number of successfully processed documents
    """
    processed = 0

    with get_db_session() as session:
        for path in file_paths:
            safe_path = sanitize_filename(path)
            try:
                doc = Document(filename=safe_path)
                session.add(doc)
                session.commit()
                processed += 1
                logger.info(f"Processed document: {safe_path}")
            except Exception as e:
                logger.error(f"Failed to process {safe_path}: {e}")
                session.rollback()

    return processed
```

### Reflex/Frontend Code

**Page Structure:**

```python
import reflex as rx
from ..components.layout import layout
from ..state.my_state import MyState

def my_page() -> rx.Component:
    """My new page description."""
    return layout(
        rx.vstack(
            rx.heading("Page Title", size="8"),
            # Your components here
            spacing="4",
            width="100%",
        ),
        on_mount=MyState.load_data,  # Optional: load on mount
    )
```

**State Classes:**

```python
import reflex as rx

class MyState(rx.State):
    """State for my page."""

    data: list[dict] = []
    loading: bool = False

    def load_data(self):
        """Load data from database."""
        self.loading = True
        # ... fetch data ...
        self.loading = False
```

---

## 🧪 Testing Your Changes

**Before submitting a PR, test:**

1. **Does the app start?**

   ```bash
   cd app
   reflex run
   ```

2. **Does your feature work?**
   - Navigate to the page you modified
   - Test with sample data
   - Check for errors in browser console (F12)
   - Check backend logs for exceptions

3. **Does existing functionality still work?**
   - Upload a test document
   - Run a search
   - Check that workers are processing jobs

4. **Are there any obvious errors?**

   ```bash
   # Check for syntax errors
   python -m py_compile app/arkham/pages/your_page.py

   # Check for import errors
   python -c "from arkham.pages.your_page import *"
   ```

**Optional but appreciated:**

- Test on a fresh virtual environment
- Test with Docker containers restarted
- Test with sample documents of different types

---

## 📝 Documentation

When adding features, update these files as appropriate:

**Always update:**

- **WORK_LOG.md**: Add entry describing your changes (see existing entries for format)

**If you added/changed user-facing features:**

- **README.md**: Update feature list or installation instructions if changed
- **CLAUDE.md**: Update if you added pages, workers, database tables, or changed architecture
- **FUTURE_TASKS.md**: Remove items you completed, add new known limitations

**If you added new dependencies:**

- Update `app/requirements.txt` or `app/requirements-minimal.txt`
- Update installation docs if special steps are needed

---

## 🚨 Common Pitfalls to Avoid

1. **Don't commit to `main` directly** - always use a feature branch
2. **Don't commit `DataSilo/` directory** - it contains user data (already in .gitignore)
3. **Don't commit `.env` files** - contains credentials (already in .gitignore)
4. **Don't use `os.getenv()` directly** - import from `config/settings.py` instead
5. **Don't store DB sessions as instance variables** - use context managers
6. **Don't use emojis in code** - some systems don't support Unicode
7. **Don't skip testing** - at least run `reflex run` and click around

---

## 🎯 Contribution Ideas

**Not sure where to start? Here are some ideas:**

**Beginner-Friendly:**

- Add CSV export to existing pages (Tables, Entity list, Timeline)
- Improve error messages with helpful suggestions
- Add tooltips explaining features
- Fix typos or improve documentation
- Add new anomaly detection keywords

**Intermediate:**

- Add new document format support (e.g., EPUB, Markdown)
- Improve OCR accuracy for specific document types
- Add new entity relationship types
- Improve UI/UX on specific pages
- Add keyboard shortcuts

**Advanced:**

- Implement new analysis features (e.g., author attribution)
- Optimize database queries for large document sets
- Add multi-language support for NER
- Implement advanced visualization options
- Add collaborative features (multi-user support)

**Check [FUTURE_TASKS.md](FUTURE_TASKS.md) for specific planned features!**

---

## 🐛 Found a Security Issue?

**Do NOT open a public issue.**

For security vulnerabilities, please email the maintainer directly (check GitHub profile for contact) or use GitHub's private security advisory feature.

Security issues will be addressed promptly and you'll be credited (unless you prefer to remain anonymous).

---

## ❓ Questions?

- **General questions**: Open a [GitHub Discussion](https://github.com/mantisfury/ArkhamMirror/discussions)
- **Bug reports**: Open an [Issue](https://github.com/mantisfury/ArkhamMirror/issues)
- **Feature requests**: Open an [Issue](https://github.com/mantisfury/ArkhamMirror/issues) with the "enhancement" label
- **Code questions**: Comment on relevant PRs or issues

---

## 📜 Code of Conduct

**Be respectful and constructive.**

This project is built to help journalists, researchers, and investigators uncover truth. Let's keep the community welcoming and professional.

- Be patient with newcomers
- Provide constructive feedback on PRs
- Assume good intentions
- No harassment, discrimination, or toxicity
- Focus on the work, not the person

---

## 🙏 Thank You

Every contribution, no matter how small, makes ArkhamMirror better for journalists and researchers around the world.

Whether you:

- Fixed a typo in the docs
- Reported a bug
- Added a major feature
- Helped another contributor

**You're making a difference.** Thank you for being part of this project.

---

_Last Updated: 2025-12-12_
