import yaml
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "checklists"

def load_checklist(name: str):
    with open(BASE / f"{name}.yaml", "r") as f:
        return yaml.safe_load(f)
