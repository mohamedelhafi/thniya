ARG PYTHON_VERSION=3.13.16-slim-trixie
FROM python:${PYTHON_VERSION}

RUN apt-get update \
 && apt-get install -y --no-install-recommends osmium-tool ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Le dépôt est monté sur /work ; le paquet citydata vit dans data/scripts
WORKDIR /work
ENV PYTHONPATH=/work/data/scripts \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python", "-m", "citydata"]
CMD ["--help"]
