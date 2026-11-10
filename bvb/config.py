import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
DB_PATH = DATA_DIR / "bvb.sqlite"


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()
