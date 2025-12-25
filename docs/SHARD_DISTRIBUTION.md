# Shard Distribution Strategy

How shards are packaged, distributed, and installed.

---

## Strategy: Monorepo + PyPI Packages

**Development**: Single monorepo containing all projects
**Distribution**: Separate pip packages published to PyPI
**End Users**: `pip install` what they need, never touch git

---

## Repository Structure

```
ArkhamMirror/                      # Main repo (monorepo)
├── app/                           # Original Reflex app (monolith)
├── ach-standalone/                # Standalone ACH tool
├── SHATTERED/                     # Next-gen modular architecture
│   ├── packages/
│   │   ├── arkham-frame/          # Core + Dashboard
│   │   ├── arkham-shard-ingest/
│   │   ├── arkham-shard-search/
│   │   ├── arkham-shard-analysis/
│   │   ├── arkham-shard-ach/
│   │   └── arkham-shard-audio/
│   └── docs/
├── docker/                        # Shared Docker infrastructure
└── DataSilo/                      # User data (gitignored)
```

**Why monorepo?**
- Single clone for developers
- Easier cross-package development
- Shared CI/CD infrastructure
- One place to manage everything

**Why separate pip packages?**
- Users install only what they need
- Independent versioning
- Clean dependency management
- No git required for end users

---

## How Users Get Shattered

### Option 1: pip install (Recommended)

```bash
# Core (includes Dashboard)
pip install arkham-frame

# Add shards you want
pip install arkham-shard-ingest
pip install arkham-shard-search
pip install arkham-shard-ach

# Run
python -m arkham_frame
```

Users never clone the repo. They get exactly what they need.

### Option 2: GitHub Release ZIPs

For users who want files without pip:

```
GitHub Releases:
├── arkham-frame-0.1.0.zip
├── arkham-shard-ingest-0.1.0.zip
└── shattered-full-0.1.0.zip      # Everything bundled
```

### Option 3: Clone (Developers Only)

```bash
git clone https://github.com/user/ArkhamMirror
cd ArkhamMirror/SHATTERED/packages/arkham-frame
pip install -e .
```

---

## How pip Packaging Works (Demystified)

### The Magic Explained

pip packages are just ZIP files with a specific structure. Here's all you need:

```
arkham-frame/
├── pyproject.toml      # Package metadata (name, version, dependencies)
├── arkham_frame/       # Your actual code
│   ├── __init__.py
│   └── ...
└── README.md
```

### pyproject.toml (The Only Config You Need)

```toml
[project]
name = "arkham-frame"                    # Package name on PyPI
version = "0.1.0"                         # Version number
description = "ArkhamMirror Shattered Frame"
readme = "README.md"
requires-python = ">=3.10"

# Dependencies - pip installs these automatically
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "sqlalchemy>=2.0.0",
    "redis>=5.0.0",
    "qdrant-client>=1.6.0",
]

# Optional dependencies
[project.optional-dependencies]
dev = ["pytest", "black", "mypy"]

# Entry point for shard discovery
[project.entry-points."arkham.shards"]
dashboard = "arkham_shard_dashboard:DashboardShard"

# Build system (just use hatchling, it works)
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Publishing to PyPI (One-Time Setup)

```bash
# 1. Create PyPI account at pypi.org
# 2. Create API token in account settings
# 3. Install build tools
pip install build twine

# 4. Build the package
cd packages/arkham-frame
python -m build
# Creates: dist/arkham_frame-0.1.0.tar.gz
#          dist/arkham_frame-0.1.0-py3-none-any.whl

# 5. Upload to PyPI
twine upload dist/*
# Enter your API token when prompted

# Done! Users can now: pip install arkham-frame
```

### Automating Releases (GitHub Actions)

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  push:
    tags:
      - 'arkham-frame-v*'    # Triggers on tags like arkham-frame-v0.1.0

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install build tools
        run: pip install build twine

      - name: Build package
        run: |
          cd SHATTERED/packages/arkham-frame
          python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: |
          cd SHATTERED/packages/arkham-frame
          twine upload dist/*
```

Now when you push a tag like `arkham-frame-v0.1.0`, it automatically publishes.

---

## Shard Discovery

Frame automatically finds installed shards via Python entry points.

### How It Works

1. Each shard declares itself in `pyproject.toml`:
   ```toml
   [project.entry-points."arkham.shards"]
   ingest = "arkham_shard_ingest:IngestShard"
   ```

2. Frame discovers all installed shards at startup:
   ```python
   from importlib.metadata import entry_points

   def discover_shards():
       eps = entry_points(group="arkham.shards")
       for ep in eps:
           shard_class = ep.load()
           print(f"Found shard: {ep.name}")
   ```

3. User installs shards, Frame finds them:
   ```bash
   pip install arkham-shard-ingest arkham-shard-search
   python -m arkham_frame
   # Output: Found shard: ingest
   #         Found shard: search
   ```

No configuration needed. Install = enabled.

---

## Version Compatibility

### Shard Dependencies

Each shard specifies compatible Frame versions:

```toml
# arkham-shard-ingest/pyproject.toml
[project]
dependencies = [
    "arkham-frame>=0.1.0,<1.0.0",  # Works with 0.x versions
]
```

### Frame Checks at Startup

```python
if not version_compatible(FRAME_VERSION, shard.required_frame_version):
    logger.error(f"Shard {name} requires Frame {required}, got {FRAME_VERSION}")
    # Don't load incompatible shard
```

---

## Development Workflow

### Working on Frame + Shards Locally

```bash
# Clone once
git clone https://github.com/user/ArkhamMirror
cd ArkhamMirror/SHATTERED/packages

# Install everything in dev mode
pip install -e ./arkham-frame
pip install -e ./arkham-shard-ingest
pip install -e ./arkham-shard-search

# Changes are live - no reinstall needed
# Edit code, restart server, see changes
```

### Adding a New Shard

```bash
# Create from template
cp -r arkham-shard-template arkham-shard-myfeature

# Edit pyproject.toml with new name
# Implement the shard
# Install in dev mode
pip install -e ./arkham-shard-myfeature

# Frame auto-discovers it
```

---

## Release Checklist

### For a New Shard Release

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Commit: `git commit -m "Release arkham-shard-foo v0.2.0"`
4. Tag: `git tag arkham-shard-foo-v0.2.0`
5. Push: `git push origin main --tags`
6. GitHub Action publishes to PyPI

### For Frame Release

Same process, but also:
- Check compatibility with all shards
- Update minimum Frame version in shard docs if needed

---

## Summary

| Audience | How They Get Shattered |
|----------|------------------------|
| End users | `pip install arkham-frame arkham-shard-ingest` |
| Non-pip users | GitHub Release ZIPs |
| Developers | Clone repo, `pip install -e .` |
| Contributors | Clone repo, make PRs |

**Current phase**: Development in monorepo
**Next phase**: First PyPI release when stable

---

*Last Updated: 2025-12-21*
