# Media Forensics Shard

Media metadata extraction and forensic analysis for images within the SHATTERED framework.

## Overview

The Media Forensics shard provides comprehensive image authenticity analysis capabilities, including:

- **EXIF Extraction**: Extract and analyze embedded metadata from images (camera info, GPS, timestamps)
- **Perceptual Hashing**: Generate perceptual hashes for image similarity detection
- **C2PA Verification**: Verify Content Authenticity Initiative (C2PA) provenance data
- **ELA Analysis**: Error Level Analysis to detect potential image manipulation
- **Sun Position Verification**: Cross-reference claimed photo timestamps with calculated sun positions
- **Similar Image Detection**: Find visually similar images across the document corpus
- **Reverse Image Search**: Search for image appearances across the web

## Installation

```bash
cd packages/arkham-shard-media-forensics
pip install -e .

# For C2PA support (optional)
pip install -e ".[c2pa]"
```

## Dependencies

- **arkham-frame**: Core framework (required)
- **Pillow**: Image processing
- **exifread**: EXIF metadata extraction
- **pysolar**: Sun position calculations
- **scipy**: Scientific computing for ELA
- **c2pa-python**: C2PA verification (optional)

## Configuration

### Reverse Image Search API Keys (Optional)

The similar image search feature works in two modes:

1. **Without API Keys (Default)**: Generates clickable URLs to perform manual reverse image searches on:
   - Google Lens
   - Google Images
   - TinEye
   - Yandex Images
   - Bing Visual Search

2. **With API Keys**: Enables automated reverse image search with results returned directly in the UI.

#### Available API Keys

Add these to your `.env` file or `docker-compose.yml` environment section:

| Variable | Service | Cost | Sign Up |
|----------|---------|------|---------|
| `TINEYE_API_KEY` | TinEye | Paid | [tineye.com/developers](https://tineye.com/developers) |
| `GOOGLE_VISION_API_KEY` | Google Cloud Vision | Free tier + paid | [Cloud Console](https://console.cloud.google.com/apis/library/vision.googleapis.com) |
| `SERPAPI_KEY` | SerpAPI (Google Images) | Free tier (100/mo) | [serpapi.com](https://serpapi.com/) |

#### Example Configuration

**In `.env` file:**
```bash
# TinEye - Commercial reverse image search with extensive database
TINEYE_API_KEY=your-tineye-api-key

# Google Cloud Vision - Web detection and similar images
GOOGLE_VISION_API_KEY=your-google-vision-api-key

# SerpAPI - Google Images results (has free tier: 100 searches/month)
SERPAPI_KEY=your-serpapi-key
```

**In `docker-compose.yml`:**
```yaml
services:
  app:
    environment:
      - TINEYE_API_KEY=${TINEYE_API_KEY}
      - GOOGLE_VISION_API_KEY=${GOOGLE_VISION_API_KEY}
      - SERPAPI_KEY=${SERPAPI_KEY}
```

#### Recommended Setup

For most users, we recommend:

1. **Start without API keys** - The manual search URLs work well for occasional use
2. **Add SerpAPI** if you need automated results - Their free tier (100 searches/month) is generous
3. **Add TinEye** for professional use - Best database for finding image origins and modifications

## API Endpoints

All endpoints are prefixed with `/api/media-forensics/`:

- `POST /analyze/{document_id}` - Run full forensic analysis on an image
- `GET /analyses/{analysis_id}` - Get analysis results
- `GET /analyses/count` - Get total analysis count (for navigation badge)
- `GET /document/{document_id}/metadata` - Get extracted EXIF metadata
- `GET /document/{document_id}/ela` - Get ELA analysis image
- `GET /document/{document_id}/c2pa` - Get C2PA verification results
- `POST /similar` - Find similar images by perceptual hash

## Events

### Published
- `media.metadata.extracted` - EXIF/metadata extraction complete
- `media.hash.computed` - Perceptual hash generated
- `media.c2pa.verified` - C2PA verification complete
- `media.ela.generated` - ELA analysis complete
- `media.similar.found` - Similar images detected

### Subscribed
- `document.ingested` - Auto-analyze newly ingested images
- `document.processed` - Process images after document processing

## Architecture

```
arkham_shard_media_forensics/
├── __init__.py          # Package exports
├── shard.py             # Shard implementation
├── api.py               # FastAPI routes
├── models.py            # Pydantic models
└── services/
    ├── __init__.py
    ├── exif_service.py      # EXIF extraction
    ├── hash_service.py      # Perceptual hashing
    ├── c2pa_service.py      # C2PA verification
    ├── ela_service.py       # Error Level Analysis
    └── sun_service.py       # Sun position verification
```

## License

MIT
