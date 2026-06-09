#!/usr/bin/env python3
"""Get or create APIM subscription key for testing."""

from azure.identity import DefaultAzureCredential
from azure.mgmt.apimanagement import ApiManagementClient
from azure.mgmt.apimanagement.models import SubscriptionCreateParameters

SUBSCRIPTION_ID = "63862159-43c8-47f7-9f6f-6c63d56b0e17"
RESOURCE_GROUP = "rg-hcmcp-eus2-dev"
APIM_NAME = "healthcaremcp-apim-v4nrndu5paa6o"
SUB_ID = "mcp-passthrough-sub"

credential = DefaultAzureCredential()
client = ApiManagementClient(credential, SUBSCRIPTION_ID)

# Create subscription
print("Creating/updating subscription...")
try:
    sub = client.subscription.create_or_update(
        resource_group_name=RESOURCE_GROUP,
        service_name=APIM_NAME,
        sid=SUB_ID,
        parameters=SubscriptionCreateParameters(
            display_name="MCP Passthrough Debug Subscription",
            scope="/products/mcp-passthrough-product",
            state="active",
        ),
    )
    print(f"Subscription: {sub.name}")
except Exception as e:
    print(f"Create error: {e}")

# Get keys
print("\nFetching subscription keys...")
try:
    secrets = client.subscription.list_secrets(
        resource_group_name=RESOURCE_GROUP,
        service_name=APIM_NAME,
        sid=SUB_ID,
    )
    print(f"\n{'='*60}")
    print("APIM Subscription Key (use this in VS Code MCP config):")
    print(f"{'='*60}")
    print(f"\nPrimary Key: {secrets.primary_key}")
    print(f"\nSecondary Key: {secrets.secondary_key}")
    print(f"\n{'='*60}")
except Exception as e:
    print(f"Secrets error: {e}")
