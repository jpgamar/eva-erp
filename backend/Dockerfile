FROM python:3.12-slim AS base

# System deps: git for version control, Node.js for Claude Code CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Initialize git repo so Claude Code can commit
RUN git init && git add -A && git commit -m "initial" --allow-empty || true

EXPOSE 8000
RUN chmod +x start.sh
CMD ["./start.sh"]
