# Credit Evidence Engine — one image for validation runs, the guard, and verification.
#
#   docker build -t credit-evidence-engine .
#   docker run --rm -v "$PWD/evidence:/app/evidence" credit-evidence-engine \
#       run --settings settings/baseline.yaml --split proof
#
# The engine itself makes no network calls. The only outbound traffic is to the
# assistant endpoint named in the settings file (a NIM inside the bank's cluster,
# in an air-gapped install). Search defaults to word-overlap, which needs no
# embedding service.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssh-client git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY settings ./settings
COPY corpus ./corpus
COPY packs ./packs

# Run as an unprivileged user; OpenShift assigns an arbitrary UID in group 0.
RUN mkdir -p runs evidence changes guard audit \
    && chgrp -R 0 /app && chmod -R g=u /app
USER 1001

ENTRYPOINT ["evidence"]
CMD ["--help"]
