# Tools image for the gate jobs scan, probe and judge (.gitlab-ci.yml, D-014).
# The build job builds and pushes it when its tag is missing. The tag is the first 12 hex digits
# of the SHA-256 of this file (TOOLS_TAG in .gitlab-ci.yml); .gitlab/ci/check.sh checks them.
#
# Ubuntu 24.04 has QEMU 8.2. QEMU 7.2 and later emulate AVX and AVX2 (TCG), so the
# EPYC-Milan model (x86-64-v3) can run. Ubuntu 22.04 has QEMU 6.2, which cannot.
FROM ubuntu:24.04

ARG CRANE_VERSION=0.22.1
ARG CRANE_SHA256=0ab7a1d6932a213aed964ce97666c3077fe691c8606413674a8b3e0b9ec4cda0

# qemu-user: the CPU probe (F3). strace and time: the offline and memory floors (F8, F7).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl python3 python3-venv qemu-user strace time \
 && rm -rf /var/lib/apt/lists/*

# crane exports the pushed image as a root filesystem, with no Docker daemon in the job.
RUN curl -fsSL -o /tmp/crane.tar.gz \
      "https://github.com/google/go-containerregistry/releases/download/v${CRANE_VERSION}/go-containerregistry_Linux_x86_64.tar.gz" \
 && echo "${CRANE_SHA256}  /tmp/crane.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/crane.tar.gz -C /usr/local/bin crane \
 && rm /tmp/crane.tar.gz

# The jobs install the floor package from their checkout into this venv.
RUN python3 -m venv /opt/floor
ENV PATH=/opt/floor/bin:$PATH
