FROM python:3.13-slim

# Copy uv, the Python package manager, from its official image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# The project environment contains both the server and CLI commands.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Keep dependency installation cached until the project metadata changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md config.toml ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["news-server", "--host", "0.0.0.0", "--port", "8000"]
