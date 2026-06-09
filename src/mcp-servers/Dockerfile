# Base Dockerfile for Healthcare MCP Servers (Azure Functions Python v2)
# Usage: build with --build-arg SERVER_NAME=<server-dir>
#
# Each MCP server is an Azure Functions Python v2 app.
# We use the official Azure Functions Python image so the Functions
# host and GRPC worker are pre-configured.
#
# NOTE: This image is linux/amd64 only. On Apple Silicon Macs the
# docker-compose.yml sets platform: linux/amd64 to run via Rosetta.

FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ARG SERVER_NAME
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    AzureWebJobsStorage= \
    AzureWebJobsSecretStorageType=files \
    FUNCTIONS_WORKER_RUNTIME=python \
    MCP_PROTOCOL_VERSION=2025-06-18

# Pre-provision a default host key so function-level auth works out of the box.
# In production Azure manages keys; locally this avoids 401s.
RUN mkdir -p /azure-functions-host/Secrets && \
    echo '{"masterKey":{"name":"master","value":"docker-master-key","encrypted":false},"functionKeys":[{"name":"default","value":"docker-default-key","encrypted":false}]}' \
    > /azure-functions-host/Secrets/host.json

# Copy shared base (mcp_base.py) into the function app root
COPY shared/mcp_base.py /home/site/wwwroot/mcp_base.py

# Copy the entire server directory (supports multi-module consolidated servers)
COPY ${SERVER_NAME}/ /home/site/wwwroot/

# Install dependencies
RUN pip install --no-cache-dir -r /home/site/wwwroot/requirements.txt
