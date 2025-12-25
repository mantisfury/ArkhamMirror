# SHATTERED Startup Guide

Quick reference for starting the SHATTERED development environment.

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm or pnpm

---

## Quick Start

### 1. Install Python Packages (First Time Only)

```bash
cd packages/arkham-frame && pip install -e .
cd packages/arkham-shard-ach && pip install -e .
cd packages/arkham-shard-dashboard && pip install -e .
# Add other shards as needed:
# cd packages/arkham-shard-ingest && pip install -e .
# cd packages/arkham-shard-search && pip install -e .
# etc.
```

### 2. Install Node Dependencies (First Time Only)

```bash
cd packages/arkham-shard-shell && npm install
```

### 3. Start Backend (Port 8105)

```bash
cd packages/arkham-frame
python -m uvicorn arkham_frame.main:app --port 8105 --host 127.0.0.1
```

Or use reload mode for development:
```bash
python -m uvicorn arkham_frame.main:app --port 8105 --reload
```

### 4. Start UI Shell (Port 5173)

In a new terminal:
```bash
cd packages/arkham-shard-shell
npm run dev
```

---

## Access Points

| Service | URL | Description |
|---------|-----|-------------|
| UI Shell | http://localhost:5173 | Main UI (React/Vite) |
| Backend API | http://localhost:8105 | FastAPI backend |
| Health Check | http://localhost:8105/health | Service status |
| API Docs | http://localhost:8105/docs | Swagger UI |

---

## Key Routes

### UI Shell Routes
- `/` - Dashboard home
- `/ach` - ACH Analysis (8-step methodology)
- `/ach/new` - Create new ACH matrix

### API Endpoints
- `GET /health` - Service health and discovered shards
- `GET /api/ach/matrices` - List ACH matrices
- `POST /api/ach/matrices` - Create new matrix
- `GET /api/ach/matrices/{id}` - Get matrix details
- `GET /api/dashboard/health` - Dashboard shard health

---

## Troubleshooting

### Backend won't start
1. Check Python version: `python --version` (need 3.10+)
2. Verify packages installed: `pip list | grep arkham`
3. Check port availability: `netstat -an | grep 8105`

### UI won't start
1. Check Node version: `node --version` (need 18+)
2. Delete node_modules and reinstall: `rm -rf node_modules && npm install`
3. Check for port conflicts on 5173

### Shards not discovered
1. Verify shard package installed: `pip show arkham-shard-ach`
2. Check entry_points in pyproject.toml
3. Look for import errors in backend logs

### API calls failing from UI
1. Verify backend is running on port 8105
2. Check vite.config.ts proxy settings
3. Look at browser Network tab for specific errors

---

## Development Tips

### Adding a new shard
1. Create package in `packages/arkham-shard-{name}/`
2. Add `pyproject.toml` with entry_points
3. Install with `pip install -e .`
4. Restart backend to discover

### Hot reload
- **Backend**: Use `--reload` flag with uvicorn
- **Frontend**: Vite HMR is automatic

### Running workers
```bash
python -m arkham_frame.workers --list-pools  # List all pools
python -m arkham_frame.workers --pool cpu-light --count 2  # Start workers
```

---

## Stop Services

- **Backend**: Ctrl+C in terminal
- **UI**: Ctrl+C in terminal

Or kill by port:
```bash
# Windows
netstat -ano | findstr :8105
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8105
kill -9 <pid>
```
