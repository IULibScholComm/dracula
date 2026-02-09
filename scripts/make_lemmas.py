# scripts/make_lemmas.py
"""
Compute chapter-level lemmatized strings and save data/chap_lemmas.csv.
Usage:
    python scripts/make_lemmas.py
"""
from pathlib import Path
import re
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RES = ROOT / "resources"
DATA.mkdir(exist_ok=True)

CLEAN = RES / "dracula_clean.txt"
OUT = DATA / "chap_lemmas.csv"

if not CLEAN.exists():
    raise SystemExit(f"Missing {CLEAN}; run scripts/clean_gutenberg.py first or place the cleaned text here.")

# lightweight chapter-splitter (same logic as your notebook)
def load_chapters(txt):
    parts = re.split(r'(?m)^\[(PREFACE|CHAPTER\s+\d+|FULL_TEXT)\]\s*$', txt, flags=re.IGNORECASE)
    if len(parts) < 3:
        split_points = re.split(r'(?m)^\[CHAPTER\s+\d+\]', txt)
        chapters = [{"chapter": i, "marker": f"CHAPTER {i:02d}", "text": b.strip()} for i,b in enumerate(split_points, start=1)]
    else:
        chapters = []
        i = 1
        for j in range(1, len(parts), 2):
            marker = parts[j].strip()
            body = parts[j+1].strip() if j+1 < len(parts) else ""
            m = re.search(r'CHAPTER\s+(\d+)', marker, flags=re.IGNORECASE)
            if m:
                idx = int(m.group(1))
            elif marker.upper().startswith("PREFACE"):
                idx = 0
            else:
                idx = i
            chapters.append({"chapter": idx, "marker": marker, "text": body})
            i += 1
    chapters = sorted(chapters, key=lambda r: (r['chapter'] if isinstance(r['chapter'], int) else 9999))
    return pd.DataFrame([{"chapter": int(c["chapter"]), "marker": c["marker"], "text": c["text"]} for c in chapters])

txt = CLEAN.read_text(encoding="utf-8")
chap_df = load_chapters(txt)

# Try to use spaCy lemmatizer if available; fallback: simple tokenization
use_spacy = True
lemmas = []
try:
    import spacy
    nlp = spacy.load("en_core_web_sm", disable=["parser","ner","textcat"])
    for doc in nlp.pipe(chap_df["text"].fillna("").astype(str).tolist(), batch_size=8):
        lemma_tokens = [t.lemma_.lower() for t in doc if t.is_alpha]
        lemmas.append(" ".join(lemma_tokens))
    logging.info("spaCy lemmas computed.")
except Exception as e:
    logging.warning(f"spaCy not available or failed ({e}). Falling back to regex tokenization.")
    for t in chap_df["text"].fillna("").astype(str):
        tokens = re.findall(r"[A-Za-z]+", t.lower())
        lemmas.append(" ".join(tokens))

out_df = pd.DataFrame({
    "chapter": chap_df["chapter"].astype(int),
    "marker": chap_df["marker"].astype(str),
    "lemmas_str": lemmas,
    "word_count": chap_df["text"].str.split().str.len().fillna(0).astype(int)
})
out_df.to_csv(OUT, index=False, encoding="utf-8")
logging.info(f"Wrote {OUT} ({len(out_df)} rows).")
