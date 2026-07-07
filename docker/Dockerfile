FROM python:3.13-slim-bookworm AS base
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip uv
WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN python -m venv "${VIRTUAL_ENV}"

FROM base AS dependencies

# Install third-party dependencies in a dedicated layer so that changing
# application source does not bust the dependency-install cache.
# Only a change to pyproject.toml or uv.lock triggers a re-install.
COPY pyproject.toml uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy the full application source and install the project package
# (including console-script entry points such as vultron-demo).
# Code-only changes only bust this layer, not the dependency layer above.
COPY . /app/
ENV PYTHONPATH=/app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

FROM dependencies AS test
# Install pytest and dev dependencies
RUN uv sync --frozen --dev
# Run the unit tests
CMD ["uv", "run", "pytest"]

FROM dependencies AS docs
CMD ["sh", "-lc", "uv run mkdocs serve --dev-addr 0.0.0.0:8000 --config-file ${MKDOCS_CONFIG_FILE:-mkdocs.yml}"]

FROM dependencies AS vultrabot_demo
CMD ["uv", "run", "vultrabot"]

FROM dependencies AS api-dev
RUN mkdir -p /app/data
CMD ["uv","run","uvicorn","vultron.adapters.driving.fastapi.main:app","--host","0.0.0.0","--port","7999","--reload"]

FROM dependencies AS demo
COPY docker/demo-entrypoint.sh /app/demo-entrypoint.sh
RUN chmod +x /app/demo-entrypoint.sh
ENTRYPOINT ["/app/demo-entrypoint.sh"]

FROM dependencies AS dev

# Install dev tooling (git and curl already present from base stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    zsh tmux jq unzip sudo ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Custom CA certs (SEI/Zscaler); no-op if no .crt files are present
COPY .devcontainer/certs /usr/local/share/ca-certificates/custom/
RUN find /usr/local/share/ca-certificates/custom -type f ! -name '*.crt' -delete \
    && if find /usr/local/share/ca-certificates/custom -type f -name '*.crt' -print -quit | grep -q .; then \
        update-ca-certificates; \
    fi

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 (required by Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# AWS CLI v2
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip

ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Bake dev dependencies (pytest, mypy, black, etc.) into the image layer
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --dev

# Create non-root developer user matching the VS Code devcontainer convention
RUN groupadd --gid 1000 vscode \
    && useradd --uid 1000 --gid 1000 -m -s /bin/zsh vscode \
    && echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode

# Claude Code CLI (installed as vscode user so it lands in ~/.local)
RUN su - vscode -c "curl -fsSL https://claude.ai/install.sh | bash"

WORKDIR /workspaces
USER vscode
