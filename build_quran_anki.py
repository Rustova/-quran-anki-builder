#!/usr/bin/env python3
"""Build a text-only, globally cumulative Quran Anki deck from QCF4."""
from __future__ import annotations
import argparse, html, json, zipfile
from pathlib import Path

EXPECTED_PAGES = 604
EXPECTED_VERSES = 6236
EXPECTED_CHAPTERS = 114
DECK_ID = 2026112201
MODEL_ID = 2026112202

def load_pages(root: Path):
    files = sorted((root / "pages").glob("[0-9][0-9][0-9].json"))
    if len(files) != EXPECTED_PAGES:
        raise ValueError(f"Expected 604 QCF4 pages; found {len(files)}")
    pages, all_keys = [], set()
    for expected, path in enumerate(files, 1):
        data = json.loads(path.read_text(encoding="utf-8"))
        if int(data.get("page", -1)) != expected:
            raise ValueError(f"Page numbering mismatch: {path}")
        page_lines = []
        for line in data.get("lines", []):
            words = []
            for w in line.get("words", []):
                typ = w.get("type")
                text = str(w.get("text") or "").strip()
                if not text:
                    continue
                if typ == "word" and w.get("verse_key"):
                    key = w["verse_key"]
                    words.append({"text": text, "verse": key, "position": w.get("position")})
                    all_keys.add(key)
                elif typ == "bismillah":
                    sid = w.get("sura")
                    if sid is None:
                        sid = next((s.get("id") for s in data.get("surahs", [])), None)
                    if sid is not None:
                        key = f"{int(sid)}:1"
                        words.append({"text": text, "verse": key, "position": 0})
                        all_keys.add(key)
            if words:
                page_lines.append({"page": expected, "line": int(line.get("line", 0)), "words": words})
        pages.extend(page_lines)
    idx = json.loads((root / "index.json").read_text(encoding="utf-8"))
    meta = idx.get("meta", {})
    chapters = idx.get("chapters", [])
    if meta.get("total_pages") != EXPECTED_PAGES or meta.get("total_verses") != EXPECTED_VERSES:
        raise ValueError("QCF4 index totals do not match expected totals")
    if len(chapters) != EXPECTED_CHAPTERS:
        raise ValueError(f"Expected 114 surahs; found {len(chapters)}")
    expected_keys = {f"{int(c['id'])}:{a}" for c in chapters for a in range(1, int(c["verses_count"])+1)}
    if all_keys != expected_keys:
        raise ValueError(f"Verse coverage mismatch: missing {len(expected_keys-all_keys)}, extra {len(all_keys-expected_keys)}")
    return pages, all_keys

def group_lines(lines, minimum=3):
    """Group actual consecutive Mushaf lines, never cutting an ayah at a boundary."""
    groups, start = [], 0
    while start < len(lines):
        end = min(start + minimum, len(lines))
        while end < len(lines):
            last_left = lines[end-1]["words"][-1]["verse"]
            first_right = lines[end]["words"][0]["verse"]
            if last_left != first_right:
                break
            end += 1
        # Avoid a tiny final fragment when possible, without splitting an ayah.
        if 0 < len(lines)-end < minimum:
            while end < len(lines):
                last_left = lines[end-1]["words"][-1]["verse"]
                first_right = lines[end]["words"][0]["verse"]
                end += 1
                if last_left != first_right:
                    break
        groups.append(lines[start:end])
        start = end
    return groups

