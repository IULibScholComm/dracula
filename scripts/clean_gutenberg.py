# scripts/clean_gutenberg.py
"""
Cleaner/splitter for Project Gutenberg plain-text Dracula.

Strategy:
 - Locate chapter-heading positions in the raw file (so we don't lose headings
   because of an earlier normalization step).
 - Slice the raw text by those positions.
 - Tidy each slice (collapse line-breaks into paragraphs, normalize Unicode).
Outputs:
 - resources/dracula_clean.txt
 - resources/chapters_plain/01.txt, 02.txt, ...
Run:
    python scripts/clean_gutenberg.py
"""
import re
from pathlib import Path
import unicodedata

SRC = Path("resources/dracula.txt")
OUT_ALL = Path("resources/dracula_clean.txt")
OUT_CHAPTER_DIR = Path("resources/chapters_plain")
OUT_CHAPTER_DIR.mkdir(parents=True, exist_ok=True)

raw = SRC.read_text(encoding="utf-8")

def normalize_unicode(s: str) -> str:
    return unicodedata.normalize("NFKC", s)

def collapse_whitespace_paragraphs(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = s.split("\n")
    new_lines = []
    buffer = []
    for ln in lines:
        if not ln.strip():
            if buffer:
                paragraph = " ".join(p.strip() for p in buffer)
                new_lines.append(paragraph)
                buffer = []
            new_lines.append("")  # paragraph break
        else:
            buffer.append(ln)
    if buffer:
        paragraph = " ".join(p.strip() for p in buffer)
        new_lines.append(paragraph)
    out = "\n\n".join([ln for ln in new_lines if ln is not None])
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()

def roman_to_int(s: str) -> int:
    s = s.upper().strip()
    roman_map = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
    val = 0
    prev = 0
    for ch in reversed(s):
        curr = roman_map.get(ch, 0)
        if curr < prev:
            val -= curr
        else:
            val += curr
        prev = curr
    return val

def find_chapter_matches_in_raw(s: str):
    """
    Find chapter heading match objects in the raw text.
    Prefer uppercase 'CHAPTER' matches; fallback to liberal '/Chapter' or 'Chapter'.
    """
    # 1) strict uppercase CHAPTER
    re_upper = re.compile(r'(?m)^\s*CHAPTER\s+([IVXLCDM]+|\d+)\b[^\n]*')
    matches = list(re_upper.finditer(s))
    if len(matches) >= 10:
        return matches

    # 2) liberal forms (/Chapter, Chapter, CHAPTER), case-insensitive
    re_liberal = re.compile(r'(?m)^\s*(?:/Chapter\s+|Chapter\s+|CHAPTER\s+)\s*([IVXLCDM]+|\d+)\b[^\n]*', flags=re.IGNORECASE)
    matches = list(re_liberal.finditer(s))
    if matches:
        return matches

    # 3) fallback: any line that starts with Chapter-like token
    re_any = re.compile(r'(?m)^\s*(?:/Chapter|Chapter|CHAPTER)\b[^\n]*', flags=re.IGNORECASE)
    return list(re_any.finditer(s))

# --- run ---
print("Raw file size (chars):", len(raw))
# Prefer to cut off Gutenberg header/footer for the final outputs, but find headings in raw
matches = find_chapter_matches_in_raw(raw)
print(f"Found {len(matches)} candidate chapter-heading matches in raw.")

def build_chunks_from_matches(s: str, matches):
    if not matches:
        return [("FULL_TEXT", s.strip())]
    chunks = []
    # include any leading preface text before first match
    if matches[0].start() > 0:
        pre = s[:matches[0].start()].strip()
        if pre:
            chunks.append(("PREFACE", pre))
    for i, m in enumerate(matches):
        heading_line = m.group(0).strip()
        num_token = m.group(1) if m.groups() else None
        if num_token:
            if num_token.isdigit():
                num = int(num_token)
            else:
                num = roman_to_int(num_token)
            label = f"CHAPTER {num:02d}"
        else:
            label = re.sub(r'\s+', ' ', heading_line)[:60].strip()
        body_start = m.end()
        body_end = matches[i+1].start() if i+1 < len(matches) else len(s)
        body_raw = s[body_start:body_end].strip()
        full_body = heading_line + "\n\n" + body_raw
        chunks.append((label, full_body))
    return chunks

chapters = build_chunks_from_matches(raw, matches)
print(f"Detected {len(chapters)} chunks (including PREFACE if present).")
for i, (lbl, body) in enumerate(chapters[:12], start=1):
    print(f"{i:02d}: {lbl} (approx {len(body):,} chars)")

# Tidy and write outputs, removing Gutenberg footer if present
def strip_gutenberg_footer(s: str) -> str:
    m_end = re.search(r"\*\*\*\s*END OF (THIS|THE) PROJECT GUTENBERG EBOOK.*\*\*\*", s, flags=re.IGNORECASE|re.DOTALL)
    if m_end:
        return s[:m_end.start()].strip()
    # fallback marker
    return re.split(r"End of the Project Gutenberg EBook", s, flags=re.IGNORECASE)[0].strip()

with OUT_ALL.open("w", encoding="utf-8") as fh:
    for label, body_raw in chapters:
        body_nofooter = strip_gutenberg_footer(body_raw)
        body_tidy = normalize_unicode(collapse_whitespace_paragraphs(body_nofooter))
        marker = f"[{label}]"
        fh.write(marker + "\n\n")
        fh.write(body_tidy + "\n\n")

for label, body_raw in chapters:
    m = re.search(r'CHAPTER\s+(\d+)', label, flags=re.IGNORECASE)
    if m:
        idx = int(m.group(1))
        fname = OUT_CHAPTER_DIR / f"{idx:02d}.txt"
    else:
        safe = re.sub(r'[^0-9A-Za-z_-]', '_', label)[:40]
        fname = OUT_CHAPTER_DIR / f"{safe}.txt"
    body_nofooter = strip_gutenberg_footer(body_raw)
    body_tidy = normalize_unicode(collapse_whitespace_paragraphs(body_nofooter))
    fname.write_text(body_tidy, encoding="utf-8")

print(f"Wrote full witness to: {OUT_ALL.resolve()}")
print(f"Wrote per-chapter files to: {OUT_CHAPTER_DIR.resolve()} (total {len(list(OUT_CHAPTER_DIR.glob('*.txt')))} files)")
