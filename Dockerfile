FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        fonts-dejavu-core \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install \
        "aiogram==3.13.1" \
        "SQLAlchemy[asyncio]==2.0.36" \
        "asyncpg==0.30.0" \
        "alembic==1.13.3" \
        "APScheduler==3.10.4" \
        "pytz==2024.2" \
        "Pillow==11.0.0" \
        "pydantic==2.10.3" \
        "pydantic-settings==2.6.1" \
        "python-dotenv==1.0.1" \
        "structlog==24.4.0"

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN mkdir -p /app/assets/flags

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "app.main"]
