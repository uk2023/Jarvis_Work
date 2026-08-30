#!/usr/bin/env bash

set -euo pipefail

# ------------------------------------------------------------------
# 1. Embedding model (used for memory/semantic search vector encoding)
# ------------------------------------------------------------------

MODEL_URL="https://huggingface.co/xenova/all-MiniLM-L6-v2/resolve/main/onnx/model.onnx"
TOKENIZER_URL="https://huggingface.co/xenova/all-MiniLM-L6-v2/resolve/main/tokenizer.json"

echo "Downloading all-MiniLM-L6-v2.onnx..."
curl -L --progress-bar -o "all-MiniLM-L6-v2.onnx" "$MODEL_URL"

echo "Downloading tokenizer.json..."
curl -L --progress-bar -o "tokenizer.json" "$TOKENIZER_URL"

# ------------------------------------------------------------------
# 2. Chat LLM (Qwen2.5-3B-Instruct, q4_k_m quant) -- this was MISSING
# from download.sh entirely before. This model is what
# HybridLLMBridge/LlamaCppEngine actually loads for chat replies
# (core/orchestration/llm_bridge.py). Without it, brain.think_and_
# respond() has nothing to talk to -- which is exactly the "model se
# communicate nahi ho raha" symptom. Official Qwen repo, exact
# filename cli.py already expects.
# ------------------------------------------------------------------

QWEN_URL="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"

mkdir -p models
if [ -f "models/qwen2.5-3b-instruct-q4_k_m.gguf" ]; then
    echo "models/qwen2.5-3b-instruct-q4_k_m.gguf already exists, skipping."
else
    echo "Downloading qwen2.5-3b-instruct-q4_k_m.gguf (~2.1 GB, this takes a while)..."
    curl -L --progress-bar -o "models/qwen2.5-3b-instruct-q4_k_m.gguf" "$QWEN_URL"
fi

echo "Download completed successfully."

