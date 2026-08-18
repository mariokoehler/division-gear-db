# Division Gear DB — Gear Set Bonus Finder

A small, dependency-free web tool for *Tom Clancy's The Division 2*: pick one or more bonus
types (Hazard Protection, Armor on Kill, Skill Haste, …) and see every Brand Set, Gear Set, Named
Item, and Exotic Item that grants them, including full Gear Set 4-piece talents, Backpack/Chest
amplifier talents, each Named/Exotic Item's own guaranteed attribute(s) and/or unique talent, the
normal brand bonuses each Named Item also gets from its civilian brand, and the Core attribute
(Red/Offensive, Blue/Defensive, Yellow/Utility) of every Gear Set, Named Item, and Exotic Item.

**Live page:** https://mariokoehler.github.io/division-gear-db/

## What's here

- `index.html` — the entire tool: markup, styles, logic, and the full dataset, all in one
  self-contained file. No build step, no server — it also works fine opened directly from disk.
- `data/combined_sets.json` — the same dataset, pretty-printed, for reference/editing.
- `data/combined_sets_min.json` — minified version, the one actually embedded into `index.html`.
- `data/named_items.json` / `data/named_items_min.json` — Named Items (Deathgrips, Turmoil, etc.),
  same pretty/minified split, embedded into `index.html` as a separate `NAMED_ITEMS` array.
- `data/exotic_items.json` / `data/exotic_items_min.json` — Exotic Items (Catharsis, Memento,
  etc.), same pretty/minified split, embedded into `index.html` as a separate `EXOTIC_ITEMS` array.

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

62 Named Items are also covered, all with a resolved fixed attribute where they have one, and each
showing its unique talent's name and full description (Gloves/Holster/Kneepads/Mask items
sometimes have both a fixed attribute and a talent; Backpack/Chest items only ever have a talent —
that's a real game-design fact, not a data gap). Each Named Item also belongs to a civilian brand
and shows that brand's normal 1pc/2pc/3pc bonuses alongside its own "Fixed" bonus, so e.g. the
Salvo holster (Unit Alloys) shows up whether you filter by its own Fixed "Rate of Fire" or by any
of Unit Alloys' brand bonuses (Assault Rifle Damage, Magazine Size). All 43 items that have a
unique talent now show its real, fully datamined name and description — a fuller Hunter export
(2026-08-18) resolved the remaining 35 that had previously only been name-confirmed by the user's
own in-game knowledge via `tools/named_items_manual_overrides.json` (that file still exists and is
still consulted first-to-last-resort, it's just not needed for any of the 62 items right now; see
its own inline comments). One genuine gap remains: Ongoing Directive's backpack companion talent
still has no `.mtalent` file in any export seen so far (confirmed by direct search, not just a
lookup miss) — everything else was a bug in the extraction scripts, not missing source data; see
`tools/extract_named_items.py`'s docstring and `tools/named_items_report.md` (regenerated each
run, gitignored) for the current list. A named item's *exact* fixed-attribute number (vs. just
which stat) still isn't reported: the relevant `itemgeneration/attributelists/` files are present
in the fuller export, but the "value" there is a gear-score-dependent curve/formula, not a flat
number — reporting a single fixed percentage wouldn't actually be accurate without a target gear
score to evaluate it at, so this is a deliberate scope limit now, not an export gap.

