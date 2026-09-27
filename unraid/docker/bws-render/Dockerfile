FROM debian:bookworm-slim

ARG BWS_VERSION=2.0.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl jq unzip \
 && curl -fsSL \
      "https://github.com/bitwarden/sdk-sm/releases/download/bws-v${BWS_VERSION}/bws-x86_64-unknown-linux-gnu-${BWS_VERSION}.zip" \
      -o /tmp/bws.zip \
 && unzip /tmp/bws.zip -d /usr/local/bin/ \
 && chmod +x /usr/local/bin/bws \
 && rm /tmp/bws.zip \
 && apt-get purge -y --auto-remove curl unzip \
 && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/bin/sh"]
