"""Shared test fixtures. Runs before any test module is imported."""
import os, sys, tempfile

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Create one test DB for the whole session
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
TEST_DB_PATH = _tmp.name


def pytest_configure(config):
    """Override DB_PATH before any test runs."""
    import config as appconfig
    appconfig.DB_PATH = TEST_DB_PATH

    import db
    db.init_db()
