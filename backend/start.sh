#!/bin/bash

# Start Celery worker in the background
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1 &

# Start FastAPI server in the foreground
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
