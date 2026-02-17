FROM python:3.13-slim-bookworm AS base
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip uv
WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN python -m venv "${VIRTUAL_ENV}"

FROM base AS dependencies

ARG BASE_DIR=..

# Copy the files we need
COPY ${BASE_DIR}/ /app
# Set the environment variable
ENV PYTHONPATH=/app
COPY ${BASE_DIR}/pyproject.toml /app/pyproject.toml
COPY ${BASE_DIR}/uv.lock /app/uv.lock

# install requirements
RUN uv sync --frozen

FROM dependencies AS test
ENV PYTHONPATH=/app
# Install pytest and dev dependencies
RUN uv sync --frozen --dev
# Run the unit tests
CMD ["uv", "run", "pytest"]

FROM dependencies AS docs
CMD ["uv", "run", "mkdocs", "serve", "--dev-addr", "0.0.0.0:8000"]

FROM dependencies AS vultrabot_demo
CMD ["uv", "run", "vultrabot"]

FROM dependencies AS api-dev
CMD ["uv","run","uvicorn","vultron.api.main:app","--host","0.0.0.0","--port","7999","--reload"]

FROM dependencies AS receive-report-demo
ENV PYTHONPATH=/app
# The BASE_URL in the script will be overridden via environment variable
CMD ["uv", "run", "python", "-m", "vultron.scripts.receive_report_demo"]