def group_text(group):
    return " ".join(w["text"] for line in group for w in line["words"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qcf4", default="quran-qcf4")
    ap.add_argument("--output", default="Quran_Cumulative_604_Pages.apkg")
    args = ap.parse_args()
    import genanki

    lines, verse_keys = load_pages(Path(args.qcf4))
    groups = group_lines(lines, 3)

    model = genanki.Model(
        MODEL_ID, "حفظ القرآن – تلاوة تراكمية",
        fields=[{"name": n} for n in [
            "Id","Kind","FrontLabel","FrontSurah","FrontJuz","FrontBody","FrontPage",
            "BackLabel","BackSurah","BackJuz","BackBody","BackPage","FrontText","BackText","Meta"]],
        templates=[{
            "name":"تلاوة تراكمية",
            "qfmt":'<div class="wrap"><div class="hdr"><div class="surah">{{FrontSurah}}</div><div class="juz">{{FrontJuz}}</div></div><div class="label">{{FrontLabel}}</div><div class="body">{{FrontBody}}</div><div class="ftr">{{FrontPage}}</div></div>',
            "afmt":'<div class="wrap"><div class="hdr"><div class="surah">{{BackSurah}}</div><div class="juz">{{BackJuz}}</div></div><div class="label">{{BackLabel}}</div><div class="body">{{BackBody}}</div><div class="ftr">{{BackPage}}</div></div>'
        }],
        css="""
.card{font-family:Amiri,"Traditional Arabic","Geeza Pro",serif;font-size:20px;direction:rtl;text-align:right;background:#fbf8f1;color:#1c1914;margin:0;padding:0}
.wrap{max-width:760px;margin:0 auto;padding:12px 16px 16px}
.hdr{display:flex;justify-content:space-between;align-items:baseline;font-size:.95em;color:#6b5b3e;border-bottom:1px solid #d9cfb8;padding-bottom:6px}
.surah{font-weight:bold}.label{text-align:center;font-size:.72em;color:#8a7a58;margin:12px 0 4px}
.body{margin:6px 0 14px;line-height:2.1}.q{font-size:1.18em;line-height:2.05;word-spacing:.12em;direction:rtl;text-align:justify}
.new{background:#f4e6b9;border-radius:5px;padding:2px 4px}.ftr{text-align:right;font-size:.95em;color:#6b5b3e;border-top:1px solid #d9cfb8;padding-top:6px}
.nightMode.card{background:#17150f;color:#efe8d6}.nightMode .hdr,.nightMode .ftr,.nightMode .label{color:#b9ab86;border-color:#3a3426}.nightMode .new{background:#57451f}
"""
    )
    deck = genanki.Deck(DECK_ID, "حفظ القرآن الكريم – التلاوة التراكمية")
    cumulative_parts = []
    verse_order = []
    previous_end_page = None

    for n, group in enumerate(groups, 1):
        new_text = group_text(group)
        previous_text = " ".join(cumulative_parts)
        start_page, end_page = group[0]["page"], group[-1]["page"]
        line_range = f"{group[0]['line']}–{group[-1]['line']}" if start_page == end_page else f"{group[0]['line']}–{group[-1]['line']} عبر الصفحات {start_page}–{end_page}"
        if previous_text:
            front_body = f'<div class="q">{html.escape(previous_text)}</div>'
        else:
            front_body = '<div class="prompt">ابدأ من أول المصحف، ثم أكمل المقطع التالي</div>'
        back_body = (f'<div class="q">{html.escape(previous_text)} </div>' if previous_text else '')
        back_body += f'<div class="q"><span class="new">{html.escape(new_text)}</span></div>'
        page_label = f"صفحة {start_page}" if start_page == end_page else f"صفحات {start_page}–{end_page}"
        meta = {
            "kind":"progressive", "unit":n, "page_start":start_page, "page_end":end_page,
            "lines":[[x["page"],x["line"]] for x in group],
            "verses":list(dict.fromkeys(w["verse"] for ln in group for w in ln["words"]))
        }
        fields = [
            f"{n:05d}", "تلاوة تراكمية",
            "اقرأ المحفوظ من أول المصحف ثم أكمل",
            "القرآن الكريم", "", front_body, page_label,
            "المقطع الجديد مميز", "القرآن الكريم", "", back_body, page_label,
            html.escape(previous_text), html.escape(new_text), json.dumps(meta,ensure_ascii=False)
        ]
        deck.add_note(genanki.Note(model=model, fields=fields, guid=genanki.guid_for("quran-cumulative-global",n)))
        cumulative_parts.append(new_text)
        for ln in group:
            for w in ln["words"]:
                if not verse_order or verse_order[-1] != w["verse"]:
                    verse_order.append(w["verse"])

    genanki.Package(deck).write_to_file(args.output)
    with zipfile.ZipFile(args.output) as z:
        if z.testzip() or "collection.anki2" not in z.namelist():
            raise ValueError("APKG archive validation failed")
    report = {
        "pages":EXPECTED_PAGES, "surahs":EXPECTED_CHAPTERS, "unique_verses":len(verse_keys),
        "ordered_verse_keys":len(set(verse_order)), "mushaf_lines":len(lines),
        "groups":len(groups), "notes":len(deck.notes), "output":args.output,
        "images":"none", "cumulative":"global from Al-Fatihah through the current group",
        "grouping":"at least 3 actual QCF4 lines where possible; ayahs are not split",
        "text_source":"QCF4 word text; user's uploaded TXT comparison is not included in this public build"
    }
    Path("build-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
