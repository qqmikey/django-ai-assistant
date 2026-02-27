FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml MANIFEST.in README.md /workspace/
COPY src /workspace/src
COPY example_project/requirements.txt /tmp/requirements.txt

RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt \
    && pip install -e /workspace

COPY example_project/app /workspace/example_project/app
COPY example_project/entrypoint.sh /workspace/example_project/entrypoint.sh
RUN chmod +x /workspace/example_project/entrypoint.sh

WORKDIR /workspace/example_project/app

CMD ["/workspace/example_project/entrypoint.sh"]
