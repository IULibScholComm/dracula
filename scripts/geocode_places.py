# scripts/geocode_places.py
"""
Geocode places from data/place_counts_raw.csv with manual overrides and country hints.

Usage:
  .venv\Scripts\Activate.ps1
  python scripts/geocode_places.py

Outputs:
  - data/places_geocoded.csv        (place, lat, lon)
  - data/geocode_suspect.csv       (rows where lat/lon look suspicious for manual review)
"""

import time
import pandas as pd
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import unicodedata

ROOT = Path(".")
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)
INPUT = OUT / "place_counts_raw.csv"
OUT_GEOCODE = OUT / "places_geocoded.csv"
OUT_SUSPECT = OUT / "geocode_suspect.csv"

if not INPUT.exists():
    raise SystemExit(f"{INPUT} not found. Run ner_spacy_per_chapter to create it.")

place_counts = pd.read_csv(INPUT)
candidates = place_counts['place'].tolist()

# manual overrides for ambiguous or high-value place names
# Edit this dict to correct common mis-geocodes.
manual_overrides = {
    # key: place name as it appears in place_counts_raw.csv
    "Transylvania": {"lat": 46.0, "lon": 25.0, "note": "region center, Romania"},
    "Bistritz": {"lat": 47.1333, "lon": 24.4833, "note": "Bistrița, Romania (historic Bistritz)"},
    "Bistrita": {"lat": 47.1333, "lon": 24.4833, "note": "Bistrița, Romania"},
    "Castle Dracula": {"lat": 46.0620, "lon": 24.6670, "note": "approx. Bran castle / Dracula association (adjust manually)"},
    # add more overrides if you find bad matches
}

# optional country hints to bias geocoding (append to query)
country_hint = {
    "Transylvania": "Romania",
    "Bistritz": "Romania",
    "Bistrita": "Romania",
    "Castle Dracula": "Romania",
    # add other mappings like ("Whitby": "UK") if necessary
}

# small helper to normalize place strings for queries
def normalize(s):
    s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = s.strip()
    return s

geolocator = Nominatim(user_agent="dracula_text_miner")

rows = []
suspects = []

# limit how many we geocode automatically to be polite
MAX_GEOCODE = 1000

for i, place in enumerate(candidates[:MAX_GEOCODE]):
    place_key = normalize(place)
    if not place_key:
        continue

    # skip items that are known to be not geographic (just in case)
    if place_key in {"I", "Sir", "Mr", "Mrs"}:
        continue

    # manual override: use pre-specified coords
    if place_key in manual_overrides:
        ov = manual_overrides[place_key]
        rows.append({"place": place_key, "lat": ov["lat"], "lon": ov["lon"], "source":"override", "note": ov.get("note","")})
        continue

    # build a geocode query: prefer adding a country hint if available
    q = place_key
    if place_key in country_hint:
        q = f"{place_key}, {country_hint[place_key]}"

    try:
        time.sleep(1)  # be polite to Nominatim
        loc = geolocator.geocode(q, timeout=15)
        if loc:
            rows.append({"place": place_key, "lat": loc.latitude, "lon": loc.longitude, "source":"nominatim", "note": ""})
            # simple plausibility check: flag if geocoded lat/lon are in an unexpected continent for some hints
            # e.g. if we hinted Romania but got a US result, flag it.
            if place_key in country_hint:
                hint = country_hint[place_key].lower()
                # crude check: if hint includes "rom" and the lon is in US range, flag
                if hint.startswith("rom") and not (12 <= loc.lon <= 30):  # Romania approx long range
                    suspects.append({"place": place_key, "query": q, "lat": loc.latitude, "lon": loc.longitude, "reason":"country_hint_mismatch"})
        else:
            suspects.append({"place": place_key, "query": q, "lat": None, "lon": None, "reason":"no_match"})
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        suspects.append({"place": place_key, "query": q, "lat": None, "lon": None, "reason": f"error:{e}"})
        continue

# write outputs
if rows:
    pd.DataFrame(rows).to_csv(OUT_GEOCODE, index=False)
else:
    pd.DataFrame(columns=["place","lat","lon","source","note"]).to_csv(OUT_GEOCODE, index=False)

if suspects:
    pd.DataFrame(suspects).to_csv(OUT_SUSPECT, index=False)
else:
    pd.DataFrame(columns=["place","query","lat","lon","reason"]).to_csv(OUT_SUSPECT, index=False)

print(f"Wrote {OUT_GEOCODE} ({len(rows)} rows) and {OUT_SUSPECT} ({len(suspects)} rows).")
print("Review geocode_suspect.csv to fix ambiguous matches; add manual_overrides to scripts/geocode_places.py for corrections.")
