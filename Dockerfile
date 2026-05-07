FROM python:3.14-slim AS base

ARG BICEP_VERSION=0.30.23
ARG TERRAFORM_VERSION=1.9.8

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# bicep
RUN curl -sSLo /usr/local/bin/bicep \
      "https://github.com/Azure/bicep/releases/download/v${BICEP_VERSION}/bicep-linux-x64" \
 && chmod +x /usr/local/bin/bicep

# terraform
RUN curl -sSLo /tmp/tf.zip \
      "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
 && unzip /tmp/tf.zip -d /usr/local/bin/ \
 && rm /tmp/tf.zip

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

WORKDIR /work
ENTRYPOINT ["bicep2tf"]
CMD ["--help"]
