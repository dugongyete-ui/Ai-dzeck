#!/bin/bash
echo "=== Starting Frontend on port 5000 ==="
cd /home/runner/workspace/frontend
PORT=5000 BACKEND_URL=http://localhost:8000 npx vite --port 5000 --host 0.0.0.0
