# Ollama service for Railway. Based on the official ollama/ollama
# image; the entrypoint starts the server and pulls the models on
# first boot. Models persist in the Railway volume mounted at
# /root/.ollama, so later boots skip the pull.
FROM ollama/ollama

# Railway's private network reaches the container on its own IP, not
# loopback, so Ollama must listen on all interfaces. Do NOT generate
# a public domain for this service: the Ollama API has no auth, and
# 0.0.0.0 is only safe because the service stays private-network-only.
ENV OLLAMA_HOST=0.0.0.0:11434

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 11434

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
