#!/bin/bash
echo "=== Starting Backend API on port 8000 ==="
cd /home/runner/workspace/backend
export OPENSSL_CONF=/home/runner/workspace/backend/openssl_compat.cnf
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
