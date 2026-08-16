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

This tool merges two community-maintained sources — there is no official API for this data:

- [mx-division-builds](https://github.com/mxswat/mx-division-builds) (CC BY-NC-SA 4.0) — used
  for initial weapon/gear structure and cross-referencing.
- [The Division Wiki](https://thedivision.fandom.com/) — Brand Sets and Gear Sets pages, fetched
  via the MediaWiki API — the primary source for the bonus values and talent text in this dataset,
  since it was more complete and caught brands the CSV source was missing.

Because the wiki data is themselves CC BY-NC-SA–style community content and one upstream source
is explicitly licensed CC BY-NC-SA 4.0, treat the **dataset** (`data/*.json` and the embedded copy
in `index.html`) as **non-commercial, share-alike, attribution-required**. The tool's own code
(HTML/CSS/JS you'd write yourself to reproduce this) is otherwise free to reuse — see `LICENSE`.

## Known data gaps

53 Brand Sets / Gear Sets are covered. Eight brand icons exist in the game's asset files with no
bonus text documented in any source found so far: Hanau, Concentrated Company, Measured Assembly,
Refactor, Tipping Scales, Unit Alloys, Urban Lookout, Virtuoso. These are flagged in a collapsible
note on the page itself rather than silently omitted. Closing this gap fully would require
extracting the game's own data files (Snowdrop `.sdftoc`/`.sdfdata` archives) with a tool like
[Hunter](https://tools.dtzxporter.com/), which is a manual/GUI-driven process.

## Updating the dataset

Edit `data/combined_sets.json`, regenerate the minified version, then re-embed it into
`index.html` in place of the `const DATA = [...]` line.
