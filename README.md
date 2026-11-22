# Quran Cumulative Anki Builder

Build a cumulative-recitation Anki deck for the 604-page Madinah Mushaf (Hafs).

## Source data
- QCF4: page, line, and word-position layout.
- Uthmani Quran text: textual comparison source (kept local; do not commit private uploads).

## Required validation
- 604 pages
- 114 surahs
- 6,236 ayahs
- No missing or duplicated ayahs
- Ayah boundaries preserved in recitation groups
- Page/line mapping checked against QCF4

## Build status
Repository initialized. The APKG builder and automated validation workflow are not yet added.


## Build
A push to the builder or workflow files triggers GitHub Actions. The workflow downloads QCF4, validates all 604 page files and all 6,236 verse keys against `index.json`, then builds the APKG artifact.
