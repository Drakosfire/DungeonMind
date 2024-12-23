import pytest
from fastapi.testclient import TestClient
from app import app
from session_management import GlobalSessionManager
import os
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@pytest.fixture(scope="session")
def test_app():
    logger.debug("Setting up test app")
    return app

@pytest.fixture(scope="session")
def test_client(test_app):
    logger.debug("Creating test client with localhost base URL")
    client = TestClient(
        test_app, 
        base_url="http://localhost",
        headers={"host": "localhost"}  # Explicitly set host header
    )
    return client

@pytest.fixture(scope="function")
def session_manager():
    return GlobalSessionManager(session_timeout_minutes=1)

# Print confirmation that this module is being loaded
logger.debug("conftest.py loaded")