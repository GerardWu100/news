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

# Serve as an unprivileged account. The server needs no privileged port and no
# system file, so a compromise of the application code reaches nothing but the
# mounted data directory. The identifiers are fixed so the files this container
# writes into the mounted directory keep a stable owner across rebuilds.
# The account is called "appuser" because Debian's base image already defines a
# system group and user named "news" (gid 9), which would make groupadd fail.
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["news-server", "--host", "0.0.0.0", "--port", "8000"]
