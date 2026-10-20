# The Rieux demo service (F13.1, F13.3, D-019): the held whisper.cpp image plus the gateway.
# Build from the repository root with the digest of the image that the gate held:
#   docker build -f deploy/service.Dockerfile --build-arg IMAGE=registry.gitlab.com/<project>/main@sha256:<digest> .
# The gateway is code-owned (.floor/floor/gateway.py). This recipe only adds python3 and starts it.
# whisper-server listens on 127.0.0.1:8081 only. The gateway on $PORT caps the audio at 30 s and
# limits the requests. Cloud Run caps the instances (infra/). No audio is stored.
ARG IMAGE
FROM ${IMAGE}

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

COPY .floor/floor/gateway.py .floor/floor/gateway.html /srv/rieux/

ENV PORT=8080 \
    WHISPER_MODEL=/app/models/ggml-base.en.bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8080
ENTRYPOINT ["python3", "/srv/rieux/gateway.py", "--serve"]
