# Division Gear DB — project context for Claude

This file exists so a fresh session opened in this folder has the context that was built up
manually (over a long back-and-forth) the first time this project was built. Read this before
doing anything else here.

## What this is

A single-page tool for *Tom Clancy's The Division 2* (`index.html`): pick one or more bonus types
and see every Brand Set / Gear Set / Named Item / Exotic Item that grants them, including Gear Set
4-piece talents, Backpack/Chest amplifier talents, each Named/Exotic Item's own guaranteed
attribute(s) and/or unique talent, and each Named/Exotic Item's Core attribute (Red/Offensive,
Blue/Defensive, Yellow/Utility). A second "Talent Browser" tab within the same page (a view
switcher, not a second HTML page) lists the full weapon/gear Talent catalog, filterable by gear
slot / weapon type. Self-contained — no build step, no server, works from `file://`.

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
  export, and re-embeds the result into `index.html`'s own `NAMED_ITEMS` line itself (this used to
  be a manual re-embed step; it turned out to be a real landmine, see the 2026-08-18 session notes
  below for what actually went wrong). See "Named Items" section below for the schema this parses,
  and "Updating Named Items" in `README.md` for run instructions.
- `tools/named_items_report.md` — gitignored, regenerated each run, not meant to be committed.
- `data/exotic_items.json` / `data/exotic_items_min.json` — Exotic Items (Catharsis, Memento,
  etc.), embedded in `index.html` as a third array, `const EXOTIC_ITEMS = [...]`.
- `tools/extract_exotic_items.py` — sibling to `extract_named_items.py`, reusing almost all of its
  parsing machinery; also self-embeds into `index.html`'s own `EXOTIC_ITEMS` line. See "Exotic
  Items" section below for what's different from Named Items, and "Updating Exotic Items" in
  `README.md` for run instructions.
- `tools/exotic_items_report.md` — gitignored, regenerated each run, not meant to be committed.
- `tools/exotic_items_manual_additions.json` — persisted, hand-confirmed data for the rare Exotic
  Item whose own `.mitem` file is missing from every export used so far but whose
  `ItemGenerationConfig` is fully present (see "Liveness filtering" under "Potential Bonuses"
  below for how the first entry, Acosta's Go Bag, was found and confirmed). Applied by
  `build_manual_config_items()` in `extract_exotic_items.py`, which reconstructs a full entry
  straight from the config (bonuses, cores, every preset talent) and only takes the item's name
  and DZ-exclusivity flag from this file, since those two are the only fields the config itself
  can never supply.
- `data/all_talents.json` / `data/all_talents_min.json` — the full weapon/gear Talent catalog
  behind the page's "Talent Browser" tab, embedded as `const ALL_TALENTS = [...]`.
- `tools/extract_all_talents.py` — walks every `.mtalent` file in a raw export (not just the ones
  referenced by a specific Brand/Gear Set/Named/Exotic Item) and classifies each one; self-embeds
  into `index.html` the same way the two scripts above do. See "All Talents" below.
- `tools/all_talents_report.md` — gitignored, regenerated each run, not meant to be committed.

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
3. Export those raw files, then `tools/update_from_hunter_export.py` parses them. A full raw-file
   export is ~2 million files / ~50GB, but every script in this repo only ever reads 3 folders
   under `hunter/game system data/juice/`: `item/`, `talent/`, and `itemgeneration/configs/` (NOT
   the rest of `itemgeneration/` — `configlinks/`/`attributelists/`/etc. are never read). See
   "Updating the dataset" in `README.md` for the full breakdown (why each folder is needed, file
   counts) — export just these three for a future run instead of everything.

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
- **A talent tooltip can also inline a small core-attribute icon instead of spelling out the
  color** — `<img src="hunter/baked/ui/loose_images/ui_player_offense.dds">` and its
  `defense`/`utility` siblings, no other icon vocabulary exists anywhere in `talent/*.mtalent`
  (confirmed by grepping every file for every distinct `<img>` tag in use). `strip_inline_markup`
  (shared by all three extraction scripts) only ever stripped `<color>` tags until a user caught a
  literal broken `<img>` reference rendering on a live card — 5 occurrences across 4 talents were
  silently affected. Fixed by mapping each icon to its color word (Red/Blue/Yellow, the same
  `CORE_COLOR_BY_STAT` convention used everywhere else) rather than just deleting the tag, since
  at least one occurrence uses the icon as a noun ("...for each `<img.../>` you have"), not a
  decorative prefix — deleting it outright would've left a grammatically broken sentence.
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

## Core attribute — shared by Named Items, Exotic Items, and Gear Sets

Every armor piece has a "Core" attribute determining its archetype: Red/Offensive, Blue/Defensive,
or Yellow/Utility. Confirmed to map to exactly 3 stats across the whole dataset:
`CORE_COLOR_BY_STAT` in `extract_named_items.py` — Weapon Damage → Red, Total Armor → Blue, Skill
Tier → Yellow. The "Total Armor" UID used here (`5D4179F15AC362CC0001190A8D09DA48`) is a
*different* UID from the "Total Armor" used for the `+X% Total Armor` bonus attribute elsewhere in
the dataset (`5D4179F15996CE00000035FD0AA3A56A`) — two separate internal encodings of the same
real-world stat, both correctly named the same thing in `attribute_uid_dictionary.json`. Confirmed
by internal field names, not guessed: the UID's own `AttributeData` block is literally named
`Armor` with curves `CoreArmorMin`/`CoreArmorMax`, and the user independently confirmed "Total
Armor" as the real name from in-game knowledge (2026-08-18).

Extraction (`parse_core_attributes` in `extract_named_items.py`, shared by both pipelines): scan
the item's own quality-tier `QualityAttributeSlots` block (Orange for named items, Exotic for
exotics — **do not** scan all 4 quality tiers the way an early exploratory pass did, see below for
why) for every `ItemAttributeSlot` with `myIsCoreAttribute TRUE`, resolve each one's
`myPresetAttribute` UID, dedupe by UID.

Two landmines, both discovered the hard way:
- **A named item's Core UID can genuinely differ across quality tiers** (Green/Blue/Purple showing
  one stat, Orange showing a different one — seen on Caesar's Guard and Henri). An early
  exploratory pass that aggregated across all 4 tiers read this as "these items have 2 cores,"
  which was wrong — named items are always Orange quality in practice, so only the Orange tier's
  value is meaningful. Restricting to Orange-only (which the real `parse_core_attributes` already
  does via `_quality_blocks`'s `quality` parameter) resolves this cleanly.
- **Backpack/Chest named items' own dedicated config has no Core at all** (same "no fixed bonus
  either" fact already documented above — talent only, no `myAttributeSlots` block). This does
  NOT mean these 19 items have no Core in-game (they do — every item does, per the user, who
  called this out explicitly after the first pass shipped these as "this slot doesn't roll one",
  which was simply wrong). The real Core lives on the regular, non-named civilian-brand piece
  these items' model/identity is drawn from, reliably found by stripping `_named` out of the named
  item's own instance_id (e.g. `player_gear_chest_t_01_named` → `player_gear_chest_t_01`; `_named`
  isn't always a trailing suffix, e.g. `player_gear_back_g_named_02` → `player_gear_back_g_02`, so
  a plain substring removal anywhere in the id is the right approach, not a suffix-anchored regex).
  `parse_named_item_file` computes this `base_id`; `build_named_items` falls back to
  `parse_core_attributes` on the base item's own config when the named item's own is empty. This
  was tried two ways before landing here: first via the ArmorItem's own `: base_id` subclass
  declaration in the `.mitem` file, which works (confirmed correct for Chainkiller, Red) but
  sometimes subclasses the generic `player_gear_<slot>_template` even when a real, correctly-named
  base item exists (e.g. Closer subclasses `: player_gear_chest_template`, yet
  `player_gear_chest_w_01` is real and has an explicit Core) — the `_named`-stripping approach
  resolves strictly more cases and was verified to never disagree with the subclass approach
  wherever both resolve, so it fully replaced it. Even so, 2 of 62 named items (Force Multiplier,
  Door-Kicker's Knock) can't be resolved this way: their base item exists and has a Core *slot*,
  but that slot has no `myPresetAttribute` at all — i.e. even the regular, non-named drop of that
  piece rolls a random core, so there's nothing fixed in the data to inherit. Confirmed instead
  from the user's own in-game knowledge (Yellow and Red respectively, 2026-08-18) via
  `tools/named_items_manual_overrides.json`'s `core`/`coreNote` keys, applied in
  `build_named_items` as a last-resort fallback after both datamined attempts come up empty --
  same override mechanism already used for talent names, resolved to a `{stat, color}` entry via
  a reverse lookup through `CORE_COLOR_BY_STAT`. All 62 named items now show a confirmed Core.
- **A user's own screenshot-sourced recollection can be wrong, and datamined defaults can still be
  right** — worth remembering given how much of this project's Core work otherwise leans on
  in-game confirmation to catch bad extraction logic. The user first stated Closer was Red from a
  screenshot; the naming-strip approach said Blue and was initially set aside as contradicted.
  The user later corrected themselves: Division 2 lets players recalibrate an item's Core after
  acquisition, and the screenshot showed someone else's recalibrated copy, not the item's real
  default. Blue was right all along. Lesson for future sessions: an item's Core as shown by a
  screenshot or a single anecdote isn't necessarily its *default* (datamined) Core — worth asking
  specifically "on an unmodified/un-recalibrated copy" when confirming this stat, not just "what
  does it show in your inventory."
- **`myPresetPercentage`'s sign does NOT reliably distinguish an active core from a decoy** on
  multi-slot exotics, unlike its role on regular (non-core) attribute slots elsewhere in this
  codebase. A few exotic Backpacks (Memento, and — sharing the exact same data shape — Harrier
  Pride and Ninja Bike Messenger Bag) declare 3 `myIsCoreAttribute TRUE` slots simultaneously, one
  per possible core color, with percentages that don't consistently follow the usual "-1.0 =
  inactive" convention (Memento's real, always-active Total Armor slot is itself marked -1.0, the
  same sentinel value that means "inactive" everywhere else). The user confirmed directly
  (2026-08-18) that Memento genuinely has all three cores, always — this is a real in-game design
  quirk (a small number of exotics can equip any core), not random junk data. `parse_core_attributes`
  therefore treats **every** `myIsCoreAttribute TRUE` slot as active regardless of its percentage,
  deliberately different from how regular (non-core) attribute slots are filtered. Harrier Pride
  and Ninja Bike Messenger Bag are assumed to behave the same way (same structure, not independently
  confirmed) — flag if a future in-game check finds otherwise.

