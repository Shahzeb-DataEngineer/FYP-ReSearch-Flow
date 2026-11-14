#!/bin/sh
# Start Ollama, pull the models ReSearch Flow needs on first boot,
# then stay in the foreground serving.
#
# Models live in /root/.ollama, which Railway mounts as a persistent
# volume, so a pull only happens once: on later boots the models are
# already present and this script skips straight to serving.
set -eu

MODELS="qwen2.5:3b nomic-embed-text"

ollama serve &
SERVE_PID=$!

# Wait for the server to answer before pulling.
for i in $(seq 1 60); do
  if ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

INSTALLED="$(ollama list 2>/dev/null || true)"
for model in $MODELS; do
  case "$INSTALLED" in
    *"$model"*) echo "Model already present: $model" ;;
    *) echo "Pulling model: $model"; ollama pull "$model" ;;
  esac
done

echo "Ollama ready with models: $MODELS"

# Serve in the foreground until the container stops.
wait "$SERVE_PID"
