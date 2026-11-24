import os
import sys
import shutil
from pathlib import Path

# Add backend directory to sys.path so 'app' imports resolve cleanly
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# In Vercel serverless environment, the filesystem is read-only except /tmp
# Copy safrons.db to /tmp so SQLite has read and write permissions
tmp_db_path = "/tmp/safrons.db"
src_db_path = backend_dir / "safrons.db"

if os.path.exists("/tmp") and os.access("/tmp", os.W_OK):
    if not os.path.exists(tmp_db_path) and src_db_path.exists():
        try:
            shutil.copyfile(str(src_db_path), tmp_db_path)
        except Exception as e:
            print(f"Warning: Could not copy safrons.db to /tmp: {e}")
    if os.path.exists(tmp_db_path):
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db_path}"
elif not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = f"sqlite:///{src_db_path}"

from app.main import create_app

app = create_app()
