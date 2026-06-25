import runpy
import sys
from pathlib import Path


APP_DIR = Path(__file__).parent / "biomimetix" / "backend"
sys.path.insert(0, str(APP_DIR))

runpy.run_path(str(APP_DIR / "app.py"), run_name="__main__")
