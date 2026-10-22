# The escape game dashboard. Build context: the repository root.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends gnupg git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The workshop platform's own importer and parser, unchanged (submodule, same commit as the
# plugin inside the ctfd-custom image the rooms run).
COPY vendor/ctfd-workshop-platform/tools/sync_subject.py vendor/ctfd-workshop-platform/tools/ws_parser.py /app/workshop-tools/
# ...and the plugin's GitHub fetcher, for "Load from a public git repository".
COPY vendor/ctfd-workshop-platform/plugins/workshop/source.py /app/workshop-plugin/
# Room contents. Answers are only present encrypted (*.yaml.gpg, see .dockerignore).
COPY subjects /app/subjects
COPY dashboard /app
# Epitech charter from the platform (fonts with their licence, 2025 logos): the ranking that the
# room's projector shows is branded like the rooms themselves. No second copy in this repo.
COPY vendor/ctfd-workshop-platform/plugins/workshop/assets/fonts /app/static/epi/fonts
COPY vendor/ctfd-workshop-platform/plugins/workshop/assets/brand /app/static/epi/brand

RUN useradd --no-log-init -u 1000 dashboard && mkdir -p /data && chown 1000:1000 /data
USER 1000
VOLUME /data
EXPOSE 8000
# Working directory /data: the importer writes its instructor code sheet
# (instructor_codes.<subject>.yaml) to the current directory.
CMD ["gunicorn", "--chdir", "/data", "--pythonpath", "/app", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "app:app"]
