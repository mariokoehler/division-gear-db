# Division Gear DB — project context for Claude

This file exists so a fresh session opened in this folder has the context that was built up
manually (over a long back-and-forth) the first time this project was built. Read this before
doing anything else here.

## What this is

A single-page tool for *Tom Clancy's The Division 2* (`index.html`): pick one or more bonus types
and see every Brand Set / Gear Set / Named Item that grants them, including Gear Set 4-piece
talents, Backpack/Chest amplifier talents, and each Named Item's own guaranteed fixed attribute
and/or unique talent. Self-contained — no build step, no server, works from `file://`.

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
- `data/named_items.json` / `data/named_items_min.json` — Named Items (Deathgrips, Turmoil, etc.),
  embedded in `index.html` as a second array, `const NAMED_ITEMS = [...]`.
- `tools/extract_named_items.py` — regenerates the two files above from the same kind of raw
  export. Unlike `update_from_hunter_export.py` it does **not** touch `index.html` itself — the
  `NAMED_ITEMS` line has to be re-pasted in by hand after review. See "Named Items" section below
  for the schema this parses, and "Updating Named Items" in `README.md` for run instructions.
- `tools/named_items_report.md` — gitignored, regenerated each run, not meant to be committed.

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

## Named Items — datamining notes

"Named Items" are the individually-named armor pieces (Deathgrips, Turmoil, etc.) — see
`tools/extract_named_items.py`. Distinct pipeline from Brand/Gear Sets above, with its own
landmines:

- **Item files live at** `game system data/juice/item/player_gear_<slot>_*_named*.mitem`
  (`<slot>` ∈ back/chest/gloves/holster/kneepads/mask — the six armor slots this tool covers;
  weapons have named variants too but are out of scope, same as the rest of the tool). Filter to
  exactly `player_gear_*_named*` — the same directory also has `blueprint_player_gear_*_named*`
  (crafting recipes), `appearance_player_gear_*_named*` (cosmetic skins), and
  `layer_gear_*_named*` (cosmetic layers), none of which are the actual item definition. A
  handful of matches (`*_alpha`, `*_charlie` suffixes) are campaign-tier variants that subclass
  another named item file and add no `myUIName` of their own — they're not new items, skip them
  silently rather than treating a missing name as a parse failure.
