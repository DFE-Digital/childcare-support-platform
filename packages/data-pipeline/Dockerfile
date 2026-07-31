FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates wget && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Add intermediate CA certs that some government sites fail to include in
# their TLS chain. Without these, requests/urllib3 cannot verify the leaf
# cert against the root. AIA URLs serve certs over plain HTTP.
RUN wget -qO /usr/local/share/ca-certificates/digicert-g2-intermediate.crt \
        "https://cacerts.digicert.com/DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt.pem" && \
    wget -qO /tmp/sectigo-ov-r36.der \
        "http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt" && \
    openssl x509 -inform DER -in /tmp/sectigo-ov-r36.der \
        -out /usr/local/share/ca-certificates/sectigo-ov-r36.crt -outform PEM && \
    rm /tmp/sectigo-ov-r36.der && \
    update-ca-certificates

# Point requests/urllib3 at the system CA bundle (which now includes the
# intermediates) instead of certifi's root-only bundle.
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

RUN pip install --no-cache-dir pip certifi --upgrade

# Install Node.js 22 LTS for Zod validation script
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Tippecanoe for PMTiles vector tile generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libsqlite3-dev zlib1g-dev git && \
    git clone --depth=1 https://github.com/felt/tippecanoe.git /tmp/tippecanoe && \
    cd /tmp/tippecanoe && make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/tippecanoe && \
    apt-get purge -y build-essential git && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/dagster/app

COPY pyproject.toml .
COPY data/postcode_lad_lookup.csv.gz data/
COPY bsil_pipeline/ bsil_pipeline/
COPY tests/ tests/

RUN pip install --no-cache-dir -e . watchfiles

COPY dagster.yaml .

ENV DAGSTER_HOME=/opt/dagster/app

# Default: run Dagster gRPC code server
EXPOSE 4000
CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-m", "bsil_pipeline.definitions"]
