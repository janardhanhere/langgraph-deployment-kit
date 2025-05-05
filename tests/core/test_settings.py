"""
Tests for the simplified Settings module used in deployment mode.
"""
import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from core.settings import Settings


def test_settings_default_values():
    """Test default settings values in deployment mode."""
    settings = Settings(_env_file=None)
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8080
    assert settings.MODE == "deployment"


def test_settings_base_url():
    """Test the BASE_URL computed property."""
    settings = Settings(HOST="0.0.0.0", PORT=8000, _env_file=None)
    assert settings.BASE_URL == "http://0.0.0.0:8000"


def test_settings_is_dev():
    """Test the is_dev() method."""
    settings = Settings(MODE="dev", _env_file=None)
    assert settings.is_dev() is True

    settings = Settings(MODE="deployment", _env_file=None)
    assert settings.is_dev() is False


def test_settings_with_langfuse():
    """Test settings with Langfuse configuration."""
    with patch.dict(
        os.environ,
        {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
            "LANGFUSE_HOST": "https://custom.langfuse.com",
        },
        clear=True,
    ):
        settings = Settings(_env_file=None)
        assert settings.LANGFUSE_PUBLIC_KEY == SecretStr("pk-test")
        assert settings.LANGFUSE_SECRET_KEY == SecretStr("sk-test")
        assert settings.LANGFUSE_HOST == "https://custom.langfuse.com"


def test_settings_with_database_config():
    """Test settings with database configuration."""
    with patch.dict(
        os.environ,
        {
            "DATABASE_TYPE": "postgres",
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "testdb",
        },
        clear=True,
    ):
        settings = Settings(_env_file=None)
        assert settings.DATABASE_TYPE == "postgres"
        assert settings.POSTGRES_USER == "testuser"
        assert settings.POSTGRES_PASSWORD == SecretStr("testpass")
        assert settings.POSTGRES_HOST == "localhost"
        assert settings.POSTGRES_PORT == 5432
        assert settings.POSTGRES_DB == "testdb"
