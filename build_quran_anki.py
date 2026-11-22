#!/usr/bin/env python3
"""Build a cumulative-recitation Anki deck from QCF4 page JSON files."""
from __future__ import annotations
import argparse, collections, html, json, re, sys, zipfile
from pathlib import Path

EXPECTED_PAGES = 604
EXPECTED_VERSES = 6236
EXPECTED_CHAPTERS = 114
DECK_ID = 2026112201
MODEL_ID = 2026112202

def clean_word(w):
    # QCF4 word records are the authoritative page-layout text.
    return str(w.get("text", "")).strip()

def load_pages(root: Path):
    pages_dir = root / "pages"
    files = sorted(pages_dir.glob("[0-9][0-9][0-9].json"))
    if len(files) != EXPECTED_PAGES:
        raise ValueError(f"Expected {EXPECTED_PAGES} page JSON files; found {len(files)}")
    pages = []
    verse_keys = set()
    for expected, path in enumerate(files, 1):
        data = json.loads(path.read_text(encoding="utf-8"))
        if int(data.get("page", -1)) != expected:
            raise ValueError(f"Page numbering mismatch in {path}")
        lines = []
        for line in data.get("lines", []):
            words = []
            for w in line.get("words", []):
                if w.get("type") == "word" and w.get("verse_key"):
                    text = clean_word(w)
                    if text:
                        words.append({"text": text, "verse": w["verse_key"], "position": w.get("position")})
                        verse_keys.add(w["verse_key"])
            if words:
                lines.append({"line": int(line.get("line", len(lines)+1)), "words": words})
        pages.append({"page": expected, "lines": lines})
    if len(verse_keys) != EXPECTED_VERSES:
        raise ValueError(f"Expected {EXPECTED_VERSES} unique verse keys; found {len(verse_keys)}")
    expected_keys = set()
    for surah, count in enumerate([
      7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,
      112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,
      89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,
      12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,
      30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6
    ], 1):
        expected_keys.update(f"{surah}:{ayah}" for ayah in range(1, count+1))
    if verse_keys != expected_keys:
        missing = sorted(expected_keys - verse_keys)[:10]
        extra = sorted(verse_keys - expected_keys)[:10]
        raise ValueError(f"Verse-key coverage mismatch. Missing={missing}; extra={extra}")
    return pages, verse_keys

def group_lines(lines, min_lines=3):
    """Create contiguous groups, ending only after a complete ayah."""
    groups, current = [], []
    for line in lines:
        current.append(line)
        line_count = len(current)
        if line_count >= min_lines:
            last_verse = current[-1]["words"][-1]["verse"]
            # A boundary is safe only when the next line does not continue this ayah.
            # Defer the decision until the next line is available.
            groups.append(None) if False else None
    # Greedy safe boundaries: a line boundary is safe if its final verse differs
    # from the first verse on the next line.
    groups, start = [], 0
    while start < len(lines):
        end = min(start + min_lines, len(lines))
        while end < len(lines):
            left_last = lines[end-1]["words"][-1]["verse"]
            right_first = lines[end]["words"][0]["verse"]
            if left_last != right_first:
                break
            end += 1
        # If this would leave a short tail, absorb it into this group.
        if len(lines) - end in (1, 2):
            end = len(lines)
        groups.append(lines[start:end])
        start = end
    return groups

def render_words(lines):
    out = []
    for line in lines:
        text = " ".join(w["text"] for w in line["words"])
        if text:
            out.append(f'<div class="qline">{html.escape(text)}</div>')
    return "".join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qcf4", default="quran-qcf4")
    ap.add_argument("--output", default="Quran_Cumulative_604_Pages.apkg")
    args = ap.parse_args()
    try:
        import genanki
    except ImportError:
        raise SystemExit("Missing dependency genanki")
    pages, verse_keys = load_pages(Path(args.qcf4))
    model = genanki.Model(
        MODEL_ID,
        "Quran Cumulative Recitation",
        fields=[{"name":"Page"},{"name":"Group"},{"name":"Front"},{"name":"Cumulative"},{"name":"NewMaterial"}],
        templates=[{
            "name":"Cumulative recitation",
            "qfmt":'<div class="top">Madinah Mushaf · Page {{Page}}</div><div class="prompt">{{Front}}</div>',
            "afmt":'{{FrontSide}}<hr id="answer"><div class="label">Cumulative text</div><div class="quran">{{Cumulative}}</div><div class="label new">New material in this step</div><div class="quran highlight">{{NewMaterial}}</div>',
        }],
        css="""
.card {font-family:Arial,sans-serif;text-align:center;color:#222;background:#fff;font-size:20px;padding:12px}
.top{font-size:15px;color:#777;margin-bottom:20px}.prompt{font-size:22px;font-weight:600}
.label{font-size:14px;color:#777;margin:18px 0 8px}.label.new{color:#287a45}
.quran{direction:rtl;text-align:justify;font-family:serif;font-size:25px;line-height:2.0}
.qline{padding:0 2px}.highlight{background:#eaf6ed;border-radius:8px;padding:8px}
"""
    )
    deck = genanki.Deck(DECK_ID, "Quran · Cumulative Recitation · Madinah Mushaf (Hafs)")
    note_count = 0
    for page in pages:
        groups = group_lines(page["lines"], 3)
        cumulative = []
        for idx, group in enumerate(groups, 1):
            cumulative.extend(group)
            first_line = group[0]["line"]
            last_line = group[-1]["line"]
            front = f"Recite from the beginning of page {page['page']} through line {last_line}.<br><small>Step {idx} · lines {first_line}–{last_line}</small>"
            note = genanki.Note(model=model, fields=[
                str(page["page"]), f"{idx}/{len(groups)}", front,
                render_words(cumulative), render_words(group)
            ], guid=genanki.guid_for("qcf4", page["page"], idx, first_line, last_line))
            deck.add_note(note)
            note_count += 1
    package = genanki.Package(deck)
    package.write_to_file(args.output)
    with zipfile.ZipFile(args.output) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f"APKG ZIP integrity failure: {bad}")
        if "collection.anki2" not in z.namelist():
            raise ValueError("APKG is missing collection.anki2")
    report = {
        "pages": len(pages), "unique_verses": len(verse_keys),
        "notes": note_count, "output": args.output,
        "qcf4_layout": "page/line/word-position source",
        "text_comparison": "not performed: user Tanzil TXT is not stored in this public repository"
    }
    Path("build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
