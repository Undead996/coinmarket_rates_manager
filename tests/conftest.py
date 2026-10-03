"""
pytest conftest — mock the database layer so tests can run without a real MySQL server.

Must be at the correct level for module-level patches to take effect before
any of the app's modules are imported.
"""

import sys
from unittest.mock import MagicMock

# 1) Prevent pymysql import (used by SQLAlchemy)
sys.modules["pymysql"] = MagicMock()

# 2) Mock src.db.database before any other code touches it
import src.db.database as db_mod

db_mod.engine = MagicMock()
db_mod.SessionLocal = MagicMock()
db_mod.Base.metadata.create_all = MagicMock()
db_mod.validate_mysql_config = MagicMock(return_value={
    "MYSQL_HOST": "localhost",
    "MYSQL_PORT": "3306",
    "MYSQL_USER": "test",
    "MYSQL_PASSWORD": "test",
    "MYSQL_DATABASE": "test",
})

# 3) Mock src.db.database.get_db — will be overridden per test via dependency_overrides
db_mod.get_db = MagicMock()