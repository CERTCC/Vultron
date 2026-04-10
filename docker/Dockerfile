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
RUN uv sync --frozen --no-install-project

# Copy the full application source and install the project package
# (including console-script entry points such as vultron-demo).
# Code-only changes only bust this layer, not the dependency layer above.
COPY . /app/
ENV PYTHONPATH=/app
RUN uv sync --frozen

FROM dependencies AS test
# Install pytest and dev dependencies
RUN uv sync --frozen --dev
# Run the unit tests
CMD ["uv", "run", "pytest"]

FROM dependencies AS docs
CMD ["uv", "run", "mkdocs", "serve", "--dev-addr", "0.0.0.0:8000"]

FROM dependencies AS vultrabot_demo
CMD ["uv", "run", "vultrabot"]

FROM dependencies AS api-dev
ENV LOG_LEVEL=DEBUG
RUN mkdir -p /app/data
CMD ["uv","run","uvicorn","vultron.adapters.driving.fastapi.main:app","--host","0.0.0.0","--port","7999","--reload"]

FROM dependencies AS demo
COPY docker/demo-entrypoint.sh /app/demo-entrypoint.sh
RUN chmod +x /app/demo-entrypoint.sh
ENTRYPOINT ["/app/demo-entrypoint.sh"]
