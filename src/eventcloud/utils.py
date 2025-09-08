import air
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
jinja = air.JinjaRenderer(directory=str(BASE_DIR / "templates"))
