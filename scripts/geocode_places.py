# scripts/geocode_places.py
"""
Geocode place names from data/place_counts_raw.csv (produced by NER step).
Produces data/places_geocoded.csv and data/geocode_suspect_manual_review_needed.csv
"""
from pathlib import Path
import pandas as pd
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

PLACE_COUNTS = DATA / "place_counts_raw.csv"
OUT = DATA / "places_geocoded.csv"
SUSPECT = DATA / "geocode_suspect_manual_review_needed.csv"

if not PLACE_COUNTS.exists():
    raise SystemExit(f"{PLACE_COUNTS} not found — run NER locally first to create it.")

df = pd.read_csv(PLACE_COUNTS)
top = df.head(200)['place'].astype(str).tolist()   # limit the scope
geolocator = Nominatim(user_agent="dracula_text_miner_local")
rows = []
suspect = []

for p in top:
    try:
        time.sleep(1)   # be polite
        loc = geolocator.geocode(p, timeout=10)
        if loc:
            rows.append({"place": p, "lat": loc.latitude, "lon": loc.longitude, "raw": str(loc)})
            # crude suspect check: many short tokens, or unusual bbox - you can expand this
            if len(p) < 4 or "," in p:
                suspect.append({"place": p, "lat": loc.latitude, "lon": loc.longitude, "raw": str(loc)})
        else:
            suspect.append({"place": p, "reason": "no_result"})
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        suspect.append({"place": p, "reason": f"error:{e}"})
        continue

pd.DataFrame(rows).to_csv(OUT, index=False)
pd.DataFrame(suspect).to_csv(SUSPECT, index=False)
print("Wrote", OUT, "and", SUSPECT)
