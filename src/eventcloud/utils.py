from pathlib import Path

import air

BASE_DIR = Path(__file__).resolve().parent
jinja = air.JinjaRenderer(directory=str(BASE_DIR / "templates"))
