# config_loader.py

import os
import streamlit as st
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
from core.security import redact_log, mask_phi
from logger import logger

load_dotenv()

# === Exception for Missing Required Configs ===
class ConfigError(Exception):
    pass

# === Azure Key Vault Setup (lazy initialization) ===
_keyvault_client = None

def get_from_secret_manager(var_name: str) -> str:
    """
    Attempts to retrieve a secret from Azure Key Vault.
    Returns None if Key Vault is not available or the secret is not found.
    """
    global _keyvault_client
    try:
        vault_url = os.getenv("AZURE_KEYVAULT_URL")
        if not vault_url:
            return None  # Key Vault not configured

        if not _keyvault_client:
            credential = DefaultAzureCredential()
            _keyvault_client = SecretClient(vault_url=vault_url, credential=credential)

        secret = _keyvault_client.get_secret(var_name)
        return secret.value
    except Exception as e:
        logger.warning(redact_log(mask_phi(f"⚠️ Key Vault lookup failed for {var_name}: {e}")))
        return None  # Gracefully fallback to next layer

def get_env(var_name: str, required: bool = True, default: str = None) -> str:
    """
    Retrieves configuration value in the following order:
    1. Azure Key Vault (if ENV=production or AZURE_KEYVAULT_URL is set)
    2. Streamlit secrets (for local/dev testing)
    3. Environment variable or .env file
    """
    value = None

    # 1. Azure Key Vault
    if os.getenv("ENV", "").lower() == "production" or os.getenv("AZURE_KEYVAULT_URL"):
        value = get_from_secret_manager(var_name)

    # 2. Streamlit secrets
    try:
        if value is None and hasattr(st, "secrets") and var_name in st.secrets:
            value = st.secrets[var_name]
    except Exception:
        pass

    # 3. Environment variable / .env
    if value is None:
        value = os.getenv(var_name, default)

    # 4. Enforce required
    if required and not value:
        logger.error(redact_log(mask_phi(f"❌ Missing required environment variable: {var_name}")))
        raise ConfigError(f"Missing required environment variable: {var_name}")

    return value

# === Centralized Configuration Loader ===
class AppConfig:
    def __init__(self):
        # === OpenAI ===
        self.OPENAI_API_KEY = get_env("OPENAI_API_KEY")
        self.OPENAI_MODEL = get_env("OPENAI_MODEL", default="gpt-3.5-turbo")

        # === Microsoft Graph ===
        self.GRAPH_CLIENT_ID = get_env("GRAPH_CLIENT_ID", required=False)
        self.GRAPH_CLIENT_SECRET = get_env("GRAPH_CLIENT_SECRET", required=False)
        self.GRAPH_TENANT_ID = get_env("GRAPH_TENANT_ID", required=False)
        self.GRAPH_SENDER_EMAIL = get_env("GRAPH_SENDER_EMAIL", required=False)

        # === NEOS ===
        self.NEOS_API_KEY = get_env("NEOS_API_KEY", required=False)
        self.NEOS_BASE_URL = get_env("NEOS_BASE_URL", default="https://app.neosconnect.com/api/v1")
        self.NEOS_COMPANY_ID = get_env("NEOS_COMPANY_ID", required=False)

        # === Dropbox ===
        self.DROPBOX_APP_KEY = get_env("DROPBOX_APP_KEY", required=False)
        self.DROPBOX_APP_SECRET = get_env("DROPBOX_APP_SECRET", required=False)
        self.DROPBOX_REFRESH_TOKEN = get_env("DROPBOX_REFRESH_TOKEN", required=False)
        self.DROPBOX_MASTER_DASHBOARD_PATH = get_env("DROPBOX_MASTER_DASHBOARD_PATH", default="/Master Dashboard.xlsx")

# === Accessor ===
def get_config() -> AppConfig:
    return AppConfig()
