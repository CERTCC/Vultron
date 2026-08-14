# syntax=docker/dockerfile:1.7-labs

FROM python:3.13-slim-bookworm AS base
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip uv
WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN python -m venv "${VIRTUAL_ENV}"

FROM base AS dep-layer

# Install all third-party + dev packages (but not the project package itself) so
# that a source-only change never busts this expensive layer.
COPY pyproject.toml uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --dev

FROM dep-layer AS dependencies

# Copy the full application source and install the project package
# (including console-script entry points such as vultron-demo).
# Code-only changes only bust this layer, not the dependency layer above.
#
# Dev-only paths are excluded HERE rather than in .dockerignore, because
# .dockerignore applies to the whole build context and would also strip them
# from the `dev` stage that backs the devcontainer. Keep this list in sync with
# the `test` stage below; the `dev` stage deliberately copies everything.
COPY --exclude=.git --exclude=.agents \
     --exclude=.github --exclude=.devcontainer \
     --exclude=.gitignore --exclude=.gitattributes \
     --exclude=archived_notes \
     --exclude=docker/Dockerfile \
     . /app/
ENV PYTHONPATH=/app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

FROM dep-layer AS test
# Same exclusion set as the `dependencies` stage above.
COPY --exclude=.git --exclude=.agents \
     --exclude=.github --exclude=.devcontainer \
     --exclude=.gitignore --exclude=.gitattributes \
     --exclude=archived_notes \
     --exclude=docker/Dockerfile \
     . /app/
ENV PYTHONPATH=/app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --dev
CMD ["uv", "run", "pytest"]

FROM dependencies AS docs
CMD ["sh", "-lc", "uv run mkdocs serve --dev-addr 0.0.0.0:8000 --config-file ${MKDOCS_CONFIG_FILE:-mkdocs.yml}"]

FROM dependencies AS vultrabot_demo
CMD ["uv", "run", "vultrabot"]

FROM dependencies AS api-dev
RUN mkdir -p /app/data
CMD ["uv","run","uvicorn","vultron.adapters.driving.fastapi.main:app","--host","0.0.0.0","--port","7999","--reload"]

FROM dependencies AS demo
COPY --chmod=755 docker/demo-entrypoint.sh /app/demo-entrypoint.sh
ENTRYPOINT ["/app/demo-entrypoint.sh"]

FROM dep-layer AS dev

# Clear VIRTUAL_ENV so uv resolves the project venv from the workspace path,
# not /app/.venv (which is valid for app stages but wrong for devcontainer use).
ENV VIRTUAL_ENV=

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

# start-dev.sh bind-mounts the host ~/.gitconfig read-only, and on macOS its
# credential.helper points at a Homebrew gh path (/usr/local/bin on Intel,
# /opt/homebrew/bin on Apple Silicon). apt installs gh to /usr/bin here, so
# without these links git cannot find the helper and every push inside a slot
# dies with "could not read Username for 'https://github.com'". The mount is
# read-only, so the host config cannot be rewritten — make its path resolve.
RUN ln -sf /usr/bin/gh /usr/local/bin/gh \
    && mkdir -p /opt/homebrew/bin \
    && ln -sf /usr/bin/gh /opt/homebrew/bin/gh

# Node.js 22 (required by Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# markdownlint-cli2
RUN npm install -g markdownlint-cli2

# AWS CLI v2
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip

ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Install project source (after all heavy system tooling is cached).
# The devcontainer needs every TRACKED path — .git, .github, archived_notes,
# .gitignore and docker/Dockerfile included. Anything omitted here shows up as a
# phantom deletion in `git status` inside the container, so this COPY takes no
# --exclude flags by design; add nothing to .dockerignore that this stage needs.
#
# Only two categories are withheld, both via .dockerignore: secrets (.env,
# .devcontainer/*.env), and gitignored paths that start-dev.sh clobber-mounts
# over /app at runtime (.devcontainer, wip_notes, wip_outputs, graphify-out).
# Being gitignored, those cannot surface as phantom deletions.
COPY . /app/
ENV PYTHONPATH=/app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --dev

# Create non-root developer user matching the VS Code devcontainer convention
RUN groupadd --gid 1000 vscode \
    && useradd --uid 1000 --gid 1000 -m -s /bin/zsh vscode \
    && echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode

# Claude Code CLI (installed as vscode user so it lands in ~/.local)
RUN su - vscode -c "curl -fsSL https://claude.ai/install.sh | bash"

# /app is owned by root from the earlier COPY steps; hand it to vscode so
# `git pull` in poststart.sh doesn't fail on dubious-ownership checks.
RUN chown -R vscode:vscode /app

WORKDIR /app
USER vscode