**Gear Sets** (Striker's Battlegear, Foundry Bulwark, etc.) also have a Core per piece, prompted by
the user pointing out the tool was missing this entirely for Gear Sets even after Named/Exotic
Items already had it (`tools/update_from_hunter_export.py`'s `parse_gearset_items` +
`parse_gearset_cores`, called from `build_dataset` for every Gear Set entry — Brand entries
deliberately do NOT get a `cores` field at all, since a civilian brand spans many different items
with no single fixed Core, unlike a curated 6-piece Gear Set or a specific Named/Exotic item):
- **A Gear Set's 6 pieces are `myQuality GearSet`, not `Orange`** — easy to miss since every other
  quality-scoped lookup in this codebase (Named Items, Exotics) defaults to `"Orange"`. Passing
  `quality="GearSet"` to `parse_core_attributes` was the whole fix; without it every piece silently
  resolved to zero cores, indistinguishable from "genuinely no Core data" until checked by hand.
- **A Gear Set's own `.mgearset` file lists its 6 concrete pieces directly**: `myItems { Item Mask
  < uid=... > = player_gear_set_j_mask_01 <guid>; Item Chest = ...; ... }` — one clean, reliable
  slot→instance_id map (`parse_gearset_items`), no fragile naming-convention guessing needed the
  way Named Items' Backpack/Chest base-item fallback required.
- **Circular import**: `parse_gearset_cores` needs `find_generation_config_block` and
  `parse_core_attributes`, both defined in `extract_named_items.py` — which already imports FROM
  `update_from_hunter_export.py` at its own top level. A top-level `from extract_named_items import
  ...` in `update_from_hunter_export.py` would create a real cycle; the import is deferred inside
  `parse_gearset_cores` itself (function-local, resolved at call time once both modules are fully
  loaded) to avoid it.
- **24 of 27 Gear Sets share one single Core across all 6 pieces** (confirmed correct in-game by
  the user for Striker's Battlegear = Red, Foundry Bulwark = Blue), but 3 are real exceptions, not
  bugs, verified individually before trusting them:
  - **Refactor** and **System Corruption** each genuinely split two different Cores 4pc/2pc across
    their pieces (e.g. Refactor: Mask/Chest/Holster = Yellow, Back/Gloves/Kneepads = Blue) — every
    piece's own Core slot has an explicit, non-random `myPresetAttribute`, just not the same one
    across all 6, so this is real per-piece data, not a lookup bug.
  - **Core Strength** is a deliberately flexible set — confirmed two ways: its own 4-piece talent
    tooltip literally says "All pieces except the Backpack feature random Cores" (found by reading
    the extracted talent text, not guessed), and the data matches exactly: 5 of its 6 pieces have
    `myPresetAttribute 00000...0` (the same null-UID sentinel used everywhere else in this codebase
    for "not actually preset"), while its Backpack alone declares all three Cores simultaneously
    active — the identical "flexible core" pattern already documented above for a few exotic
    Backpacks (Memento etc.).
  - Given these exceptions, `parse_gearset_cores` returns the **union of every Core resolved across
    all 6 pieces**, deduped by color, rather than asserting a single Core per set. This reduces to
    the single common case for 24/27 sets and reads correctly for the 3 exceptions too ("these are
    the Core(s) found across this set's pieces") without fabricating a single answer that isn't
    real for them.

## Exotic Items — datamining notes

Distinct item category from Named Items: gear whose *unique talent* never appears on any Brand
Set, Gear Set, or Named Item, and which always carries exactly two guaranteed bonus **types** (not
values — the roll is always random by design, unlike a Named Item's guaranteed-max Fixed
attribute). `tools/extract_exotic_items.py` reuses almost all of `extract_named_items.py`'s
parsing machinery directly (imported, not copied) — the schema turned out to be nearly identical:

- **Item files**: `game system data/juice/item/player_gear_*exotic*.mitem` (note: no `_named`
  requirement in the glob — exotics use their own naming, e.g. `player_gear_mask_exotic_03`).
  Same `blueprint_*`/`_aprilfools` exclusions as Named Items. `parse_named_item_file` (from
  `extract_named_items.py`) parses these directly with **no changes needed** — slot detection from
  filename tokens, name/description extraction, and DZ-tag detection (some exotics genuinely are
  DZ Elite Boss drops, e.g. Catharsis) all just work. The one field that must be **ignored**:
  `parse_named_item_file`'s brand-fallback logic (matching the file's own top-of-file gearbrand
  include) picks up unrelated shared-asset includes for exotics — e.g. Catharsis's file includes
  `gearbrand_set_c.mgearbrand`, which is NOT actually Catharsis's brand. Exotics simply don't have
  a civilian brand; don't wire the returned `brand_code` into anything for this category.
- **Config lookup**: same `find_generation_config_block` token-multiset matching as Named Items,
  unchanged — exotics' real configs live in the same `itemgeneration/configs/` directory, whose
  index (`_index_generation_configs`) globs the whole directory flatly, so the dedicated
  `configs_exotics_code1_data*.mitemgenerationconfigs` family was always included in the search
  automatically, never a separate lookup step. It just never turned out to matter for any of the
  28 items this pipeline resolves via their own `.mitem` file, since those 28 items' configs are
  all duplicated in the regular per-slot files too — **but it does matter** for at least 2 real
  exotic items (a Backpack, a pair of Kneepads) whose own `.mitem` file is missing from this
  export entirely; their configs exist *only* in this family. See "Potential Bonuses" below
  (the "later, same-session correction" bullet under "Liveness filtering") for how that was found
  and what it means for `extract_all_talents.py`'s own exotic-talent classification.
- **Talent**: exactly one `ItemTalentSlot` under `QualityTalentSlots Exotic` (not `Orange`) —
  `parse_preset_talent`/`_quality_blocks` both take a `quality` parameter for this (defaults to
  `"Orange"` for Named Items' existing callers, pass `"Exotic"` explicitly for this pipeline).
- **Bonus slots**: `ItemAttributeSlot`s (excluding the Core one) with a `myPresetAttribute` —
  reuses `parse_preset_attributes(config_body, quality="Exotic")` directly, but **deliberately
  does not check `has_preset_percentage`** the way Named Items' Fixed-attribute extraction does:
  an exotic's guaranteed bonus slot never carries `myPresetPercentage` at all (there's nothing to
  gate on — the type is fixed, the value stays random). Only the null/placeholder-UID sentinel
  (`00000...`) is filtered, same as everywhere else.
- **Core**: `parse_core_attributes(config_body, uid_dict, quality="Exotic")` — see the "Core
  attribute" section above, this is exactly where the "not everything follows the percentage-sign
  convention" and "some items have several simultaneously" complications were found.
- **Excluded items** (`EXCLUDED_INSTANCE_IDS` / placeholder-name check / config-not-found in
  `extract_exotic_items.py`), none guessed at, all either structurally detected or user-confirmed:
  - `player_gear_gloves_exotic_02` ("Rathbone's Gloves") — `myItemGenerationConfig` is a literal
    `NULLREFERENCE` in its own `.mitem` file. Detected automatically: `find_generation_config_block`
    returns `None` for it, and — unlike Named Items, where a missing config has so far always meant
    "genuinely real item, this one file just isn't in the export" and the item is still included
    with empty fields — Exotics **skip the item entirely** on a missing config, since this
    specific case is a dead, unfinished item, not an export gap.
  - `player_gear_kneepads_exotic_04` — `myUIName`'s `text` value is literally `"TBD"`. Caught by
    a placeholder-name check, but only after fixing a real bug in the shared `extract_field_text`
    helper: its contextComment-fallback (designed for `myDescription`, where a handful of Y1-era
    named items' real drop-source info only exists in that dev comment) was also being applied to
    `myUIName`, silently replacing "TBD" with this item's *contextComment* — an internal editor
    label ("Y7S2.3 Climax Exotic Gear Piece Name"), not a real display name — before any
    placeholder check ever saw the raw "TBD" value. Fixed by adding an
    `allow_comment_fallback` parameter to `extract_field_text`, defaulting to `True` (unchanged
    behavior for `myDescription`) but passed `False` for `parse_named_item_file`'s `myUIName` call.
    Verified zero named-item names changed as a result (the one existing case that relies on
    seeing a raw placeholder, "INSERT NAME HERE" → "The Gift" via manual override, already worked
    before this fix too, because that specific item's contextComment happened to be empty).
  - `player_gear_mask_exotic_06` ("Investor") — a real, released Y8S1 item, confirmed by the user
    (2026-08-18) via its own talent text to be intentionally fully-random: "This item can feature
    any Core Attribute" / "features a third random Attribute instead of a mod slot" / cannot roll
    certain attributes. It simply doesn't fit this database's "always X and Y" model, and was
    excluded outright at first (no generic structural signal distinguishes "no data" from
    "intentionally no data" without the user's own confirmation of which one this is). **Included
    since a later session** once the user pointed out its talent, "Slotted", had nothing to attach
    to otherwise — see `CONFIRMED_RANDOM_BONUS_ITEMS` and the "Potential Bonuses" section's
    "Liveness filtering" below for the mechanism that lets it show `bonuses: []`/`cores: []`
    honestly (confirmed by its own config, not fabricated) with an explicit "fully random" note
    instead of looking like an unresolved gap.
- **Two more bugs surfaced by exotic-item flavor/description text specifically, both fixed in
  shared code** (`update_from_hunter_export.py`, so both this pipeline and the gear-set one
  benefit):
  - `extract_braced`'s quote-tracking desynced on text containing an apostrophe combined with a
    nested `\\"..."` escape (an escaped-backslash immediately followed by a genuinely unescaped
    quote, one level deeper than the common case) — read as closing the *outer* field's string
    early, then everything after silently miscounted braces until the file appeared unbalanced
    (hit on 9 of 31 candidate exotic files). Since no field in this format legitimately spans
    multiple lines, the fix resets quote-tracking state at every newline rather than trying to
    correctly model arbitrarily-nested escaping. (Separately: `extract_named_items.py` already had
    its own more targeted local override of `extract_braced` for a related pattern, predating this
    session — that one skips whole `myXxx "..."` lines wholesale rather than char-scanning them,
    and was never actually affected by this specific bug; only a throwaway exploration script that
    imported the wrong module's copy of the function hit it.)
  - `naive_substitute`'s percent-formatting heuristic and `parse_mtalent_file`'s tooltip parser had
    two more quote/escape gaps of the same family as the ones already documented in the 2026-08-18
    session notes below — see that section for the fixes (double-`%` and a second, distinct
    quote-style gap in the hand-rolled tooltip parser, since consolidated to reuse
    `extract_localized_text` instead of maintaining a third copy of the same logic).

## All Talents — the "Talent Browser" tab

A second view within the same page (`index.html`'s view-tabs — no second HTML page, just two
`<div>`s toggled by JS), added on the user's request for a full catalog of every weapon/gear
Talent, not just the ones already reachable by following a reference from a Brand/Gear
Set/Named/Exotic Item. `tools/extract_all_talents.py` walks *every* `.mtalent` file in the export
(769 files as of the export this was built from) and classifies each one, rather than being
handed a specific instance_id to look up — a fundamentally different traversal from the other
three pipelines, all of which start from a known reference and resolve outward.

- **Output**: `data/all_talents.json` / `data/all_talents_min.json`, embedded as
  `const ALL_TALENTS = [...]` (same landmines as the other two self-embedding scripts apply here
  too — same-line-only regex match, function replacement not string replacement, see the
  2026-08-18 session notes below for why both matter).
- **Schema per talent**: `{id, name, description, kind, slot, weaponType, tier}`. `kind` is one of
  `gear` / `weapon` / `exotic-gear` / `exotic-weapon` / `exotic-other` / `other`. `slot` and
  `weaponType` are mutually exclusive — a talent has one or neither, never both — but `slot` can
  itself be a `" / "`-joined pair (currently only `"Backpack / Chest"`, ~14 talents rollable on
  either, confirmed via the pool data below, not guessed). `tier` is `"Perfect"` when the instance
  id ends `_perfect`, else `"Standard"`.
- **A non-Exotic item only ever rolls a Talent on Chest or Backpack — never Mask/Gloves/Holster/
  Kneepads.** Confirmed two ways, not just asserted: the user's own in-game knowledge (this whole
  sub-section exists because two early rounds of this pipeline got it wrong and the user caught
  both), *and* structurally — every `configs_gear_mask_*`/`configs_gear_gloves_*`/
  `configs_gear_holster_*`/`configs_gear_kneepads_*` file's own base `ItemGenerationConfig`
  (`MaskBase`, etc.) has a completely empty `myTalentSlots {}` block, while `ChestBase`/
  `BackPackBase` both populate theirs. This matches this codebase's own pre-existing Named Items
  finding (those 4 slots get a Fixed attribute instead, never a talent) and now extends it to
  regular/civilian gear too. Talent files literally named `talent_mask_*`/`talent_gloves_*`/etc.
  with real names and descriptions do genuinely exist in the export (50+ of them) — they're
  leftover/legacy data (same situation as the confirmed-cut "Watch" slot below), not real
  obtainable content, and are excluded rather than shown on a slot that can't roll them.
- **The authoritative source for "which talents actually roll on Chest vs. Backpack" is the
  game's own random-roll talent-pool data, not the talent's own filename slot token — which is
  frequently wrong, or absent entirely.** Discovered after the user caught two more misclassified
  talents (Adrenaline Rush shown as "Universal/Other" when it's Backpack-only; Headhunter shown
  the same way when it's Chest-only) that a first, filename-only fix couldn't have caught, since
  neither file carries any slot token at all (`warlock_talent_nearby_enemies_grant_bonus_armor`,
  `warlock_talent_headshot_kills_increase_next_weapon_hit`). Traced where the *real* per-slot
  talent pool lives: a Chest/Backpack item's `ItemGenerationConfig` → `myTalentSlots` →
  `QualityTalentSlots` (Orange and Purple both point at the same one) → `ItemTalentSlot` →
  `myPossibleTalentLists` → a `TalentListContainer` *reference* (e.g. `= warlock_chest_talents
  <guid>`), whose actual body — a flat list of `Talent "label" = <instance_id> <guid>` entries —
  lives in a **separate directory**, `itemgeneration/talentlists/*.mitemgenerationtalentlists`
  (parallel to the already-known `itemgeneration/attributelists/` for attribute value curves).
  `build_gear_talent_pools` in `extract_all_talents.py` unions every `Talent = <id>` entry across
  every declaration of the 4 real container names actually referenced by live Chest/Backpack
  configs (`warlock_chest_talents`/`WarlockChestTalents`/`active_chest_talents`/
  `common_chest_talents` for Chest, the `*back*`/`*backpack*` equivalents for Backpack — grepped
  directly from every `configs_gear_chest_*`/`configs_gear_back_*` file's own `myTalentSlots`, not
  guessed). Same "many near-duplicate files, index every declaration" pattern already established
  for `configs/` — each container name is declared many times across different
  `talentlist_code1_dataN.mitemgenerationtalentlists` shards with a *different* uid each time;
  results are unioned across all of them rather than picking one. This pool override runs for
  every non-exotic talent regardless of its filename-derived classification, and **only ever adds
  or corrects a slot, never removes one an item actually confirms** (see the named-item
  cross-check below) — it recovered real Chest talents filed under a `mask`/`holster`/`kneepads`
  token (Tag Team = `talent_mask_hits_reduce_cooldown`, Trauma = `talent_mask_headshots_blind_target`,
  Braced = `talent_kneepads_increase_weapon_handling_after_entering_cover`, and others), reclassified
  several talents the filename-only pass had put in `weapon` (bare `weapon` token, e.g.
  `warlock_talent_weapon_damage_grants_skill_damage`, which is actually a Backpack talent despite
  the name), and rescued 25 of the original 50 excluded mask/gloves/holster/kneepads-filed talents
  by confirming their real Chest/Backpack slot — the other 25 are in neither pool and stay excluded
  as genuinely unresolvable/legacy. **Deliberately NOT used to *remove* an already-slotted talent
  just because it's absent from the pool**: a named item's own preset talent (e.g. Festive
  Delivery's `talent_gear_back_firecrackers`, already confirmed real and Backpack-slotted via its
  item's own config) doesn't need to appear in the generic random-roll pool at all, since it's
  assigned directly via `myPresetTalent`, a completely separate mechanism — absence from the pool
  only means "not obtainable via random roll," a narrower question than "is this a real
  currently-used talent." Only ever applied to non-exotic kinds; an Exotic's talent comes from its
  own item config, never this general pool.
  - A `talentlist_dev_testing_only_*.mitemgenerationtalentlists` family also exists, containing
    plausible-looking containers (`dev_testing_backpack_talents`, etc.) with real-sounding talents
    (Aegis, Second Primary Weapon) — but grepping every real Chest/Backpack config confirms *none*
    of them ever reference these dev-testing containers. Deliberately excluded from the pool
    query rather than trusted, even though some of their contents might be genuine — no structural
    way to tell from this export alone, and the whole point of the pool approach is not to
    reintroduce the same kind of guess it was built to replace.
- **Exclusions, each checked by hand against real file content before being excluded** (see
  `EXCLUDE_PREFIXES` in `extract_all_talents.py`), not guessed from the name alone:
  - `talent_gearset_*` — already fully covered by `combined_sets.json` (4pc/companion talents);
    showing them again here would just be a duplicate of the Attribute Finder tab's own cards.
  - `talent_specialization_*` / bare `specialization_*` (case-insensitive — some files declare
    their own instance id with a capital `S`, e.g. `Specialization_Ammo_GL`, even though the
    filename itself is always lowercase) — the specialization skill tree, a different system.
  - `warlock_skill_talent_*` — Skill Tier 7 unlocks (Adrenaline Rush's trap/pulse/shield variants
    etc.), tied to a skill, not to equipped gear/weapon.
  - `dz_*` — Dark Zone rank/reputation perks, account-level, not droppable gear.
  - `boo_*` — battle-pass/account reward perks (extra inventory slots, extra loadouts, crafting
    tiers) — a completely different reward system that happens to share the `.mtalent` format.
  - `test*` — literal test data (`test_talentarmorbonus`).
  - `talent_watch_*` — a "Watch" gear slot that was apparently planned and cut before launch
    (never shipped in-game); this data is a leftover, not a real slot to filter by.
  - `talent_sd_*` — a "Dungeon Arena" roguelike-mode temporary talent pool (confirmed by reading
    the files' own `contextComment`, e.g. `"Dungeon Arena Talent Name: Armor increased by {0}"`),
    not obtainable on regular gear.
  - `talent_augment_*` — Skill Augments (Amalgam, Anomaly, Atomize, etc.), a distinct equip system
    from weapon/gear talents.
  - Placeholder/unfilled names (`(PH)`, `TBD`, `INSERT NAME`, or a bare `[...]`-wrapped label) —
    only 6 files across the whole export, e.g. `"[AR Archetype Talent 4 (PH)]"` — real,
    structurally-valid talent files whose display name was simply never finalized in this data
    snapshot, same "don't fabricate" policy as everywhere else in this codebase.
  - No usable description at all after `naive_substitute` (5 files) — nothing to show.
- **Classification (`classify_talent`)**: strips one of several known prefix aliases first —
  `virginia_talent_exotic_`, `warlock_talent_exotic_`, `talent_exotic_`, `talent_gear_`,
  `warlock_talent_`, `talent_`, tried longest/most-specific first (`warlock_`/`virginia_` are
  internal dev codenames that prefix an otherwise-normal `talent_exotic_`/`talent_gear_`/plain id
  — e.g. `warlock_talent_exotic_backpack_mk1a` is a real exotic Backpack talent, not a skill
  talent, despite starting the same way as the excluded `warlock_skill_talent_*` bucket). What's
  left after stripping is matched against an ordered list of gear-slot and weapon-type prefixes
  (longest-match-first so `assault_rifle` doesn't get eaten by a bare `rifle` match) — this is only
  the *first pass* for non-exotic gear now; the pool override described above runs afterward and
  is authoritative whenever it finds a match. No match at all (and no pool match either) →
  `kind: "other"` — a real, in-scope talent that just isn't restricted to one slot/weapon, e.g. the
  `talent_basic_*`/`talent_slot_*` families (Accurate, Allegro, Distance — universal weapon-stat
  talents with no weapon-type restriction). One single hardcoded special case:
  `ninja_backpack_talent_exotic` (Ninja Bike Messenger Bag's own talent) has no recognizable prefix
  structure at all.
- **Exotic gear talents whose filename carries no slot token at all** (e.g. Tinkerer mask's talent
  is just `talent_exotic_abridged`, not `talent_exotic_mask_abridged`) are resolved the same way
  `parse_named_item_file`/`find_generation_config_block`/`parse_preset_talent` already resolve a
  named/exotic item's OWN talent in the other two pipelines — just inverted here
  (`build_exotic_gear_talent_slots`): walk every exotic armor `.mitem` file (same glob
  `extract_exotic_items.py` uses, including the 3 items that pipeline itself excludes — Rathbone's
  Gloves, the "TBD" kneepad, Investor — since their raw `.mitem`/config still exist and still
  correctly resolve a slot even though they don't ship as a card), resolve each one's own preset
  Exotic-tier talent, and invert into `{talent_id: slot}`. Recovered 4 of the original 5
  slot-less exotic entries (Abridged→Mask, Bob and Weave→Holster, Escape Plan→Kneepads,
  Ostracize→Kneepads); the 5th (Ardent, a weapon heat-meter mechanic) is a genuine exotic *weapon*
  talent, correctly left unresolved since this codebase has no weapon `.mitem` parsing at all.
- **A bare `weapon` filename token on an exotic talent does NOT mean "Any Weapon."** Unlike the
  real universal weapon-talent pool (`talent_weapon_*`, genuinely droppable on any weapon), an
  exotic weapon's talent is always tied to exactly one specific gun (`talent_exotic_weapon_
  big_alejandro` is Big Alejandro's own talent, not a generic pool entry) — matching it against the
  same `("weapon", "Any Weapon")` fallback used for the real pool would be a straightforward lie.
  `EXOTIC_WEAPON_PREFIXES` (a copy of `WEAPON_PREFIXES` with that one generic entry removed) is
  used instead for the exotic path; a bare/unrecognized weapon token there falls through to the
  same "try the item cross-reference, then give up honestly" path as slot-less exotic gear talents
  above (`kind: "exotic-other"`, both `slot` and `weaponType` null) rather than mislabeling 12 real
  exotic weapons' talents (Prima Donna, The Senate, Big Alejandro, Vindicator, Ouroboros, etc.) as
  usable on literally any weapon. The page's own card renderer shows an honest "tied to one
  specific item, not resolved in this dataset" instead of a slot/weapon-type claim for these.
- **Known limitation, accepted rather than solved**: `naive_substitute`'s percent-vs-flat-number
  heuristic (see the Gear Set section above) is applied to all ~357 included talents' description
  text with no per-talent manual review — for the handful of gear-set talents shown elsewhere in
  this tool, a human has checked each substitution once; for this much larger set, that wasn't
  done. Occasionally produces a wrong-looking value (e.g. a 3-second duration rendered as `300%`)
  since a value's *type* (percent/seconds/flat count) genuinely can't be inferred from the raw
  number alone. Flagged in the page's own "About the Talent Browser" note rather than silently
  shipped as if verified.
- **Deliberately not attempted by this pipeline**: inferring which of these talents'
  conditional/situational effects could be surfaced as a "potential" bonus type. That work exists
  now — see "Potential Bonuses — inferred conditional attributes" below — but lives in its own
  persisted dictionary and consumption step, not in `extract_all_talents.py`'s own classification
  logic.

## Potential Bonuses — inferred conditional attributes (Talent Browser, Part 2)

A talent's tooltip text often grants a real bonus attribute (Weapon Damage, Skill Damage, Bonus
Armor, ...) *conditionally* — e.g. Composure: "increases total weapon damage by 15% while in
cover." This was always the second half of the original "add a Talent Browser" request (see the
session note at the end of this file) — deliberately split off and started only once Part 1 (the
Talent Browser tab itself, fully covered above) had shipped and been trusted through three rounds
of user-caught classification bugs.

- **No script can reliably do this interpretation.** Free-form flavor text ("while all skills are
  on cooldown", "per stack up to 5, 15s") isn't structured data — deciding *which* named attribute
  a given sentence maps to, and phrasing its trigger condition, is a judgment call. So it's done
  **once**, by hand (an AI read every gear-slotted talent's description and classified it), and
  the result is persisted in `tools/talent_bonus_inferences.json` — the same
  "persist the one-time expensive judgment call, let the script only ever check for drift" pattern
  already established by `tools/attribute_uid_dictionary.json` (attribute UID → name) and
  `tools/named_items_manual_overrides.json` (named-item corrections). The user's own framing for
  this session: interpret the text once, store it in a dictionary, and have the Python script only
  ever *point out* new/changed talents for a future interpretation pass — never try to re-derive
  the interpretation itself.
- **Schema**: `{talent_id: {"fingerprint": md5(description), "bonuses": [{"attribute",
  "condition"}, ...]}}`. `bonuses: []` is a real, meaningful answer — "this talent was reviewed
  and genuinely grants nothing mappable to a named attribute" (e.g. a pure unlock like "Second
  Primary Weapon", or a proc that doesn't cleanly correspond to any tracked stat, like a stun
  immunity or a mark/debuff mechanic) — distinct from "not yet reviewed" (id simply absent from
  the dictionary). `condition` is a short human-readable trigger description, not a parseable
  format.
- **Scope: `kind` in `{gear, exotic-gear}` only (138 talents)**, not all 357. This mirrors the
  Attribute Finder's own scope: it only ever answers "which gear should I equip for bonus X", and
  this tool tracks no weapons at all, so a weapon-side talent's potential bonus has no "equip
  this" answer to attach it to. Deliberately excludes `weapon`/`exotic-weapon`/`exotic-other`/
  `other` (219 talents) — those stay Talent-Browser-only, exactly as before this feature existed.
- **Attribute vocabulary**: reuses the exact names in `tools/attribute_uid_dictionary.json`
  (Weapon Damage, Skill Damage, Skill Repair, Critical Hit Chance, Headshot Damage, ...) wherever
  a talent's wording matches a real guaranteed-bonus stat, but is **not limited to that
  vocabulary** — talents also introduced their own new-but-consistent names not used anywhere
  else in this dataset, because they describe mechanics no Brand/Gear Set/Named/Exotic Item ever
  grants as a guaranteed roll: `Amplified Damage` (the game's own distinct "target takes X% more
  damage" mechanic — kept separate from `Weapon Damage`/`Skill Damage` whenever a tooltip's own
  wording says "amplifies"/"amplified", since Division 2 treats it as a different calculation
  layer), `Bonus Armor` (temporary overshield procs — kept separate from `Armor Regeneration`,
  which is reserved for talents that literally *repair/heal* a % of armor, since these are
  different in-game mechanics that just sound similar), `Damage Resistance`, `Movement Speed`,
  `Grenade Damage`/`Grenade Radius`/`Grenade Capacity`, `Armor Kit Capacity`, `Revive Speed`.
  Deliberately reused the same name across every talent describing the same effect (rather than
  inventing near-duplicate names per-talent) so a future Attribute-Finder cross-reference could
  still meaningfully group them.
- **Unconditional talent-granted bonuses are still recorded**, with `condition: "Always active"`
  — a handful of talents (mostly exotics, e.g. "...Two in the Bag": +100% Armor Kit Capacity,
  +300% Grenade Capacity, +25% Ammo Capacity, +10% Skill Repair, +10% Status Effects, all with no
  trigger condition at all) grant a flat, guaranteed stat purely through their talent text, the
  same way a Named Item's Fixed attribute slot does — worth surfacing even though there's no
  "condition" in the everyday sense.
- **Drift detection**: `extract_all_talents.py`'s `apply_bonus_inferences()` hashes each in-scope
  talent's *current* description (md5) and compares against the fingerprint stored at
  interpretation time. A mismatch (a rebalance patch changed the numbers/wording) or a missing id
  (a new talent) means the persisted `bonuses` are stale or absent — the talent gets flagged in
  `tools/all_talents_report.md`'s "Potential-bonus inference coverage" section and **no**
  `potentialBonuses` field is attached to its `data/all_talents.json` entry until it's
  re-interpreted by hand. The dictionary is never auto-edited by the script — only ever read and
  diffed against.
- **UI**: each Talent Browser card with a non-empty `potentialBonuses` array gets a
  "Potential Bonuses (Conditional)" block (distinct dashed divider, `--accent2` cyan-blue color —
  deliberately different from the orange `--accent` used elsewhere for a confirmed/guaranteed
  bonus match, so a user can't mistake a conditional talent effect for a guaranteed one at a
  glance). Talents with `bonuses: []` (reviewed, nothing mappable) simply show no such block, same
  as a talent that was never in scope.
- **Wired into the main Attribute Finder tab** (Part 2b, same session as Part 2a above, once the
  user confirmed how each half should be represented):
  - **Exotic Items**: `extract_exotic_items.py` now also emits `talentId` per item (the
    `.mtalent` instance id behind its own unique talent — previously computed internally as
    `preset_talent["ref_file"]` but never persisted to the output JSON). `index.html` builds
    `TALENT_BY_ID` (an id → `ALL_TALENTS` entry map) and uses it to attach the item's own talent's
    `potentialBonuses` as a `potentialTiers` array on that Exotic Item's existing
    `EXOTIC_ITEM_ENTRIES` object — rendered as a "Potential bonuses (conditional)" block directly
    on the item's card (`renderResults()`'s `b.kind === "Exotic Item"` branch), right where its
    Fixed attributes and talent description already show. Exactly the user's own framing: "just
    include it into the item card."
  - **Generic (not-item-specific) talents**: the `gear`-kind Chest/Backpack talents (rollable on
    any brand) plus the `exotic-gear` talents that turned out to have *no* matching Exotic Item in
    this dataset at all (discovered while wiring this up, not previously known —
    `extract_exotic_items.py` only ever produced 28 items; verified by checking every real Exotic
    Item's own `talentId` and confirming none of these ids appear) get their own standalone result
    card in the Attribute Finder's results list, styled identically to a Talent Browser card
    (`GENERIC_TALENT_ENTRIES`, rendered by the `b.kind === "Talent"` branch) — exactly the user's
    own framing for these: "surface the talent card... as an individual result." A `talentKind`
    field (`"gear"` vs `"exotic-gear"`) picks the badge color/label so the orphaned exotics still
    read as exotic content, not confused with the generic pool. **Important**: not having a
    matching Exotic Item in this dataset does NOT mean legacy/cut — see "liveness filtering" below
    (a same-session follow-up) for the full, corrected breakdown of exactly which of these are
    confirmed real vs. genuinely unconfirmed, after an initial pass here wrongly generalized from
    a couple of real examples to the whole set.
  - **Chip vocabulary**: `ALL_STATS` (the full bonus-type chip list) now folds in `potentialTiers`
    stats alongside `tiers` stats — otherwise a stat that ONLY ever comes from a conditional talent
    effect (`Amplified Damage`, `Bonus Armor`, `Armor Kit Capacity`, ...) could never be selected
    as a chip at all, and the whole point of this wiring (letting a user search "Amplified Damage"
    and find what can grant it) would silently fail. Matching (`statsHere` in `renderResults()`)
    was broadened the same way, so ANY/ALL mode both correctly treat a conditional match as a hit.
  - Verified live in-browser (not just statically): selecting "Armor Kit Capacity" surfaces
    "... Two in the Bag" as a standalone Exotic Gear Talent card (its only source, since it has no
    matching item); selecting "Amplified Damage" surfaces both item cards (Overdogs, via its
    Weakest Link talent) and standalone talent cards (Ostracize, Headhunter, Glass Cannon, Spotter,
    ...) side by side, each with the matching row highlighted. No console errors, no regressions
    to the pre-existing Attribute Finder or Talent Browser behavior.
- **Liveness filtering** (same session, immediately after the wiring above — the user's own
  explicit general rule: "don't surface any items or talents that are currently not actively used
  in the game," recognized the same way everything else in this codebase is, from structural
  references in the game's own files, never guessed from a name or a hunch):
  - **`talent_back_hoarder_grenade_enhancements` ("Hoarder") turned out to be Collector's own
    unique talent, misclassified as generic `gear`** — a real, previously-unknown bug, not a
    liveness question. Its filename carries no "exotic" token at all, so `classify_talent`'s
    prefix-alias step (which only even attempts an exotic-item cross-reference once it's already
    decided the id *looks* exotic) never had a chance to catch it; it fell straight into the
    generic Chest/Backpack bucket, implying random-roll availability on any brand, when it's
    really Collector's own, item-specific ability. Fixed in `extract_all_talents.py`'s
    `build_all_talents()` by running the `build_exotic_gear_talent_slots()` item-side
    cross-reference **universally, first, for every kind** — not just ones `classify_talent`
    already suspected were exotic — so an item-preset match always wins regardless of what the
    talent's own filename suggested. Recovered 6 reclassifications total (5 were the
    already-known `exotic-unresolved` → `exotic-gear` cases, now just resolved one step earlier;
    Hoarder was the one genuinely new one). This is exactly why the exotic-gear talent *total*
    went from 39 to 40 between the two bullets above and this one — Hoarder moved in, not a new
    file appearing.
  - **A later, same-session correction — the "11 orphaned exotic-gear talents" characterization
    above was too broad.** The user searched "Grenade Capacity" in the Attribute Finder, got
    "... Two in the Bag" as a hit (correct — it's a real talent with real potential bonuses) but
    noticed no matching item card, and asked whether this was the same kind of "not associated
    with an item" case. Investigating properly (not just repeating the earlier assumption) found
    real content, not legacy data: `player_gear_back_exotic_01_config` exists as a complete,
    live-looking `ItemGenerationConfig` — two guaranteed bonus slots (Skill Haste, Skill Damage), a
    Core (Skill Power/Yellow), and **two** `myPresetTalent` entries (mk1a AND mk1b, both at once —
    explaining their "One in Hand..." / "...Two in the Bag" wordplay pairing, a reference to "a
    bird in hand is worth two in the bush"). Its owning item's actual `.mitem` file (which would
    give its real name/flavor text) simply isn't present anywhere in this export — only
    `blueprint_craft_player_gear_back_exotic_01.mitem` (the crafting recipe) survived. Same
    situation confirmed for `talent_exotic_kneepads_mk1_a` ("Grace Under Fire") via
    `player_gear_kneepads_exotic_01_config`. This is a genuine export-completeness gap — the same
    kind already well-precedented in this codebase (Ongoing Directive's backpack talent, several
    named items' once-missing `.mtalent` files) — **not** legacy/cut design content, despite the
    `_mk1a`/`_mk1b`-style naming looking superficially similar to genuinely-dead variants.
    - Root cause this exposed: `build_exotic_gear_talent_slots` (the existing item→talent reverse
      lookup) can only ever walk real `.mitem` files, so it has no way to learn about a config
      whose owning item file doesn't exist. Fixed by adding
      `build_exotic_gear_talent_slots_from_configs()` — an independent second source for the same
      `{talent_id: slot}` map, this one walking every `ItemGenerationConfig` declaration directly
      (already indexed flatly across the whole `itemgeneration/configs/` directory by the existing
      `_index_generation_configs` helper, including the `configs_exotics_code1_data*` family — an
      earlier note in this file calling that family "unnecessary" was based on it never adding
      anything *beyond* what the 28 already-found items' regular per-slot configs already had, not
      on it being excluded from the search; it never was) and deriving the slot from the config's
      own declared name via the same `SLOT_MAP` token match `parse_named_item_file` uses on an
      item's filename, instead of requiring the item file at all. Also, unlike `parse_preset_talent`
      (which only ever returns the first `myPresetTalent` match), this new function collects EVERY
      one per config, since a single config can genuinely assign more than one (confirmed by the
      two-talent Backpack above). Merged as a fallback under the existing item-based map (which
      wins on the rare id both would resolve). In this export it changes zero `kind`/`slot` values
      — mk1a/mk1b/kneepads_mk1_a's own filenames already carried a correct slot token, so
      `classify_talent` had already gotten their slot right by itself — but it does let
      `tools/all_talents_report.md` correctly flag exactly which orphaned exotic-gear talents are
      *confirmed real* (own config found) versus genuinely unconfirmed, under a new "Confirmed
      real... but the owning item's own .mitem file is missing" report section.
    - Net correction to the 12 exotic-gear talents with no matching `EXOTIC_ITEMS` entry: **3 are
      confirmed real** (`...Two in the Bag`, `One in Hand...`, `Grace Under Fire` — export gap,
      not legacy), **2 belong to items already known and deliberately excluded for documented
      reasons unrelated to liveness** (`talent_exotic_ostracize` → the "TBD" kneepads placeholder
      item, `talent_exotic_mask_invested` → Investor, both per the Exotic Items section above —
      confirmed by checking their own talent text against what's already documented for those two
      items), and **7 remain genuinely unconfirmed** (gloves `mk1_b`/`mk1_c`, holster `mk1_b`/
      `mk1_c`, kneepads `mk1_b`/`mk1_c`, `virginia_talent_exotic_mask_byzantine_inferno_wrath`) —
      these only ever appear as a same-file `include` line across every `configs_exotics_*` shard,
      never as an actual `myPresetTalent` assignment anywhere, the one structural signal that
      distinguishes a real-but-unnamed item (like the 3 above) from a talent that was truly never
      wired to anything. Only these 7 are accurately called "legacy/likely unused" — a narrower,
      now-verified claim than the original blanket "11 are early/duplicate design variants."
  - **Resolved, same session, immediately after**: the user checked in-game and confirmed the
    Backpack's real name — **Acosta's Go Bag** — closing the gap the bullet above could only
    describe, not fix. Also confirmed directly by the user: its two talents ("One in Hand...",
    "...Two in the Bag") really are both simultaneously active, not one live/one-unused draft —
    the config's own two `myPresetTalent` entries were telling the truth. Added
    `tools/exotic_items_manual_additions.json` (instance_id → confirmed `name`/
    `isDarkZoneExclusive`/`note`, same "persist the one fact datamining can never supply, verify
    everything else structurally" pattern as `named_items_manual_overrides.json`) and
    `build_manual_config_items()` in `extract_exotic_items.py`, which reconstructs a full
    `EXOTIC_ITEMS` entry straight from the item's own `ItemGenerationConfig` for any instance_id
    listed there — bonuses via the same `parse_preset_attributes` path every other exotic uses,
    cores via `parse_core_attributes`, and **every** `myPresetTalent` in the config (not just the
    first, unlike `parse_preset_talent` — this item is the reason a multi-match variant was
    needed at all). Schema addition: an `extraTalents` array (empty for all 28 pre-existing items)
    holds any talent beyond the first `talent`/`talentId` pair; `index.html`'s
    `EXOTIC_ITEM_ENTRIES` folds every extra talent's `potentialBonuses` into the same
    `potentialTiers` union as the primary one, and `EXOTIC_TALENT_IDS_WITH_ITEM` (which decides
    whether an exotic-gear talent gets its own standalone `GENERIC_TALENT_ENTRIES` card or attaches
    to an item) now checks `extraTalents` too — Acosta's Go Bag correctly absorbed both talents out
    of the standalone-card pool once this landed. The Exotic Item card's own renderer gained a
    loop over `extraTalents` for the summary row *and* the full description block, right alongside
    the existing single-talent code path, which is untouched for every other item. Total Exotic
    Items: 28 → 29. `talent_exotic_kneepads_mk1_a` ("Grace Under Fire") remains in the same state
    the bullet above left it — confirmed real, config-resolvable, just not yet name-confirmed by
    the user — and would take exactly the same one-entry addition to this same file if/when it is.
  - **A related but structurally different orphan, resolved the same way conceptually but not the
    same mechanism**: the user noticed "Slotted" (Investor's own talent) was still orphaned too,
    and asked whether Investor — excluded outright since the "Exotic Items — datamining notes"
    section above, confirmed intentionally fully-random rather than following the "always X and Y"
    model — could just be included now that there's a talent to connect it to. Unlike Acosta's Go
    Bag, Investor's own `.mitem` file was never missing; it was a deliberate design-fit exclusion.
    Re-reading its config directly confirmed every one of its Core/bonus slots really does carry
    the usual null-UID "not preset" sentinel (not a fabricated or half-resolved state), so
    un-excluding it produces an honest, correct `bonuses: []`/`cores: []` — nothing invented.
    `EXCLUDED_INSTANCE_IDS` dropped to empty; a new `CONFIRMED_RANDOM_BONUS_ITEMS` set (currently
    just this one id, with the full reasoning inline as a comment) suppresses the
    `MISSING_BONUS_ATTRIBUTE` review-note path for its 3 null-UID bonus slots specifically (that
    note's usual meaning — a real export gap needing research — would be wrong here) and sets a
    new `"bonusesRandom": true` field instead. `index.html` renders that as an explicit "Any Core
    (confirmed fully random)" badge and a "Bonus attributes fully random — no fixed types
    (confirmed)" row, rather than the "not yet resolved" language used for a genuine gap, which
    would have implied this was still missing data rather than a confirmed design fact. Exotic
    Items: 29 → 30.
  - **The remaining pool-absent `gear`-kind talents needed a second, independent liveness check**:
    a Chest/Backpack talent absent from the random-roll pool isn't necessarily dead — it might be
    one specific Named Item's own directly-assigned talent instead (confirmed real precedent:
    Festive Delivery's Fireworks Show, `talent_gear_back_firecrackers`, never in the pool by
    design). So `extract_named_items.py` got the same `talentId` treatment `extract_exotic_items.py`
    already got (the `.mtalent` id behind a Named Item's own preset talent, previously computed
    internally via `parse_preset_talent` but never persisted to `named_items.json`). With both
    cross-references available, `build_all_talents()` now excludes any `gear`-kind talent that
    matches **neither** the live pool **nor** a Named Item's own `talentId` — genuinely
    legacy/cut data, not shown as if obtainable. Confirmed exactly 5 of the 7 originally
    pool-absent talents fail both checks and are excluded: **Aegis, Lazarus, Patched, Second
    Primary Weapon, Selfless** (two of the seven, Fireworks Show and Hoarder, are accounted for by
    the two liveness signals respectively). Aegis and Second Primary Weapon's dead status has
    independent corroboration already in this file: both names appear, verbatim, in the
    `dev_testing_backpack_talents`/`dev_testing_chest_talents` containers documented above as
    "confirmed never referenced by any real Chest/Backpack config" — i.e. this exclusion agrees
    with a fact already established by a completely different piece of archaeology, not a new
    guess. `data/all_talents.json`'s talent count dropped from 357 to 352 as a result (`gear`:
    99 → 93; `exotic-gear`: 39 → 40). `tools/talent_bonus_inferences.json` keeps its now-orphaned
    entries for these 5 rather than deleting them (same "never delete good data, overrides just go
    inert" policy as `named_items_manual_overrides.json`) — if a future export or patch makes any
    of them live again, the interpretation is already sitting there ready to apply.
  - **Weapon-side liveness (kind `weapon`/`exotic-weapon`/`exotic-other`/`other`, ~259 talents) is
    explicitly NOT attempted here** — the user asked to scope this session to the gear side only.
    A quick investigation (grepping `itemgeneration/configs/configs_code1_data*.mitemgenerationconfigs`
    for weapon `ItemGenerationConfig`s) confirmed weapon items DO have their own per-model talent
    slot data, structurally similar in spirit to the Chest/Backpack pool mechanism — but the shape
    is meaningfully different (a base weapon config like Carbine 7's assigns one `myPresetTalent`
    directly at Orange quality rather than referencing a random pool, with Blue/Purple quality
    referencing a shared, not-yet-traced `generic_*_weapon_talent_slots_definition` template) and
    would need the same kind of careful, multi-round verification the Chest/Backpack pool itself
    took (including two rounds of user-caught mistakes) before trusting it enough to exclude real
    content. Left as a distinct, dedicated follow-up rather than rushed.
  - **`kind: "other"` (the no-slot-token catch-all, 45 talents) renamed "Legacy / Removed"**
    (was "Universal / Other") in `index.html` — both the Talent Browser's kind-toggle button and
    its category chip, plus the `KIND_BADGE_LABEL`/`CATEGORY_ORDER` entries and card badge text.
    Purely a label change on the user's own explicit say-so ("that'll do for now"), based on their
    observation that this whole bucket looks like cut content — **not** independently structurally
    verified the way Chest/Backpack liveness now is (that would need the weapon-side pool work
    above, since these are unrestricted weapon-or-gear talents by definition). The page's own
    "About the Talent Browser" note says so explicitly, so a future session (or a sharp-eyed user)
    doesn't mistake the rename for a verified claim.

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

The same session then closed out the "35 items' unique talent text wasn't resolvable" gap
mentioned above, partially: the user supplied the confirmed real talent *name* (not description)
for all 35, sourced from their own in-game knowledge, as a plain name -- talent-name list.
`tools/named_items_manual_overrides.json` now supports a `talentName` (+ `talentNote`) key per
instance_id alongside the pre-existing `name` key, applied in `extract_named_items.py` only when
a talent is otherwise fully unresolved (referenced `.mtalent` file missing *and* no description
fallback) -- deliberately name-only, not a guessed description: `talent_status` becomes
`"manual_name_only"`, `out["talent"] = {"name": ..., "desc": None}`, and `talentStatus` is still
set to `"needs_manual_research"` so the page's existing `b.talent.desc` check keeps showing "Full
talent text not yet catalogued." for the description instead of inventing one. This needed no
index.html changes at all -- the existing `if (b.talent)` / `if (b.talent && b.talent.desc)`
branches already handled a name-without-desc talent correctly once the data supported it. All 62
items with a unique talent now show a real name on their card; 43 items have a talent at all (the
remaining 19 are Gloves/Holster/Kneepads/Mask items with only a Fixed attribute, no talent), of
which 8 have the full datamined description and 35 have a confirmed name only. Re-running `extract_named_items.py` against a fuller future export will
naturally upgrade any of the 35 to a full datamined description without touching the overrides
file, since the datamined path is tried first and only falls through to the override when the
`.mtalent` file is still missing.

A rebalance patch is expected in the next few weeks that will remove some bonuses (Shock
Resistance, Health, Incoming Repairs, Swap Speed), add a new one ("Protection from Elites"), and
reshuffle which stat appears on which brand/set. The update script is designed to handle this
without help *except* for naming the one new attribute type the first time it's seen — see
`tools/attribute_uid_dictionary.json` and the "Updating the dataset" section of `README.md`.

## 2026-08-18 session: a much fuller Hunter export turned out to fix bugs, not just add data

The user re-exported raw files with Hunter and got a dramatically larger tree (`hunter/` alone
had ~2M files this time, vs. a much smaller export before) at `E:\Temp\Hunter\raw_files\hunter`.
Re-running `update_from_hunter_export.py` against it changed **nothing** in
`data/combined_sets.json` (0 added/removed/changed, 0 unresolved UIDs) — the existing 64-entry
Brand/Gear Set dataset was already fully correct. The one remaining structural warning (Ongoing
Directive's backpack companion talent) was independently confirmed still genuinely missing by
searching the full export directly for anything ongoingdirective-related: only `_5piece`,
`_6piece`, and `_chest` `.mtalent` files exist, no `_back` file at all. That's a real content gap
in every export seen so far, not a lookup bug.

Named Items told a very different story. Re-running `extract_named_items.py` against the same
export took "35 items' talent text unresolvable" (the previous session's understanding, believed
to be a genuine export gap) down to **zero** — all 43 items that have a unique talent now show
its full datamined name *and* description, not just a manually-recalled name. That number jump
came from finding and fixing four real, pre-existing bugs that this fuller export happened to be
the first thing to actually exercise:

1. **`parse_mtalent_file`'s instance-id regex didn't handle subclass syntax.** "Perfect"-tier
   talent files (the very ones behind most named items' unique talents) declare
   `Talent <id> < uid=... > : <base_talent> { ... }` — a `: <base_talent>` subclass clause between
   the uid and the opening brace that the regex (`Talent\s+(\S+)\s*<[^>]*>\s*\{`) never accounted
   for, so it silently returned `None` for every one of them (106 files in this export) even
   though the files were sitting right there. This — not a missing export — was the real root
   cause of the previous session's "35 items still unresolvable" gap. Fixed by making the
   subclass clause optional in the regex: `(?:\s*:\s*\S+\s*)?` before the `\{`.
2. **`extract_localized_text` only handled one `text = ` quote-delimiter style.** It assumed
   `text = \"...\"` (backslash-escaped double quote) always; Perfect-tier talents' `myUIName`
   fields use `text = '...'` (bare single quote) instead, same ambiguity
   `extract_marked_value` in `extract_named_items.py` already handled for item names/descriptions
   — ported that same both-styles logic in here too (shared by gear-set *and* talent parsing).
3. **The `index.html` DATA-embed regex was greedy + `DOTALL`, and silently deleted `NAMED_ITEMS`
   on every run.** `const DATA = \[.*\];` with `re.DOTALL` matches from `const DATA = [` through
   the *last* `];` anywhere in the rest of the file — i.e., straight through `NAMED_ITEMS`'s own
   closing bracket, since both consts are adjacent single-line minified-JSON declarations. This
   was **confirmed to actually happen** to a committed `index.html` while re-running the script
   this session (`NAMED_ITEMS` count went from 2 to 0 after one run) — caught before it was
   committed, via `git checkout -- index.html` to recover, but it means every *previous* run of
   `update_from_hunter_export.py` had this same live landmine. Fixed by scoping the match to
   `[^\n]*` instead of `.*`/`DOTALL` — both consts are guaranteed single-line, so this makes the
   cross-array match structurally impossible rather than just less likely.
4. **`re.sub`/`re.subn` interpret backslash escapes in a *string* replacement.** Both the DATA and
   NAMED_ITEMS embed steps passed the new minified JSON as a plain string replacement; the `re`
   module treats `\n`, `\g<...>`, etc. in a string replacement the same way it would in a pattern.
   Named items' flavor/tooltip text legitimately contains literal `\n` (e.g. Backbone: `"...you do
   it."\n- The Strategist`), which was silently turned into a *real* embedded newline mid-JSON,
   corrupting the embed (confirmed by direct byte inspection: source JSON had zero raw newlines,
   the written `index.html` had one, in exactly that spot). Root-caused *after* initially
   suspecting Bash tool shell-quoting — a minimal repro without any shell involved reproduced it
   from `re.sub` alone. Fixed by passing a replacement *function* (`lambda m: new_line`) instead of
   a string; a function's return value is inserted verbatim with no escape processing. This
   pattern is now used for both embed steps in both scripts — don't revert to a string replacement
   here even for a "quick" edit.
5. **`naive_substitute` double-appended `%`.** Its percent heuristic (`abs(v) < 5` → format as
   `%` and append a literal `%`) assumed the talent-tooltip template never already had its own
   `%` after `{n}` — true for every previously-resolved gear-set talent, false for several
   Perfect-tier ones (`"...by {0}%..."` in the template *plus* the heuristic's own appended `%` →
   `"7%%"`). Fixed by peeking at the template's next character and skipping the append when it's
   already `%`. Verified zero regressions against the existing (already-`%%`-free) gear-set
   dataset before and after.

`extract_named_items.py` now also auto-embeds into `index.html` itself, the same way
`update_from_hunter_export.py` already did for `DATA` (using the same newline-scoped-match +
replacement-function pattern from fixes #3/#4 above) — this closes out what used to be a
documented *manual* re-embed step, which is exactly what triggered the bug #4 corruption in the
first place when done by hand this session. `README.md`'s "Updating Named Items" section reflects
this; there is no more manual re-embed step.

Net effect on data quality: all 62 named items still resolve exactly as before structurally (62
items, 43 with a talent, 19 Gloves/Holster/Kneepads/Mask-only with no talent), but all 43 talents
now carry a full datamined description instead of 8 full + 35 name-only.
`tools/named_items_manual_overrides.json`'s `talentName` entries are now inert for every item
(the datamined path resolves first and wins) but were deliberately left in place rather than
pruned, per the file's own established role as a safety net if a future export ever regresses —
consistent with the project's standing "never delete good data" approach. Two of the 35 previously
manually-recalled names turned out to be slightly wrong once compared against the real datamined
text: Carpenter's talent is "**Perfectly** Mad Bomber" (not "Perfect Mad Bomber"), Combustor's is
"**Perfectly** Explosive Delivery" (not "Perfect Explosive Delivery") — minor recall slips, now
silently corrected since datamined data takes priority automatically.

Also investigated whether the fuller export's newly-present
`game system data/juice/itemgeneration/attributelists/*.mitemgenerationattributelists`
(completely absent from every export used before, previously assumed to be the reason a named
item's *exact* fixed-attribute value couldn't be reported) would close that gap. It doesn't, but
not because of missing data this time: the relevant `AttributeListContainer NamedAttributes`
blocks hold `myRangeMin`/`myRangeMax` as **gear-score-dependent curve formulas**
(`ItemGenerationBracketedCurveFormula`, referencing named brackets like `Percent_1_To_10` defined
by `myMaxPower`/`myA`/`myB`/`myC` per level range), not flat numbers — there is no single "the
value" to extract without first picking a target gear score to evaluate the curve at. This is a
real structural/design fact about how the game generates item stats, not an export gap, so
"which stat, not how much" for a named item's Fixed attribute is now a deliberate, understood
scope limit rather than an open question — no curve-evaluation work was attempted this session
(would be a real feature addition, not a bug fix, and wasn't asked for).

### Follow-up the same session: attempted max-gear-score fixed-value extraction, dropped it

The user asked, given the curve system above, whether the *max gear score* value specifically
could be shown (sidestepping the "which target gear score" ambiguity by always picking the
highest one). This got much further than expected but ultimately didn't reach a trustworthy
formula, and was deliberately dropped rather than shipped — worth recording so a future attempt
doesn't have to redo the same archaeology from scratch.

**What was found**, tracing a named item's Fixed attribute end to end:
- A config's Orange-tier `ItemAttributeSlot` has `myPresetAttribute <uid>` and
  `myPresetPercentage <n>` (see the "Named Items" section above for the slot structure itself).
  `myPresetPercentage` is **not** a 0–100 position within the attribute's roll range like its name
  suggests — real values seen include `210.0`, `900.0`, `400.0`, `220.0`, `145.0`, `214.0`, not
  just the expected `100.0`. What it actually represents is still unresolved.
- The slot's `myPossibleAttributeLists` entry has the same two-uid reference shape seen elsewhere
  in this codebase (talent refs, gear-set 4pc refs): `AttributeListContainer "List 0" <
  uid=LOCAL_INSTANCE_ID > = SomeName TARGET_GUID`. The **trailing GUID**, not the `<uid=...>` one,
  is the actual `AttributeListContainer`'s own identity — got this backwards on the first attempt
  (mirrors the exact same class of bug documented above for `parse_preset_talent`'s `ref_file`
  history). There are 957 distinct containers by their own uid but only ~72 distinct *ref-names*
  (`NamedAttributes`, `GlovesOffense`, etc.) reused across many files/slot-families — matching by
  ref-name alone silently picks an arbitrary wrong container.
- A container declaration can itself be a pure alias with no body: `AttributeListContainer
  KneepadsOffense < uid=X > = OffensiveGearStatsBase Y` (no `{...}` following) — the real
  `AttributeData` entries live in whatever `Y` resolves to, which can itself be another alias.
  This indirection wasn't present on the "named item exclusive" pools (`NamedAttributes`,
  `GlovesNamed`, etc.) but *was* present for stats shared with regular random rolls (crit
  chance/damage, weapon handling, headshot damage) — named items borrow those items' general
  attribute pools rather than having their own.
- Inside an `AttributeData` block, `myRangeMin`/`myRangeMax` are each either an inline one-off
  `ItemGenerationBracketedCurveFormula { myA myB myC }` or a reference (`= CurveName <guid>`) to a
  shared named `ItemGenerationBracketedCurve` with multiple brackets keyed by `myMaxPower`
  (observed labels: "1-30 MIN", "31-40", "41-50" — read as character-level-ish brackets, though
  never confirmed). The **last** bracket has no `myMaxPower` (unbounded) and, for every curve
  actually used by a named item's Fixed attribute, had `myA = myB = 0` — i.e. flattens to a
  constant (`myC`) once "power" is high enough, which is what "max gear score" should read off of.
  This part seems solid: re-verified same-file curve definitions aren't silently diverging across
  the ~20 near-duplicate attributelist files for the handful actually checked.
- `AttributeData` blocks can carry `myQualityModifiers { QualityCurveModifier Orange { myModifier
  1.2 } }` — a real per-quality multiplier — but **only** on the shared/general pools, not on the
  `NamedAttributes`-flavored ones (which declare the Orange block with no `myModifier` field at
  all, i.e. implicitly 1.0). Missing this the first time around was why an initial pass looked
  much worse than it should have.

**Where it broke down**: tested `value = topBracketC(myRangeMax's curve) × (myPresetPercentage /
100) × qualityModifier(Orange, default 1.0)` against 6 real values the user confirmed in-game
(2026-08-18) and it matched exactly for only 2 of them:

| item | stat | formula result | real value |
|---|---|---|---|
| Salvo | Rate of Fire | 5% | 5% ✅ |
| Turmoil | Crit Hit Chance | 6% | 6% ✅ |
| Deathgrips | Armor on Kill | 9% | 10% ❌ |
| The Hollow Man | Damage to Health | 13.05% | 14% ❌ |
| Turmoil | Crit Hit Damage | 10.8% | 12% ❌ |
| Forge | Shield Health | 81% | 50% ❌ |
| Claws Out | Melee Damage | 800% | 500% ❌ |

The two large misses (Forge, Claws Out) are exactly the two items whose `myPresetPercentage` is
far from 100 (`900.0`, `400.0`), so whatever that field means, it clearly isn't a simple linear
multiplier once it's away from 100 — real/computed ratios for those two (0.617, 0.625) are
suspiciously close to each other, hinting at *some* consistent non-linear relationship, but two
data points isn't enough to fit one with any confidence. The small ~1-point misses on otherwise
"clean" `pct=100` cases are unexplained too, and don't share an obvious common cause with each
other (ruled out: wrong-file curve lookup, missing quality modifier, rounding).

**Decision**: presented this table to the user and they chose to drop it rather than ship a
partially-wrong formula or a caveated "approximate" range — 2-out-of-7 confidence is too low for
a public tool. The `tools/_explore_maxvalues*.py` scripts used for this investigation were
throwaway and deleted; nothing in the shipped pipeline changed. If revisited, the honest starting
point is "the modifier/multiplier story is more complicated than `pct/100 × qualityModifier`, and
`myPresetPercentage` values above 100 need their own explanation" — not the formula above.

### Later the same session: Core attribute + Exotic Items added

In the same conversation, the user asked for two more things: (1) show each Named Item's Core
attribute (Red/Offensive, Blue/Defensive, Yellow/Utility) on its card, and (2) add a whole new
"Exotic Items" category (Catharsis, Memento, etc.) — gear with a unique talent that never appears
elsewhere, and (per the user) usually a small fixed set of guaranteed bonus *types* with randomized
values. Both landed; full technical detail is in the "Core attribute" and "Exotic Items —
datamining notes" sections above (placed with the other datamining reference material, not here,
since that's where a future session will look for it) — this entry just records what happened and
why, chronologically.

Cores turned out to need two rounds of correction before shipping. The first exploratory pass
(scanning all 4 quality tiers of a named item's config) found what looked like 2 multi-core named
items (Caesar's Guard, Henri) — turned out to be a false positive from not restricting to the
Orange tier (a named item's Core UID can genuinely differ *across* quality tiers; only Orange is
real). The user then confirmed a genuine multi-core case among the exotics instead: Memento
(a Backpack) really does have all three cores, always — which broke the working assumption that
`myPresetPercentage`'s sign reliably marks an active vs. decoy core slot (Memento's real, always-
active Blue slot is itself marked with the usual "-1.0 = inactive" sentinel). Ended up treating
every `myIsCoreAttribute TRUE` slot as active, full stop, for the core-extraction path specifically
— confirmed correct for Memento, assumed (not independently confirmed) for the two structurally
identical Harrier Pride and Ninja Bike Messenger Bag.

Exotic Items came together faster than expected, mostly because `extract_named_items.py`'s
existing parsing machinery turned out to need almost no changes — `parse_named_item_file`,
`find_generation_config_block`, `parse_preset_attributes`, and the whole talent-resolution path
all worked on exotic `.mitem`/config files with zero or one-line changes (see "Exotic Items —
datamining notes" above for specifics). The real work was three bugs the exotic files' flavor/name
text happened to be the first thing to exercise: a second `extract_braced` quote-desync pattern (9
files), a second distinct quote-style gap in the talent-tooltip parser (fixed by consolidating it
to reuse `extract_localized_text` instead of maintaining a third near-duplicate quote parser), and
a `myUIName` placeholder ("TBD") being silently overwritten by an unrelated internal editor label
before any placeholder check could see it (fixed with an `allow_comment_fallback` parameter,
verified zero effect on any existing Named Item's name). Net result: 28 real Exotic Items, all 28
with a fully datamined talent, one item (Acosta's Kneepads) with an honestly-flagged bonus-type
gap instead of a guess, and three confirmed-unreleased/random items (Rathbone's Gloves, a "TBD"
kneepad, and Investor) correctly excluded rather than shown broken or fabricated.

**Third round, after a screenshot from the user showed the shipped page**: two real UI/data
problems. (1) Core badges rendered in a row and could overflow a card's edge, hidden behind its
neighbor, on longer combinations like "Yellow — Skill Tier" — fixed by stacking them in a column
instead (guaranteed to fit the card's own width regardless of label length). (2) The user pointed
out Chainkiller and Closer both have a Red core in-game, contradicting what the page showed (no
core badge at all for either, alongside 17 other Backpack/Chest named items) — this was flagged
as "did you just not find it" rather than accepted as the documented design fact from earlier
("these items don't have a Core"), and the user was right to push: it *was* a bug, not a design
fact. Root cause and fix are in the "Core attribute" section above (the `_named`-stripping
base-item fallback, replacing an earlier ArmorItem-subclass attempt that resolved fewer cases).
Worth calling out here specifically because the *user's own confirmation was itself wrong* for
Closer (Red) on the first pass — sourced from a screenshot of someone else's item after using
Division 2's in-game Core recalibration feature, not the item's un-modified default — and they
caught and corrected this themselves once the datamined answer (Blue) didn't match. The datamined
default turned out to be the reliable ground truth once the extraction bug was actually fixed;
17 of 19 previously-blank named items now show a confirmed-correct Core this way. The final 2
(Force Multiplier, Door-Kicker's Knock) genuinely can't be datamined — even their base item's own
Core rolls randomly in this data — so the user checked both in-game directly (Yellow and Red) and
those went into `named_items_manual_overrides.json` as a last-resort fallback, same mechanism
already used for talent names. All 62 named items and all 28 exotic items now show a Core.

**Fourth round**: two more asks, both landed cleanly. (1) A dedicated Red/Blue/Yellow filter row
next to the existing kind toggle — entries with no `cores` field at all (Brand entries) drop out of
the results entirely when a specific color is selected, everything else filters down to just that
color; trivial once every relevant entry already carried a `cores` array from the earlier rounds.
(2) The user pointed out Gear Sets (Striker's Battlegear, Foundry Bulwark) also have a fixed Core
per piece, which the tool didn't show at all yet. This turned into real, useful new territory
rather than a copy-paste of the Named Item logic — full technical detail is in the "Core
attribute" section above. Short version: Gear Set pieces use `myQuality GearSet` (not `Orange`,
the default every other quality-scoped lookup in this codebase assumes), each set's `.mgearset`
file cleanly lists its 6 concrete pieces via `myItems`, and — most interestingly — 3 of the 27 sets
turned out to have genuinely non-uniform Cores across their pieces rather than the single shared
Core the other 24 have (Refactor and System Corruption split two Cores by slot; Core Strength is
deliberately flexible, confirmed by its own talent text literally saying "All pieces except the
Backpack feature random Cores"). Handled with one general rule — union of every Core resolved
across a set's 6 pieces — rather than special-casing the 3 exceptions, which reduces to the single
common case automatically for the other 24. All 27 Gear Sets now show a Core; Brand entries
deliberately don't (a civilian brand isn't one fixed item, so there's no single Core to show).

## 2026-08-22 session: Talent Browser Part 2 — potential/conditional bonus attributes

Picked up the explicitly-deferred "Part 2" from the Talent Browser work (see "All Talents" above):
inferring which talents conditionally grant a real bonus attribute, and surfacing that in the main
Attribute Finder tab. Landed in seven steps within the same session, each confirmed with the user
before moving to the next:

1. **The interpretation dictionary + drift-detection plumbing** (`tools/talent_bonus_inferences.json`,
   `extract_all_talents.py`'s `apply_bonus_inferences()`) — the user's own explicit design ask: do
   the (AI) interpretation once, persist it, and have the script only ever flag new/changed talents
   for a future pass rather than trying to re-derive the interpretation itself. Scoped to the 138
   gear-slotted talents (`gear` + `exotic-gear` kinds) since only those can attach to something
   equippable in this dataset. Full detail in "Potential Bonuses — inferred conditional attributes"
   above, including the attribute-vocabulary decisions (`Amplified Damage` vs `Weapon Damage`,
   `Bonus Armor` vs `Armor Regeneration`, etc.) and why unconditional talent-granted bonuses
   (`condition: "Always active"`) are still recorded rather than treated as out of scope.
2. **Wiring it into the Attribute Finder** — the user answered the fork left open at the end of
   step 1 directly: exotic-gear talents should attach to their item's existing card, generic
   (non-item-specific) talents should get their own standalone result card, same look as a Talent
   Browser card. Implementing the first half surfaced a real, previously-unknown data fact: 11 of
   the 39 `exotic-gear` talents in this dataset don't belong to any of the 28 extracted Exotic
   Items at all — handled by falling those 11 back to the same standalone-card treatment as the
   generic pool, rather than silently dropping their bonuses (and the chips for stats like
   `Armor Kit Capacity` that *only* ever come from one of them) from the Attribute Finder entirely.
   (At this point in the session they were assumed to be early/duplicate design variants; step 4
   below found that assumption was wrong for several of them.) Full detail in "Potential Bonuses"
   above.

Both steps were verified live in a real browser (extension was connected this session, unlike
earlier ones that had to fall back to static checks) — served the repo over a throwaway
`python -m http.server` since `file://` navigation is blocked by the extension's own sandboxing,
not because of anything in this codebase.

3. **A third, same-session follow-up**: the user noticed the 11 orphaned exotic-gear talents from
   step 2 and the Talent Browser's 45 "Universal / Other" talents both looked like cut content, and
   stated a general rule — don't surface anything not currently live in the game — asking whether
   this is recognizable from the game's own file references. It is, for gear: real archaeology
   (not a guess) found a genuine bug (Collector's own talent, "Hoarder", was misclassified as
   generic `gear` instead of `exotic-gear` because its filename carries no exotic-style token) and
   a real 5-talent exclusion (Aegis, Lazarus, Patched, Second Primary Weapon, Selfless — confirmed
   dead by checking them against both the random-roll pool and every Named Item's own preset
   talent, the two structural ways a Chest/Backpack talent is actually obtainable). For weapons, a
   quick investigation found the necessary data (`ItemGenerationConfig`s per weapon model) exists
   but has a meaningfully different, unproven shape — the user chose to scope this session to gear
   only and defer weapons as a dedicated follow-up, and to just rename the "Universal / Other"
   bucket to "Legacy / Removed" for now as an honest-but-unverified interim label rather than wait
   on the full weapon-side investigation. Full technical detail in "Potential Bonuses" above, under
   "Liveness filtering".
4. **A fourth, same-session correction**: the user then searched "Grenade Capacity" themselves,
   found "... Two in the Bag" (one of the 11 talents from step 2) as a hit with no matching item
   card, and asked the sharp follow-up — is this actually the same kind of unassociated-talent case
   as step 3's exclusions? It wasn't. Proper investigation (not repeating the step-2 assumption)
   found a real, fully-designed exotic Backpack config (two bonus slots, a Core, and genuinely
   *two* preset talents at once) whose own `.mitem` file is simply missing from this export — a
   real export gap, same class as several already-documented ones, not legacy/cut data. Confirmed
   the same for one more (`talent_exotic_kneepads_mk1_a`, "Grace Under Fire"), and confirmed two
   others from step 2 (Ostracize, Slotted) actually belong to items already known and deliberately
   excluded for unrelated, already-documented reasons (the "TBD" kneepad, Investor) rather than
   being unconfirmed. Net: only 7 of the original 11 are still accurately called
   likely-legacy/unconfirmed. Added `build_exotic_gear_talent_slots_from_configs()` so a talent's
   real config can be found even when its owning item's `.mitem` file can't be — this didn't change
   any `kind`/`slot` value in this particular export (the 3 confirmed-real talents already had a
   correct slot from their own filename), but it does make `tools/all_talents_report.md` correctly
   distinguish "confirmed real, item file missing" from "genuinely unconfirmed" going forward, and
   it's the right structural check to have regardless of what this one export happens to contain.
   Full technical detail in "Potential Bonuses" above, under "Liveness filtering" — the "later,
   same-session correction" bullet.
5. **A fifth, same-session follow-up**: the user checked in-game and came back with the confirmed
   name — Acosta's Go Bag — plus confirmation that both talents really are simultaneously active.
   Built the mechanism to actually use that: `tools/exotic_items_manual_additions.json` +
   `build_manual_config_items()`, reconstructing the full item straight from its
   `ItemGenerationConfig` (bonuses, cores, both talents) with only the name/DZ-flag taken on the
   user's word, plus a small `extraTalents` schema addition (`index.html`'s Exotic Item card,
   `potentialTiers` union, and the "does this exotic-gear talent already belong to an item" check
   all updated to fold it in). Exotic Items: 28 → 29. Full detail in "Potential Bonuses" above,
   under "Liveness filtering" — the "Resolved, same session, immediately after" bullet.
6. **A sixth, same-session bug fix**: the user spotted a literal broken `<img
   src="hunter/baked/...">` tag rendering in Kill Confirmed's description. Root cause:
   `strip_inline_markup` (shared by all three extraction scripts) only ever stripped `<color>`
   tags, never `<img>` ones — a talent tooltip can inline one of exactly 3 small core-attribute
   icons instead of spelling out the color (confirmed exhaustive by grepping every `.mtalent` file
   in a full export: `ui_player_offense/defense/utility.dds`, no other icon vocabulary exists).
   Fixed by mapping each to the matching color word (Red/Blue/Yellow, this codebase's own
   established `CORE_COLOR_BY_STAT` convention) instead of just deleting the tag, since at least
   one occurrence (Energy Infusion: "...for each `<img.../ui_player_utility.dds>` you have") uses
   the icon as a noun substitute, not a decorative prefix — stripping it outright would have left
   a grammatically broken sentence. Affected 5 occurrences across 4 talents total, only 1 of which
   (Kill Confirmed) the user happened to spot: Energy Infusion, Capacitance (exotic-weapon, out of
   `tools/talent_bonus_inferences.json`'s scope but still needed the same text fix), and Perfect
   Protected Reload. Re-running all three extraction scripts after the fix changed 3 talents'
   description text (and therefore their fingerprint), which `apply_bonus_inferences()` correctly
   flagged as drift — recomputed just the fingerprint for those 3 `tools/talent_bonus_inferences.json`
   entries (their actual `bonuses` needed no changes; the interpretation already said "Yellow
   core"/"Blue core" in its own condition text, unaffected by the raw description's own wording).
7. **A seventh, same-session follow-up**: the user asked about one more orphaned exotic-gear
   talent, "Slotted" — it belongs to Investor, which had been deliberately excluded (see "Exotic
   Items — datamining notes" above) since it's confirmed intentionally fully-random rather than
   following this dataset's usual "always X and Y" model. The user's own framing: now that there's
   a talent to connect it to, does it make sense to include the item after all? It did — re-reading
   Investor's own config confirmed every bonus/Core slot really does carry the null-UID sentinel,
   so un-excluding it produces an honest `bonuses: []`/`cores: []`, not a fabricated one. Added
   `CONFIRMED_RANDOM_BONUS_ITEMS` (currently just this one id) so its 3 null-UID bonus slots don't
   get logged as `MISSING_BONUS_ATTRIBUTE` (that note's usual meaning — a real gap needing
   research — doesn't apply here), and a `bonusesRandom` flag that `index.html` renders as an
   explicit "confirmed fully random" note instead of the "not yet resolved" language used for a
   genuine gap. Exotic Items: 29 → 30. Full detail in "Potential Bonuses" above, under "Liveness
   filtering" — the "related but structurally different orphan" bullet.

