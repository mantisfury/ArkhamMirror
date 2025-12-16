# Migration Guide: Switching Embedding Providers

This guide explains how to switch between `bge-m3` (Standard) and `minilm-bm25` (Minimal) embedding providers.

## Why Migration is Needed

Different embedding models produce vectors of different dimensions:

- **BGE-M3**: 1024 dimensions
- **MiniLM**: 384 dimensions

Qdrant collections are created with a fixed dimension. To switch providers, you must delete the existing collection and re-process all documents to generate new embeddings.

## Step-by-Step Migration

### 1. Update Configuration

Edit `config.yaml` to select your desired provider:

```yaml
embedding:
  provider: "minilm-bm25"  # or "bge-m3"
```

### 2. Install Dependencies (If switching to Minimal)

If you are switching to the minimal tier to save space, you can use the minimal requirements file:

```bash
pip install -r requirements-minimal.txt
```

### 3. Re-Index Documents

We have provided a script to automate the re-indexing process. This script will:

1. Delete the existing Qdrant collection.
2. Re-create it with the correct dimensions for your new provider.
3. Iterate through all documents in the database and re-embed them.

Run the script:

```bash
python scripts/reindex_embeddings.py
```

**Note**: This process may take time depending on the number of documents.

### 4. Verify

Start the application and try a search query to ensure results are returned.

```bash
streamlit run streamlit_app/Search.py
```
