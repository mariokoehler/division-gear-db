# Division Gear DB — Gear Set Bonus Finder

A small, dependency-free web tool for *Tom Clancy's The Division 2*: pick one or more bonus
types (Hazard Protection, Armor on Kill, Skill Haste, …) and see every Brand Set and Gear Set
that grants them, including full Gear Set 4-piece talents and Backpack/Chest amplifier talents.

**Live page:** https://mariokoehler.github.io/division-gear-db/

## What's here

- `index.html` — the entire tool: markup, styles, logic, and the full dataset, all in one
  self-contained file. No build step, no server — it also works fine opened directly from disk.
- `data/combined_sets.json` — the same dataset, pretty-printed, for reference/editing.
- `data/combined_sets_min.json` — minified version, the one actually embedded into `index.html`.

## Data sources & attribution

The bonus values and talent text in this dataset are extracted directly from *The Division 2*'s
own game files: the Snowdrop engine's `.sdftoc`/`.sdfdata` archives, opened with the community tool
[Hunter](https://tools.dtzxporter.com/) (raw file export enabled), which decompiles the game's
plain-text config format (`.mgearbrand`, `.mgearset`, `.mtalent`). Attribute IDs referenced by
these files were resolved to human-readable stat names by cross-matching against community wiki
data, then applied back across the full dataset.

This was cross-checked against two community-maintained secondary sources:

- [mx-division-builds](https://github.com/mxswat/mx-division-builds) (CC BY-NC-SA 4.0)
- [The Division Wiki](https://thedivision.fandom.com/) — Brand Sets and Gear Sets pages

Cross-checking against the raw game files caught several brands whose in-game values had drifted
from what the wiki documented (balance patches the wiki hadn't caught up on), and surfaced 12
Brand Sets / Gear Sets that neither community source had documented at all.

Because two of the upstream cross-reference sources are CC BY-NC-SA–style community content, treat
the **dataset** (`data/*.json` and the embedded copy in `index.html`) as **non-commercial,
share-alike, attribution-required**. The tool's own code (HTML/CSS/JS you'd write yourself to
reproduce this) is otherwise free to reuse — see `LICENSE`.

## Coverage

64 Brand Sets / Gear Sets are covered (37 Brand Sets, 27 Gear Sets) — every brand/gear set
identified in the game's own data files, including several never documented by any community
source. Two attribute/tooltip details that couldn't be resolved from the raw file export alone
(Unit Alloys' 1-piece stat, Refactor's 4-piece talent tooltip) were confirmed directly in-game
and folded in — no known gaps remain.

## Updating the dataset (e.g. after a rebalance patch)

1. In Hunter, open `hunter/sdf/pc/data/sdf.sdftoc` from the game install, enable **raw files** in
   the file-type settings, and export. This produces a folder tree rooted at a `hunter/` directory
   containing `game system data/juice/item/*.mgearset` and `game system data/juice/talent/*.mtalent`.
2. Run:
   ```
   python tools/update_from_hunter_export.py --raw-dir "<path to the exported 'hunter' folder>"
   ```
   Run from anywhere; it locates the repo from its own location. This updates
   `data/combined_sets.json` / `data/combined_sets_min.json` / `index.html`, and prints (and saves
   to `tools/last_update_report.md`) a report of what changed: new/removed brands or gear sets,
   every changed bonus value, any talent needing a manual text review, and any attribute type it
   couldn't name.
3. Read the report. If it lists **unresolved attribute UIDs**, look up what stat that attribute
   represents (patch notes / wiki / in-game) and add it to `tools/attribute_uid_dictionary.json`
   — permanently resolved from then on. If it lists **talents needing review**, the tool already
   wrote a best-effort draft description into the JSON (numbers substituted in, wording not
   polished) — clean up the wording by hand. **Structural warnings** mean something in the file
   format itself didn't match what the script expects (e.g. a referenced file wasn't in the
   export) — investigate before trusting that entry.
4. Review the diff (`git diff`), then commit and push as usual. The script never commits or
   pushes on its own.

Why this works well for pure rebalances: every bonus value is keyed to a stable attribute ID
that doesn't change even when its value does, and gear-set talent descriptions are only
regenerated when the numbers backing them actually change (tracked via a hidden `_values`
fingerprint per talent) — an unrelated patch touching other sets won't disturb hand-polished
text elsewhere. New attribute types (e.g. a rebalance introducing a bonus that didn't exist
before) are the one case that still needs a short manual lookup, once per new attribute.
