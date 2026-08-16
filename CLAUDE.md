# Division Gear DB — project context for Claude

This file exists so a fresh session opened in this folder has the context that was built up
manually (over a long back-and-forth) the first time this project was built. Read this before
doing anything else here.

## What this is

A single-page tool for *Tom Clancy's The Division 2* (`index.html`): pick one or more bonus types
and see every Brand Set / Gear Set that grants them, including Gear Set 4-piece talents and
Backpack/Chest amplifier talents. Self-contained — no build step, no server, works from `file://`.

**Live:** https://mariokoehler.github.io/division-gear-db/ (GitHub Pages, `main` branch, root).
**Repo:** https://github.com/mariokoehler/division-gear-db (public).


## Hard constraint from the user, still in force

**Never modify the game's own install files.** The game is at
`E:\Ubisoft\Ubisoft Game Launcher\games\Tom Clancy's The Division 2`. Only ever read from there,
or from files the user has explicitly exported/copied elsewhere (e.g. `E:\Temp\Hunter\raw_files\`).

## Repo layout

- `index.html` — the whole tool (HTML/CSS/JS + the dataset embedded as `const DATA = [...]`).
- `data/combined_sets.json` — same dataset, pretty-printed, source of truth.
- `data/combined_sets_min.json` — minified copy, what actually gets embedded in `index.html`.
- `tools/update_from_hunter_export.py` — regenerates all three of the above from a fresh Hunter
  raw-file export. See "Updating the dataset" in `README.md` for the run instructions — don't
  duplicate that here, just know it exists and is the right tool for a rebalance patch.
- `tools/attribute_uid_dictionary.json` — persisted, accumulating map of attribute UID → stat
  name (e.g. `"Health"`). This is the thing that makes future updates mostly automatic; see below.
- `tools/last_update_report.md` — gitignored, regenerated each run, not meant to be committed.

## Where the data actually comes from

Not a public API — there isn't one. The dataset is datamined directly from the game's own files:

1. The game ships gameplay data (item/gear/talent definitions) as plain-text config inside the
   Snowdrop engine's `.sdftoc`/`.sdfdata` archives (`hunter/sdf/pc/data/sdf.sdftoc` under the game
   install, ~99GB). These aren't readable directly.
2. [Hunter](https://tools.dtzxporter.com/) (community tool, GUI-only, Windows) opens that archive.
   **Critical setting:** its file-type filter has "raw files" *disabled by default* — the gameplay
   data files (`.mgearbrand`, `.mgearset`, `.mtalent`) only show up once that's turned on. Without
   it you only see animation/image/sound/model, which looks like the data isn't there at all (this
   cost real time the first time around).
3. Export those raw files, then `tools/update_from_hunter_export.py` parses them.

## The Snowdrop text-config format — what took a long time to learn

Files look like a C-ish struct literal, e.g. (`gear_brand_set_511.mgearset`):
```
GearSet gear_brand_set_511 < uid=... > : gear_brand_set_template
{
    myUIName "... text = \"5.11 Tactical\" ..."
    myUnlocks { GearSetUnlock "1 item equipped" { myRequiredNumberOfItems 1
        myEffects { BonusAttributeRef "..." { myAttributeUID 4F5DDEA2... myValue 0.3 } }
        myEffectsOverrides { GearSetEffectOverride PvPOverride { myEffects { ... } } }
    } ... }
}
```

Key facts, each learned the hard way:

- **Relevant files live under** `game system data/juice/item/*.mgearset` (both civilian Brand Sets
  — `gear_brand_set_*` — and named Gear Sets — `gear_set_*`) and `game system data/juice/talent/*.mtalent`.
  The `fruit/` vs `juice/` split is schema-definitions vs. actual-instance-data; only `juice/` matters
  for extraction. `rejuice/` also exists, not yet investigated.
- **Every bonus value sits behind a `BonusAttributeRef`** with a `myAttributeUID` (a stable GUID
  identifying *which stat*, e.g. "Health") and a `myValue`. The UID does not change when a
  rebalance changes the value — this is the whole reason the update script can be mostly
  automatic. The `.fruit`/`.mgearbrand`/`.mgearset` files never spell out the UID→name mapping in
  plain text; it has to be inferred (this session did it by cross-matching known wiki bonus values
  against raw `myValue`s until UIDs resolved with high confidence — see
  `tools/attribute_uid_dictionary.json`, now persisted so this never has to happen again for a
  known attribute).
- **`myEffectsOverrides` / `PvPOverride` blocks are decoys** — always use the *first* `myEffects`
  block (base/PvE values), not the override.
- **A gear set's 4-piece talent is referenced directly**: `Talent "label" < uid=... > = <file_id> <guid>`
  inside the 4pc-tier `myEffects`. The quoted `"label"` before `<uid=...>` is just an internal
  editor comment/instance name — **it is not reliably the real display name**. Always follow
  `<file_id>.mtalent` and read its own `myUIName`/`myToolTipText` for the truth (e.g. one file's
  label was `"Ortiz Nanites"` but its actual in-game name is "Ortiz Rapid Application Nanite
  Prototype"). Piece-count for the final tier is *usually* 4 but not always — some historical
  gear sets have talent files literally named `_5piece`/`_6piece` (naming-only quirk, the
  `myRequiredNumberOfItems` in the `.mgearset` is still what's authoritative).
- **Backpack/chest amplifier talents are separate files with no reliable filename convention**
  (compare `talent_gearset_camaraderie_back.mtalent` — sensible — to Refactor's
  `talent_gearset_backpack_over_engineered.mtalent` — totally unrelated name). Find them
  mechanically instead: scan all `.mtalent` files for a `myRequirements { GearTalentRequirementTalent
  { ... myTalent <4pc_instance_id> ... } }` back-reference, then classify as backpack vs. chest by
  checking for "back"/"chest" as a substring of *that file's own* instance id (held in every case
  seen). Two more wrinkles this required handling:
  - The back-reference's case doesn't always match the 4pc file's own declared case
    (`talent_gearset_season08_4pc` referencing vs. `talent_gearset_Season08_4pc` declaring) —
    compare case-insensitively.
  - Some companions have no `myTalent` id at all, only a human-readable `myText` naming the
    talent — fall back to matching that against the 4pc talent's own display name.
- **Tooltip text contains `{0}`, `{1}}`-style placeholders** filled from the talent's own
  `myBonusList` (ordered). Formatting is ambiguous from the raw data alone (percent vs. seconds vs.
  flat count can't be inferred mechanically) — this is the one part of the pipeline that still
  benefits from a human/AI read. The update script tracks a fingerprint of the raw values behind
  each talent description; if they haven't changed since last run, the hand-written text is kept
  untouched, so this only comes up for genuinely new/changed talents, not every run.
- **The raw text format itself has landmines**: brace-matching must be quote-aware. At least three
  of the game's own files (`gear_set_d/j/l.mgearset` — Negotiator's Dilemma, Striker's Battlegear,
  Hunter's Fury) have a literal `}` embedded inside a quoted string value
  (`...\"MenuLine\"}"`), which silently truncates a naive brace-counter and drops everything
  after it (this actually shipped to production once before being caught — see git history around
  "Add repeatable update script"). `tools/update_from_hunter_export.py`'s `extract_braced()`
  handles this; reuse it rather than re-deriving brace parsing from scratch.
- **Not every raw-file export is complete.** Two files this session were referenced by other files
  but simply absent from the exported tree (Refactor's own 4pc tooltip; Ongoing Directive's
  backpack talent). The update script preserves the last known-good value in that case (with a
  flagged warning) rather than deleting good data — don't "fix" that behavior into silently
  dropping fields.

## Data provenance / licensing

The dataset was originally bootstrapped from two community sources before being replaced by direct
datamining: [mx-division-builds](https://github.com/mxswat/mx-division-builds) (CC BY-NC-SA 4.0)
and [The Division Wiki](https://thedivision.fandom.com/). Because of that lineage, treat
`data/*.json` (and the copy embedded in `index.html`) as non-commercial/share-alike/attribution
content, distinct from the tool's own MIT-licensed code — see `LICENSE` and `README.md`.

## Environment notes (Windows-specific gotchas from this session)

- Bash tool here is Git Bash; `python3`/`node` aren't on `PATH`. Windows Python is at
  `C:\Users\mario\AppData\Local\Programs\Python\Python311\python.exe` — call it by full path.
  When passing paths *into* a Python script string, use Windows style (`C:\...` / raw strings);
  the Bash tool's own commands use POSIX style (`/c/...`) — don't mix them up.
- `gh` (GitHub CLI) isn't on `PATH` either; it's at `C:\Program Files\GitHub CLI\gh.exe`.
- Windows console is cp1252 — printing non-ASCII (e.g. "Česká Výroba") from Python crashes with
  `UnicodeEncodeError`. Write results to UTF-8 files instead of `print()`-ing them when they might
  contain non-ASCII.

## Current known state (as of the last session)

64 entries (37 Brand Sets, 27 Gear Sets), fully datamined, cross-checked, all previously-missing
brands/sets resolved. Two minor export-coverage gaps exist (documented in `README.md`'s Coverage
section and inline in the page's "Data notes") but don't affect displayed data quality — both are
"file missing from a specific export" situations, not unresolved data.

A rebalance patch is expected in the next few weeks that will remove some bonuses (Shock
Resistance, Health, Incoming Repairs, Swap Speed), add a new one ("Protection from Elites"), and
reshuffle which stat appears on which brand/set. The update script is designed to handle this
without help *except* for naming the one new attribute type the first time it's seen — see
`tools/attribute_uid_dictionary.json` and the "Updating the dataset" section of `README.md`.
