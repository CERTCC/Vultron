FROM python:3.12-slim-bookworm AS base
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
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
CMD ["uv", "run", "--project=/app/src", "pytest"]

FROM dependencies AS docs
CMD ["uv", "run", "--project=/app/src", "mkdocs", "serve", "--dev-addr", "0.0.0.0:8000"]
