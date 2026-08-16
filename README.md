# Division Gear DB — Gear Set Bonus Finder

A small, dependency-free web tool for *Tom Clancy's The Division 2*: pick one or more bonus
types (Hazard Protection, Armor on Kill, Skill Haste, …) and see every Brand Set and Gear Set
that grants them, including full Gear Set 4-piece talents and Backpack/Chest amplifier talents.

**Live page:** enable GitHub Pages for this repo (Settings → Pages → Source: `main` / `/ (root)`)
and it will be served at `https://<your-username>.github.io/division-gear-db/`.

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

## Updating the dataset

Edit `data/combined_sets.json`, regenerate the minified version, then re-embed it into
`index.html` in place of the `const DATA = [...]` line.