- **The fixed/guaranteed bonus and any unique talent live in the item's `ItemGenerationConfig`**,
  not the `.mitem` file itself. Chain: item's `myItemGenerationConfig` → a `*_config_link` file
  (this one's usually empty, a dead end) → the real `ItemGenerationConfig` block, which lives
  somewhere in `game system data/juice/itemgeneration/configs/configs_gear_<slot>_code1_data*.mitemgenerationconfigs`
  (~20 near-duplicate files per slot; just index every `ItemGenerationConfig` declaration once).
  **The declared config name's relationship to the item's own instance id is not consistent** —
  seen in the wild: `<item_id>_config`, `<item_id_minus_"_named">_config_named`, even one literal
  authoring typo merging tokens into `_namedconfig`. Don't guess a naming transform; instead
  match by **token multiset** — split both on `_`, lowercase, sort — since every real config name
  is exactly the item id's tokens plus one extra `config` token, in any order/position. Case can
  also mismatch entirely (`Player_gear_chest_z_01_named` item vs. its config's declared case).
- **Inside that config**, under `myAttributeSlots → QualityAttributeSlots Orange → mySlots →
  ItemAttributeSlot`: a slot with `myPresetAttribute <uid>` **and a positive**
  `myPresetPercentage` is a guaranteed, always-maxed bonus (the `myIsNamedAttribute TRUE/FALSE`
  flag on these is inconsistent across items — don't rely on it, key off `myPresetPercentage`
  instead, and specifically its *sign*: a **negative** value, seen as `-1.0`, is a sentinel for
  "this slot's preset isn't actually active here" even though the field is present — e.g. a
  random `ItemAttributeSlot` can carry `myPresetAttribute 000...000 myPresetPercentage -1.0`,
  which must NOT be read as a real fixed bonus; the all-zero UID is also independently filtered
  as a null placeholder). The `Core` slot (`myIsCoreAttribute TRUE`) also carries a
  `myPresetAttribute` but no percentage — that's just the ordinary guaranteed core stat every
  item of that slot type has, not a named-only bonus; exclude it. **Gloves/Holster/Kneepads/Mask
  items get 1–2 of these fixed bonuses; Backpack/Chest items get none at all** — their named
  identity is purely a talent instead (confirmed by reading several Backpack configs:
  `myAttributeSlots` is simply absent). This is a real game-design fact, not a data gap — don't
  treat "no fixed attribute" on a Backpack/Chest card as an error.
- **A unique talent**, when present, is `myTalentSlots → QualityTalentSlots Orange → mySlots →
  ItemTalentSlot → myPresetTalent < uid=... > = <slug> <guid>` — same two-token shape as a Gear
  Set's 4pc talent reference (`Talent "label" < uid=... > = <file_id> <guid>`): the FIRST token
  is the `.mtalent` file's own instance-id/slug (what `talent_index` is keyed by and what you
  look the talent up by), the trailing hex GUID is a separate identifier that's captured by the
  regex but never actually used for anything. **An earlier version of `parse_preset_talent` had
  these swapped** — stored the GUID as `"ref_file"` and looked talents up by that — so the lookup
  could never hit even when the referenced `.mtalent` file was sitting right there in the export
  (caught by checking one specific "missing" talent, Festive Delivery's
  `talent_gear_back_firecrackers`, by hand and finding it fully present and parseable). Fixed by keying off the first
  token, same as the Gear Set script's established convention; recovered 1 of 43 named-item
  talent references this way (the review-report's error text now shows the real slug too, not a
  bare GUID, which also makes a genuinely-missing file easier to search for by hand later).
  **Landmine, found only after the user pointed out several talent-only Backpack/Chest items were
  showing no talent at all**: `QualityAttributeSlots`/`QualityTalentSlots`'s own instance label is
  **not reliably the quality name** — many blocks use a generic editor-default label instead
  (`QualityTalentSlots "New QualityTalentSlots (0)"`, `QualityAttributeSlots "New
  QualityAttributeSlots (0)"`) even though their *contents* are the real Orange-tier block (a
  `myQuality Orange` field inside confirms it). A regex anchored on the literal label `Orange`
  silently finds nothing for these — indistinguishable from "this item truly has no talent" — a
  much worse failure mode than the already-flagged `MISSING_TALENT` case, because nothing gets
  flagged for review at all. Match every `QualityAttributeSlots`/`QualityTalentSlots` block
  regardless of its own label, then filter by the `myQuality Orange` field inside (see
  `_orange_quality_blocks` in `extract_named_items.py`). Fixing this recovered a real fixed
  attribute (Ammo Dump) and, more importantly, revealed that **every** Backpack/Chest named item
  does carry a talent reference — the ones without a resolved name simply need their `.mtalent`
  file, not a "no talent" verdict.
- **Do not try to derive a talent's real display name from `myPresetTalent`'s `ref_name` slug**
  (`talent_gloves_damage_done_increased_to_status_affected_perfect`-style tokens) when its
  `.mtalent` file is missing. Checked directly against the 4 items whose real name *is* known
  (via the description fallback) — the slug describes the underlying mechanic, not the flavor
  name, and bears no resemblance whatsoever: that exact slug's real name is "Perfectly Wicked",
  not anything containing "damage"/"status"/"increased". A humanized guess would be actively
  misleading, worse than the honest "not yet catalogued" the page shows instead.
- **The exact numeric value behind a fixed attribute isn't resolvable from this export.** The
  `AttributeListContainer` a preset attribute's UID belongs to (e.g. "NamedAttributes") is only a
  *reference*; the actual value range lives in
  `game system data/juice/itemgeneration/attributelists/*.mitemgenerationattributelists`, and that
  whole directory was absent from every raw export used so far (only `configlinks/` and `configs/`
  came through). So a named item's fixed bonus can only be reported as *which stat*, not *how
  much* — that's an inherent export gap, not a parsing bug; don't spend time trying to derive it
  from `configs/` alone.
- **`myUIName`/`myDescription` field parsing needs its own escaping logic**, separate from the
  gear-set parser's `extract_localized_text` (which only handles the simple `text = \"...\"`
  case). Named items' `text = ` value can be delimited by **either** an unescaped quote of the
  *other* type (`text = '<color name=\"x\">Name</color>'`, when nested inside a `myUIName "..."`
  wrapper) **or** a backslash-escaped quote of the *same* type
  (`text = \"...\"`, when nested inside a wrapper using the same quote char) — which one depends
  on the specific field, not the file. A value that itself embeds a quoted `<color name="...">`
  attribute then gets escaped *again* on top of that, e.g. `\\"` (escaped-backslash followed by
  unescaped quote, read left-to-right) rather than a clean `\"` — character-by-character
  quote-depth tracking is genuinely ambiguous here. The approach that works (see
  `extract_marked_value` in `extract_named_items.py`): after finding the `text = `/
  `contextComment = ` marker, search pragmatically for the known trailing marker (`, type` /
  `, enabled`) in whichever quote representation matches the opening, then unescape *both* quote
  types in the captured span (not just the delimiter's own) — mirrors the fallback strategy
  `update_from_hunter_export.py`'s talent-tooltip parser already uses successfully. One item
  (`player_gear_mask_dz_named_01` — The Hollow Man) has a literal stray `\"` inside the name value
  itself in the source data (a dev typo, not a real part of the name) — strip any leftover quote
  character from the final cleaned name.
- **A handful of older (Y1-era) named items never got their real `myDescription` written** — its
  `text` field is literally the placeholder string `"INSERT TEXT HERE"`, and the actual
  drop-source/talent info lives only in that same field's `contextComment` (an internal dev note,
  same string but a different sub-key). Extract both; fall back to `contextComment` whenever
  `text` is empty or one of these obvious placeholders. A few of those `contextComment`s go
  further and literally spell out `Talent: <name>\n<description>` — when present, that's a usable
  fallback for a talent whose `.mtalent` file is otherwise missing from the export (see next
  point) — `fallback_talent_from_description` regexes for that pattern.