28 Exotic Items are also covered (Catharsis, Memento, Deathgrips-tier gear but at Exotic quality,
etc.) — the small pool of gear pieces whose talent never appears on any other Brand Set, Gear Set,
or Named Item. Every exotic always carries exactly two guaranteed bonus *types* plus its unique
talent, all fully datamined with real names and descriptions. Unlike a Named Item's Fixed
attribute, an exotic's actual rolled value is always random by design, so only the stat type is
shown, never a number — that's not a data gap, it's how the game generates these items. One item
(Acosta's Kneepads) is missing both bonus types in this export (flagged, not guessed at). A few
items found in the game's own data are deliberately excluded: an unreleased kneepad piece whose
name is literally the placeholder text "TBD", a pair of gloves whose entire generation config is a
dead `NULLREFERENCE`, and Investor (a real, released mask) — confirmed by the user to be
intentionally fully-random by design (its own talent text says "This item can feature any Core
Attribute" / "features a third random Attribute"), so it simply doesn't fit this database's
"always X and Y" model. See `tools/extract_exotic_items.py`'s docstring and
`tools/exotic_items_report.md` (regenerated each run, gitignored) for the current list.

Every Named Item, Exotic Item, and Gear Set also shows its **Core attribute** (Red/Offensive,
Blue/Defensive, Yellow/Utility — a real property of every item, never optional in-game). All 28
Exotic Items and all 62 Named Items show one; Backpack/Chest named items don't carry it in their
own dedicated config (talent only) so it's inherited from the regular civilian-brand piece the
named item is based on instead, confirmed correct in-game by the user for Chainkiller (Red) and
Closer (Blue). 2 items (Force Multiplier, Door-Kicker's Knock) can't be resolved that way — their
underlying base piece itself rolls a random core in this data — so those two are confirmed instead
from the user's own in-game knowledge (Yellow and Red) via
`tools/named_items_manual_overrides.json`, same mechanism already used for talent names. A handful
of exotic Backpacks (Memento, confirmed directly by the user, plus Harrier Pride and Ninja Bike
Messenger Bag, which share the exact same data structure) genuinely support all three cores
simultaneously rather than just one — a real design quirk, not a data error.

All 27 Gear Sets show a Core too (a Gear Set's 6 pieces are ordinary items with their own Core the
same way a Named/Exotic Item is), confirmed correct in-game by the user for Striker's Battlegear
(Red) and Foundry Bulwark (Blue). 24 of 27 sets share one single Core across every piece; the
other 3 are real exceptions, not bugs — Refactor and System Corruption each genuinely split two
different Cores across their pieces, and Core Strength is a deliberately flexible set (its own
4-piece talent text says "All pieces except the Backpack feature random Cores"). A dedicated
Red/Blue/Yellow filter (next to the kind filter) hides everything with no fixed Core — Brand
entries, since a civilian brand spans many different items rather than one fixed piece — and
shows only entries with that Core otherwise.

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

### Updating Named Items

Separate script, same raw export, same landmines (see `CLAUDE.md`'s Named Items section for the
schema this parses — item file → its `ItemGenerationConfig` → preset attribute/talent):

```
python tools/extract_named_items.py --raw-dir "<path to the exported 'hunter' folder>"
```

This regenerates `data/named_items.json` / `data/named_items_min.json`, re-embeds the new
minified JSON into `index.html`'s own `const NAMED_ITEMS = [...]` line, and writes
`tools/named_items_report.md`. (This used to be a manual re-embed step; it turned out to be a real
landmine — a naive find/replace here can silently corrupt the page, see the comment above the
substitution code in both this script and `update_from_hunter_export.py` for what actually went
wrong and why the fix is a same-line-only match plus a replacement *function*, not a plain
string.) Review the diff before committing either way.

Why this works well for pure rebalances: every bonus value is keyed to a stable attribute ID
that doesn't change even when its value does, and gear-set talent descriptions are only
regenerated when the numbers backing them actually change (tracked via a hidden `_values`
fingerprint per talent) — an unrelated patch touching other sets won't disturb hand-polished
text elsewhere. New attribute types (e.g. a rebalance introducing a bonus that didn't exist
before) are the one case that still needs a short manual lookup, once per new attribute.

### Updating Exotic Items

Sibling script to `extract_named_items.py`, reusing almost all of its parsing machinery (see
`CLAUDE.md`'s Exotic Items section for what's actually different: no civilian brand, bonus TYPES
without values since the roll is always random, and the Core-attribute extraction shared with
Named Items):

```
python tools/extract_exotic_items.py --raw-dir "<path to the exported 'hunter' folder>"
```

Same self-embedding behavior as `extract_named_items.py` — regenerates
`data/exotic_items.json` / `data/exotic_items_min.json`, re-embeds into `index.html`'s own
`const EXOTIC_ITEMS = [...]` line, and writes `tools/exotic_items_report.md`. Review the diff
before committing.
