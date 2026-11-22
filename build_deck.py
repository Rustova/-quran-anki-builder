import json, glob, os, re, sqlite3, time
from pathlib import Path
import genanki

ROOT = Path("quran-qcf4")
pages_dir = ROOT / "pages"
page_files = sorted(pages_dir.glob("*.json"))
assert len(page_files) == 604, f"Expected 604 QCF4 pages, found {len(page_files)}"

# Read all lines in canonical Mushaf order. QCF4 word text is the source for
# exact page/line placement; no page images or glyph-font rendering is used.
lines = []
for pf in page_files:
    page = json.loads(pf.read_text(encoding="utf-8"))
    pno = int(page["page"])
    for line in page["lines"]:
        parts = []
        verse_keys = []
        for w in line.get("words", []):
            typ = w.get("type")
            txt = (w.get("text") or "").strip()
            if not txt:
                continue
            if typ in ("word", "end", "surah_header", "bismillah", "quarter"):
                parts.append(txt)
                vk = w.get("verse_key")
                if vk and vk not in verse_keys:
                    verse_keys.append(vk)
        if parts:
            lines.append({"page": pno, "line": int(line["line"]),
                          "text": " ".join(parts), "verses": verse_keys})

assert lines, "No text lines were extracted"

# Form contiguous chunks of about three actual Mushaf lines. Extend a chunk
# until the final ayah on its last line is complete; never split an ayah.
chunks = []
i = 0
while i < len(lines):
    start = i
    target = min(i + 3, len(lines))
    seen = set()
    for ln in lines[i:target]:
        seen.update(ln["verses"])
    j = target
    while j < len(lines):
        # If any verse on the current boundary continues onto the next line,
        # extend until that verse has ended.
        current_keys = set(lines[j-1]["verses"])
        next_keys = set(lines[j]["verses"])
        if current_keys & next_keys:
            seen.update(next_keys)
            j += 1
            continue
        break
    group = lines[start:j]
    txt = " ".join(x["text"] for x in group)
    verses = []
    for x in group:
        for vk in x["verses"]:
            if vk not in verses:
                verses.append(vk)
    chunks.append({"lines": group, "text": txt, "verses": verses,
                   "page_start": group[0]["page"], "page_end": group[-1]["page"]})
    i = j

# Validate source coverage: every verse key in QCF4 must appear in sequence.
all_verses = []
for ln in lines:
    for vk in ln["verses"]:
        if not all_verses or all_verses[-1] != vk:
            all_verses.append(vk)
assert len(set(all_verses)) == 6236, f"Expected 6236 distinct verses, got {len(set(all_verses))}"

model = genanki.Model(
    2026112201, "حفظ القرآن – تلاوة تراكمية",
    fields=[{"name":n} for n in ["Id","Kind","FrontLabel","FrontSurah","FrontJuz","FrontBody","FrontPage",
                                  "BackLabel","BackSurah","BackJuz","BackBody","BackPage","FrontText","BackText","Meta"]],
    templates=[{
      "name":"تلاوة تراكمية",
      "qfmt":'''<div class="wrap"><div class="hdr"><div class="surah">{{FrontSurah}}</div><div class="juz">{{FrontJuz}}</div></div><div class="label">{{FrontLabel}}</div><div class="body">{{FrontBody}}</div><div class="ftr">{{FrontPage}}</div></div>''',
      "afmt":'''<div class="wrap"><div class="hdr"><div class="surah">{{BackSurah}}</div><div class="juz">{{BackJuz}}</div></div><div class="label">{{BackLabel}}</div><div class="body">{{BackBody}}</div><div class="ftr">{{BackPage}}</div></div>'''
    }],
    css='''.card{font-family:Amiri,"Traditional Arabic",serif;font-size:20px;direction:rtl;text-align:right;background:#fbf8f1;color:#1c1914;margin:0;padding:0}.wrap{max-width:760px;margin:0 auto;padding:12px 16px 16px}.hdr{display:flex;justify-content:space-between;font-size:.95em;color:#6b5b3e;border-bottom:1px solid #d9cfb8;padding-bottom:6px}.surah{font-weight:bold}.label{text-align:center;font-size:.72em;color:#8a7a58;margin:12px 0 4px}.body{margin:6px 0 14px;line-height:2.1}.q{font-size:1.25em;line-height:2.05;word-spacing:.12em;direction:rtl;white-space:normal}.new{background:#f4e6b9;border-radius:5px;padding:2px 4px}.ftr{text-align:right;font-size:.95em;color:#6b5b3e;border-top:1px solid #d9cfb8;padding-top:6px}.nightMode.card{background:#17150f;color:#efe8d6}.nightMode .hdr,.nightMode .ftr,.nightMode .label{color:#b9ab86;border-color:#3a3426}.nightMode .new{background:#57451f}'''
)

deck = genanki.Deck(2026112202, "حفظ القرآن الكريم – التلاوة التراكمية")
cumulative = []
notes = []
for n, ch in enumerate(chunks, 1):
    prev = " ".join(cumulative)
    new = ch["text"]
    # Preserve the complete cumulative sequence as the recall prompt, and
    # visually mark only the newly introduced text on the answer.
    front = '<div class="q">' + (prev if prev else "بداية المصحف") + '</div>'
    back = '<div class="q">' + (prev + " " if prev else "") + '<span class="new">' + new + '</span></div>'
    meta = {"kind":"progressive","unit":n,"page_start":ch["page_start"],"page_end":ch["page_end"],
            "lines":[[x["page"],x["line"]] for x in ch["lines"]],"verses":ch["verses"]}
    vals = [f"{n:05d}","تلاوة تراكمية","اقرأ من أول المصحف ثم أكمل",
            "القرآن الكريم","",front,f"صفحة {ch['page_start']}" if ch["page_start"]==ch["page_end"] else f"صفحة {ch['page_start']}–{ch['page_end']}",
            "المقطع الجديد مميز","القرآن الكريم","",back,
            f"صفحة {ch['page_start']}" if ch["page_start"]==ch["page_end"] else f"صفحة {ch['page_start']}–{ch['page_end']}",
            prev,new,json.dumps(meta,ensure_ascii=False)]
    note = genanki.Note(model=model, fields=vals, guid=genanki.guid_for("quran-cumulative", n))
    deck.add_note(note)
    cumulative.append(new)

package = genanki.Package(deck)
out = "Quran_Cumulative_604_Pages.apkg"
package.write_to_file(out)
print(json.dumps({"pages":len(page_files),"lines":len(lines),"chunks":len(chunks),
                  "unique_verses":len(set(all_verses)),"notes":len(deck.notes),
                  "output":out,"bytes":os.path.getsize(out)},ensure_ascii=False))
