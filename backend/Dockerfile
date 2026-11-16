# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./

# An extra CA certificate can be supplied for builds behind a TLS-inspecting proxy:
#   docker build --secret id=extra_ca,src=/path/to/ca.crt backend
# It is used only during this step and is not stored in the image.
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then \
      export PIP_CERT=/run/secrets/extra_ca SSL_CERT_FILE=/run/secrets/extra_ca; \
    fi; \
    pip install --no-cache-dir uv==0.11.32 \
    && uv sync --frozen --no-dev --no-install-project

COPY . .
RUN useradd --system --uid 10001 lodgeos && chown -R lodgeos /app
USER lodgeos
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# Migrations are a separate, explicit release step (see docs/DEPLOYMENT.md).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
