import os, sys, tempfile
from pathlib import Path
os.environ["WX_AUTH_MODE"]="mock"
os.environ["LLM_MODE"]="scripted"
SERVER=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(SERVER))

# Tests are destructive by design (many cases call reset_and_seed). Keep them
# on a process-specific temporary SQLite database so running pytest can never
# erase the demo's plans, coupons, reservations or merchant updates.
TEST_DB = Path(tempfile.gettempdir()) / f"mallquest-pytest-{os.getpid()}.db"
os.environ["MALL_DB_PATH"] = str(TEST_DB)

def pytest_sessionfinish(session, exitstatus):
    TEST_DB.unlink(missing_ok=True)
