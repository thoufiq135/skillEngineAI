#!/bin/sh

echo "======================================"
echo "Starting Skill Engine AI"
echo "======================================"

echo "Starting FastAPI on port 8100..."

uvicorn backend.api:app \
    --host 0.0.0.0 \
    --port 8100 &

echo "Starting Streamlit on port 8501..."

exec streamlit run app.py \
    --server.address=0.0.0.0 \
    --server.port=8501