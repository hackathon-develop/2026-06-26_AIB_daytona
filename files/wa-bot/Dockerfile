# Builds the Daytona SNAPSHOT (the reusable environment).
# Deliberately bakes only dependencies, NOT the app code: the code is git-cloned
# into the running sandbox once, then updated in place by CI (git pull). That keeps
# this image stable so you only rebuild the snapshot when requirements.txt changes.
#
# Build into a Daytona snapshot named "wa-bot":
#   daytona snapshot create wa-bot --dockerfile ./Dockerfile --context .
# (verify exact flags with: daytona snapshot create --help)

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /home/daytona/app
EXPOSE 8000
