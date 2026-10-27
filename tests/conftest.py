"""
Pytest configuration and fixtures.
"""
import pytest
import logging

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Disable verbose logging for some modules during tests
logging.getLogger('crypto').setLevel(logging.WARNING)
logging.getLogger('storage').setLevel(logging.WARNING)
logging.getLogger('identity').setLevel(logging.WARNING)
logging.getLogger('messaging').setLevel(logging.WARNING)


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging level for each test."""
    yield
    # Reset after test if needed