- **The same unfilled-placeholder problem can hit `myUIName` itself, not just `myDescription`** —
  one item's raw `text` value was literally `INSERT NAME HERE` (its real display name, "The
  Gift", simply hadn't synced into this particular data snapshot at export time; `contextComment`
  was empty too, and no separate localization/string-table export exists in the raw files to
  cross-reference — `console scripts/localization/mygear.txt` despite its name is just a QA
  console-spawn script, not a string table). This is a genuine content gap in the source, not
  something parseable from data alone — it needs a human who's seen the item in-game. Rather than
  leave it wrong forever or hand-edit the generated JSON (which the next `--raw-dir` re-run would
  silently clobber), confirmed corrections like this go in
  `tools/named_items_manual_overrides.json` (instance_id → `{"name": ..., "note": ...}`), which
  `extract_named_items.py` applies after parsing and logs as a `MANUAL_OVERRIDE` review note —
  persists across re-runs the same way `attribute_uid_dictionary.json` does for attribute names.
- **Same "not every export is complete" caveat as Gear Sets, worse here**: as of the export this
  was built from, 35 of 62 named items' unique-talent `.mtalent` file wasn't present (only
  referenced; 42 of 43 total talent references, once the `ref_file` lookup-key bug above was
  fixed — the exported `talent/` folder holds 91 `.mtalent` files, 90 of them the
  `talent_gearset_*` family used by Brand/Gear Sets and exactly 1 stray named-item talent that
  happened to make it in) — flagged per-item in `tools/named_items_report.md` and on the item's
  own card in the page ("not yet catalogued"). 8 items' talent name+description were recovered
  anyway, 7 via the `contextComment`/`myDescription` fallback described above and 1 from its
  `.mtalent` file actually being present. Don't fabricate plausible-sounding
  text to fill the rest in (see the "don't guess from the slug" note further down — it's tempting
  but proven unreliable); wait for a fuller export or in-game confirmation, same policy as the two
  Gear Set gaps below. (5
  fixed-attribute UIDs had the same problem at first, but all 5 turned out to be ordinary
  attribute-name gaps, not export gaps — the user identified each one from in-game knowledge and
  they're now permanently resolved in `attribute_uid_dictionary.json`, same mechanism as any other
  attribute. Notably 3 of the 5 — Reduced Threat, Damage to Targets Out of Cover, Melee Damage —
  don't appear on *any* Brand Set or Gear Set in this dataset, confirming the user's original
  suspicion that some named items carry bonuses unobtainable anywhere else.)
