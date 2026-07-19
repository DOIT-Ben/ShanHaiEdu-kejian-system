# syntax=docker/dockerfile:1.7

FROM node:22.22.0-bookworm-slim@sha256:7cc56ef285a8568121537d17b05e72128f01b89c54607b51acf084a50ef483f3 AS node-runtime
FROM ghcr.io/astral-sh/uv:0.10.6@sha256:f75b8eba2090c1dd8758da8201362386f5eda41e7bc1d43ec5b216039650fcda AS uv-runtime
FROM python:3.12.12-slim-bookworm@sha256:2986c55feb36e6cae00fa1fefb454283e4b33f35e75ff8bdd123b134130be301 AS workspace

ARG DEV_UID=1000
ARG DEV_GID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    COREPACK_HOME=/opt/corepack/home \
    PNPM_HOME=/home/developer/.local/share/pnpm \
    PATH=/workspace/.venv/bin:/opt/corepack:/home/developer/.local/share/pnpm:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

COPY --from=node-runtime /usr/local/ /usr/local/
COPY --from=uv-runtime /uv /uvx /usr/local/bin/

RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=5 -o Acquire::https::Timeout=30 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::https::Timeout=30 install --yes --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        ffmpeg \
        fontconfig \
        fonts-dejavu-core \
        fonts-liberation2 \
        git \
        jq \
        libpq-dev \
        libreoffice-core \
        libreoffice-impress \
        openssh-client \
        poppler-utils \
        postgresql-client \
        procps \
        redis-tools \
        ripgrep \
        tini \
        unzip \
    && rm -rf /var/lib/apt/lists/*

COPY --chmod=0755 infra/dev/git-wrapper.sh /usr/local/bin/git

RUN install -d /opt/corepack /opt/corepack/home \
    && corepack enable pnpm --install-directory /opt/corepack \
    && corepack prepare pnpm@10.30.2 --activate \
    && groupadd --gid "${DEV_GID}" developer \
    && useradd --create-home --uid "${DEV_UID}" --gid "${DEV_GID}" --shell /bin/bash developer \
    && install -d -o developer -g developer \
        /workspace \
        /home/developer/.cache/uv \
        /home/developer/.local/share/pnpm/store \
    && chown -R developer:developer /home/developer

WORKDIR /workspace
USER developer
RUN pnpm --version
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]
