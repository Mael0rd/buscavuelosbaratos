"""Genera worker/src/origins.json a partir de config.yaml (se corre al desplegar)."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))

origins, countries = {}, []
for cid, c in cfg["countries"].items():
    countries.append({"id": cid, "name": c["name"], "flag": c["flag"], "cc": c["cc"],
                      "origins": c["origins"]})
    for code in c["origins"]:
        origins[code] = {"name": cfg["origin_names"][code], "country": cid,
                         "country_name": c["name"], "cc": c["cc"], "flag": c["flag"]}

out = ROOT / "worker" / "src" / "origins.json"
out.write_text(json.dumps({"origins": origins, "countries": countries}, ensure_ascii=False, indent=1),
               encoding="utf-8")
print(f"{out}: {len(origins)} ciudades de salida")