- **Brand isn't always in `myGearBrand`** — items that subclass their own non-named base item
  (`ArmorItem foo_named < ... > : foo`) often don't redeclare it. Fall back to the file's own
  top-of-file `include ".../gearbrand/gearbrand_<code>.mgearbrand"` line, which is present
  regardless of inheritance; join `<code>` (lowercased) against the Brand entries already in
  `data/combined_sets.json` by stripping their `gear_brand_set_` prefix — same brand namespace.

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

64 Brand Set / Gear Set entries (37 Brand Sets, 27 Gear Sets), fully datamined, cross-checked, all
previously-missing brands/sets resolved. Two minor export-coverage gaps exist (documented in
`README.md`'s Coverage section and inline in the page's "Data notes") but don't affect displayed
data quality — both are "file missing from a specific export" situations, not unresolved data.

62 Named Items were added this session (`index.html`'s `NAMED_ITEMS` array, fully integrated into
the same bonus-type chip filter as Brands/Gear Sets, plus a "Named Items only" kind toggle — see
the "Named Items" section above for the extraction pipeline). All 5 fixed-attribute UIDs and one
placeholder item name ("INSERT NAME HERE" → "The Gift") were resolved via user in-game knowledge
and are now permanently fixed in `tools/attribute_uid_dictionary.json` /
`tools/named_items_manual_overrides.json` respectively. A follow-up parsing-bug fix (the
`QualityAttributeSlots`/`QualityTalentSlots` label landmine, see above) then recovered one more
fixed attribute and revealed that every Backpack/Chest item does carry a talent reference. A
second bug fix (the `ref_file`/`ref_name` swapped lookup key, see above) recovered one more
resolved talent (Festive Delivery); 8 talent names are now resolved in total (up from 4), and
each Named Item card shows the talent name as its own row (`Talent — <name>`) whether resolved or
not, per the user's request, so it's visible/greppable even before the full description is
catalogued. One gap remains, flagged in-page rather than guessed at: 35 items' unique talent text
wasn't resolvable because their `.mtalent` file was missing from the raw export this was built
from (see `README.md`'s Coverage section). Revisiting that just needs a fuller Hunter export re-run through
`tools/extract_named_items.py` — no code changes anticipated.

A later session (from a different machine, raw export at `C:\Temp\raw_files\raw_files\hunter`)
added each Named Item's civilian-brand bonuses (1pc/2pc/3pc, e.g. Unit Alloys' Assault Rifle
Damage/Magazine Size) alongside its own "Fixed" bonus and talent — previously a named item like
the Unit Alloys holster Salvo only surfaced under a search for its own Fixed stat (Rate of Fire),
not under the brand bonuses it also gets simply by being Unit Alloys-branded (Assault Rifle
Damage, Magazine Size). `extract_named_items.py`'s `build_named_items()` now also takes a
`brand_tiers` dict (brand code → the Brand entry's `tiers` list, sourced from
`combined_sets.json`) and writes it to each item's `brandBonuses` field in `named_items.json`.
`index.html`'s `NAMED_ITEM_ENTRIES` folds `fixedAttributes` (pieces: null) and `brandBonuses`
(real pieces count) into one `tiers` array so the existing chip-filter logic needs no change; the
Named Item card renderer distinguishes them by `pieces === null` ("Fixed" label) vs. a real piece
count (rendered the same `Npc` style as Brand/Gear Set cards, brand name already shown in the
card's subtitle line).

A rebalance patch is expected in the next few weeks that will remove some bonuses (Shock
Resistance, Health, Incoming Repairs, Swap Speed), add a new one ("Protection from Elites"), and
reshuffle which stat appears on which brand/set. The update script is designed to handle this
without help *except* for naming the one new attribute type the first time it's seen — see
`tools/attribute_uid_dictionary.json` and the "Updating the dataset" section of `README.md`.
