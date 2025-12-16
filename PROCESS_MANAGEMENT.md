# Process Management Guide

This guide covers how to manage ArkhamMirror's services after installation.

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python system_status.py` | Check all services |
| `python system_status.py --start-all` | Start everything |
| `python system_status.py --stop-all` | Stop everything |
| `python reflex_server.py start` | Start web app |
| `python worker_manager.py start` | Start background workers |

---

## System Status Tool

The `system_status.py` script is your main health check tool.

### Check Everything
```bash
python system_status.py
```

This shows:
- Docker services (PostgreSQL, Qdrant, Redis)
- Reflex server status
- Worker status
- Port availability

### Start All Services
```bash
python system_status.py --start-all
```

Starts in order:
1. Docker containers
2. Reflex web server
3. Background workers

### Stop All Services
```bash
python system_status.py --stop-all
```

Stops everything gracefully.

---

## Reflex Server Management

The web application runs on Reflex (React/Next.js frontend + FastAPI backend).

### Commands
```bash
python reflex_server.py start    # Start the server
python reflex_server.py stop     # Stop the server
python reflex_server.py restart  # Restart the server
python reflex_server.py status   # Check if running
```

### Ports
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000

### Manual Start (Alternative)
```bash
cd app
reflex run
```

---

## Worker Management

Background workers process documents asynchronously (OCR, parsing, embedding, etc.).

### Commands
```bash
python worker_manager.py start      # Start 1 worker
python worker_manager.py start 3    # Start 3 workers
python worker_manager.py stop       # Stop all workers
python worker_manager.py restart    # Restart workers
python worker_manager.py status     # Check worker status
python worker_manager.py list       # List active workers
```

### Manual Start (Alternative)
```bash
cd app
python run_rq_worker.py
```

---

## Docker Services

Infrastructure runs in Docker containers.

### Commands (from docker/ directory)
```bash
cd docker
docker compose up -d    # Start containers
docker compose down     # Stop containers
docker compose ps       # Check status
docker compose logs     # View logs
```

### Services
| Service | External Port | Internal Port |
|---------|---------------|---------------|
| PostgreSQL | 5435 | 5432 |
| Qdrant | 6343 | 6333 |
| Redis | 6380 | 6379 |

### Data Location
All Docker data is stored in `DataSilo/`:
- `DataSilo/postgres/` - Database files
- `DataSilo/qdrant/` - Vector database
- `DataSilo/redis/` - Queue data

---

## Troubleshooting

### Port Already in Use
If you see "port already in use" errors:
```bash
# Check what's using the port
netstat -ano | findstr :3000    # Windows
lsof -i :3000                   # Mac/Linux

# Kill the process or change ports in .env
```

### Docker Not Starting
```bash
# Ensure Docker Desktop is running
docker info

# Check for container issues
cd docker
docker compose logs
```

### Workers Not Processing
```bash
# Check Redis connection
python -c "import redis; r = redis.from_url('redis://localhost:6380'); print(r.ping())"

# Check worker logs
python worker_manager.py status
```

### Database Connection Issues
```bash
# Test PostgreSQL connection
python -c "from config import DATABASE_URL; print(DATABASE_URL)"

# Reset database (WARNING: deletes all data)
cd app
python -c "from arkham.services.db.reset_db import reset_database; reset_database()"
```

### Frontend Not Loading
1. Check if Reflex server is running: `python reflex_server.py status`
2. Check browser console for errors
3. Try clearing browser cache
4. Restart: `python reflex_server.py restart`

---

## LM Studio (Local LLM)

For AI features, LM Studio must be running with server mode enabled.

### Setup
1. Download [LM Studio](https://lmstudio.ai)
2. Load a model (recommended: `qwen3-vl-8b` for vision features)
3. Start the server (default port: 1234)

### Test Connection
```bash
curl http://localhost:1234/v1/models
```

---

## Logs

Application logs are stored in `DataSilo/logs/`.

### View Recent Logs
```bash
# Windows
type DataSilo\logs\arkham.log

# Mac/Linux
tail -f DataSilo/logs/arkham.log
```

---

## Complete Startup Sequence

For a fresh start:

```bash
# 1. Start Docker services
cd docker
docker compose up -d
cd ..

# 2. Wait for databases to initialize (first time only)
sleep 10

# 3. Start the application
python system_status.py --start-all

# 4. Open browser
# http://localhost:3000
```

---

## Complete Shutdown Sequence

```bash
python system_status.py --stop-all
cd docker
docker compose down
```
