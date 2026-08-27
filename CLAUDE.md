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
slot / weapon type, including talents' inferred conditional ("potential") bonus attributes, which
also surface as standalone result cards in the main tab. Self-contained — no build step, no
server, works from `file://`.

**Live:** https://mariokoehler.github.io/division-gear-db/ (GitHub Pages, `main` branch, root).
**Repo:** https://github.com/mariokoehler/division-gear-db (public).

## Hard constraint from the user, still in force

**Never modify the game's own install files.** The game is at
`E:\Ubisoft\Ubisoft Game Launcher\games\Tom Clancy's The Division 2`. Only ever read from there,
or from files the user has explicitly exported/copied elsewhere (e.g. `E:\Temp\Hunter\raw_files\`).

## Repo layout

- `index.html` — the whole tool (HTML/CSS/JS + the dataset embedded as four `const` arrays: `DATA`,
  `NAMED_ITEMS`, `EXOTIC_ITEMS`, `ALL_TALENTS`).
- `data/combined_sets.json` — Brand/Gear Set dataset, pretty-printed, source of truth.
  `data/combined_sets_min.json` — minified copy, what's actually embedded as `DATA`.
- `data/named_items.json` / `_min.json` — Named Items (Deathgrips, Turmoil, etc.), embedded as
  `NAMED_ITEMS`.
- `data/exotic_items.json` / `_min.json` — Exotic Items (Catharsis, Memento, etc.), embedded as
  `EXOTIC_ITEMS`.
- `data/all_talents.json` / `_min.json` — the full weapon/gear Talent catalog behind the "Talent
  Browser" tab, embedded as `ALL_TALENTS`.
- `tools/update_from_hunter_export.py` — regenerates the Brand/Gear Set files above from a fresh
  Hunter raw-file export. See "Updating the dataset" in `README.md` for run instructions.
- `tools/extract_named_items.py` — regenerates the Named Items files above and re-embeds
  `NAMED_ITEMS` into `index.html`. See "Named Items" below for the schema this parses.
- `tools/extract_exotic_items.py` — sibling to `extract_named_items.py`, reusing almost all of its
  parsing machinery; regenerates the Exotic Items files and re-embeds `EXOTIC_ITEMS`. See "Exotic
  Items" below for what's different from Named Items.
- `tools/extract_all_talents.py` — walks every `.mtalent` file in a raw export (not just the ones
  referenced by a specific Brand/Gear Set/Named/Exotic Item), classifies each one, and re-embeds
  `ALL_TALENTS`. See "All Talents" below. **Run this one last**, after the two scripts above — it
  reads their JSON output to recognize a Chest/Backpack talent as a specific item's own preset and
  to reclassify exotic talents its own filename gives no hint about.
- `tools/attribute_uid_dictionary.json` — persisted, accumulating map of attribute UID → stat name
  (e.g. `"Health"`). This is what makes future rebalance updates mostly automatic.
- `tools/named_items_manual_overrides.json` — persisted, hand-confirmed corrections keyed by
  instance_id (`name`, `core`/`coreNote`, `talentName`/`talentNote`) for the handful of facts that
  can't be datamined at all — see "Named Items" below for when each key applies.
- `tools/exotic_items_manual_additions.json` — persisted, hand-confirmed `name`/
  `isDarkZoneExclusive`/`note` for an Exotic Item whose own `.mitem` file is missing from every
  export used so far but whose `ItemGenerationConfig` is fully present. Applied by
  `build_manual_config_items()` in `extract_exotic_items.py`, which reconstructs the full entry
  (bonuses, cores, every preset talent) straight from the config — see "Exotic Items" below.
- `tools/talent_bonus_inferences.json` — persisted, hand-interpreted map of talent id → inferred
  conditional bonus attribute(s). See "Potential Bonuses" below.
- `tools/*_report.md` — gitignored, regenerated each run, not meant to be committed.

## Where the data actually comes from

Not a public API — there isn't one. The dataset is datamined directly from the game's own files:

1. The game ships gameplay data (item/gear/talent definitions) as plain-text config inside the
   Snowdrop engine's `.sdftoc`/`.sdfdata` archives (`hunter/sdf/pc/data/sdf.sdftoc` under the game
   install, ~99GB). These aren't readable directly.
2. [Hunter](https://tools.dtzxporter.com/) (community tool, GUI-only, Windows) opens that archive.
   **Critical setting:** its file-type filter has "raw files" *disabled by default* — the gameplay
   data files (`.mgearbrand`, `.mgearset`, `.mtalent`) only show up once that's turned on. Without
   it you only see animation/image/sound/model, which looks like the data isn't there at all.
3. Export those raw files, then `tools/update_from_hunter_export.py` parses them. A full raw-file
   export is ~2 million files / ~50GB, but every script in this repo only ever reads 3 folders
   under `hunter/game system data/juice/`: `item/`, `talent/`, and `itemgeneration/configs/` (NOT
   the rest of `itemgeneration/` — `configlinks/`/`attributelists/`/`talentlists/`/etc. are never
   read, except `itemgeneration/talentlists/` for the Chest/Backpack talent pool, see "All
   Talents" below). See "Updating the dataset" in `README.md` for the full breakdown (why each
   folder is needed, file counts) — export just these for a future run instead of everything.

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
  plain text; it has to be inferred by cross-matching known values against raw `myValue`s until a
  UID resolves with high confidence — see `tools/attribute_uid_dictionary.json`, persisted so this
  never has to happen again for a known attribute.
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
  checking for "back"/"chest" as a substring of *that file's own* instance id. Two more wrinkles:
  - The back-reference's case doesn't always match the 4pc file's own declared case — compare
    case-insensitively.
  - Some companions have no `myTalent` id at all, only a human-readable `myText` naming the
    talent — fall back to matching that against the 4pc talent's own display name.
- **Tooltip text contains `{0}`, `{1}`-style placeholders** filled from the talent's own
  `myBonusList` (ordered). Formatting is ambiguous from the raw data alone (percent vs. seconds vs.
  flat count can't be inferred mechanically) — this is the one part of the pipeline that still
  benefits from a human/AI read. The update script tracks a fingerprint of the raw values behind
  each talent description; if they haven't changed since last run, the hand-written text is kept
  untouched, so this only comes up for genuinely new/changed talents, not every run.
- **A talent tooltip can also inline a small core-attribute icon instead of spelling out the
  color** — `<img src="hunter/baked/ui/loose_images/ui_player_offense.dds">` and its
  `defense`/`utility` siblings, no other icon vocabulary exists anywhere in `talent/*.mtalent`.
  `strip_inline_markup` (shared by all extraction scripts) maps each icon to its color word
  (Red/Blue/Yellow, the same `CORE_COLOR_BY_STAT` convention used everywhere else) rather than
  just deleting the tag, since at least one occurrence uses the icon as a noun ("...for each
  `<img.../>` you have"), not a decorative prefix — deleting it outright would leave a
  grammatically broken sentence.
- **The raw text format itself has landmines**: brace-matching must be quote-aware. At least three
  of the game's own files (Negotiator's Dilemma, Striker's Battlegear, Hunter's Fury) have a
  literal `}` embedded inside a quoted string value, which silently truncates a naive brace-counter
  and drops everything after it. `extract_braced()` (shared) handles this; reuse it rather than
  re-deriving brace parsing from scratch.
- **Not every raw-file export is complete.** Some files are referenced by other files but simply
  absent from a given export (e.g. Ongoing Directive's backpack companion talent, still missing as
  of the fullest export used so far — confirmed by direct search, only `_5piece`/`_6piece`/`_chest`
  `.mtalent` files exist for it, no `_back` file at all). Every script preserves the last known-good
  value in that case (with a flagged warning) rather than deleting good data — don't "fix" that
  behavior into silently dropping fields.

### Self-embedding and text-extraction landmines (apply to all four extraction scripts)

Each script re-embeds its own minified JSON directly into `index.html`'s matching `const X = [...]`
line. This mechanism has bitten the project multiple times; the fixes below are load-bearing —
don't revert any of them for a "quick" edit:

- **The instance-id regex must tolerate subclass syntax.** `Talent <id> < uid=... > : <base_talent>
  { ... }` — a `: <base_talent>` clause between the uid and the opening brace — appears on most
  Perfect-tier talent files and silently broke a naive `Talent\s+(\S+)\s*<[^>]*>\s*\{` regex for
  all of them. Make the subclass clause optional: `(?:\s*:\s*\S+\s*)?` before the `\{`.
  Concretely, this was the real root cause of an early "35 named-item talents unresolvable"
  report that looked like an export gap but wasn't (see "Named Items" below).
- **A `text = ` field's quote-delimiter style varies by field, not by file.** Some use a
  backslash-escaped double quote (`text = \"...\"`), others a bare single quote (`text = '...'`,
  common on Perfect-tier `myUIName` fields) — `extract_localized_text`/`extract_marked_value` must
  handle both. A value that itself embeds a quoted `<color name="...">` attribute can get escaped
  *again* on top of that (`\\"` rather than a clean `\"`) — the working approach searches
  pragmatically for the known trailing marker (`, type` / `, enabled`) in whichever quote
  representation matches the opening, then unescapes both quote types in the captured span.
- **The `const X = [...]` embed-match must be scoped to a single line (`[^\n]*`), never
  `.*` with `re.DOTALL`.** All four consts are single-line minified-JSON declarations sitting one
  after another; a greedy `DOTALL` match starting at one `const X = [` matches through to the
  *last* `];` anywhere later in the file — i.e. straight through a different const's own closing
  bracket, silently deleting it. This actually happened to a committed `index.html` once (a
  `NAMED_ITEMS` count went from 2 to 0 after one run) before being caught and fixed.
- **Never pass the replacement JSON as a plain string to `re.sub`/`re.subn`.** The `re` module
  interprets backslash sequences (`\n`, `\g<...>`, etc.) in a *string* replacement the same way it
  would in a pattern. Item/talent text legitimately contains literal `\n` (e.g. a flavor-text
  signature line), which gets silently turned into a *real* embedded newline mid-JSON, corrupting
  the embed. Always pass a replacement **function** (`lambda m: new_line`) — its return value is
  inserted verbatim with no escape processing.
- **`naive_substitute`'s percent-vs-flat-number heuristic must peek at the template's next
  character before appending its own `%`.** Some Perfect-tier templates already end a placeholder
  with `%` (`"...by {0}%..."`); appending unconditionally produces `"7%%"`.

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
  (usually empty, a dead end) → the real `ItemGenerationConfig` block, which lives somewhere in
  `game system data/juice/itemgeneration/configs/configs_gear_<slot>_code1_data*.mitemgenerationconfigs`
  (~20 near-duplicate files per slot; just index every `ItemGenerationConfig` declaration once).
  **The declared config name's relationship to the item's own instance id is not consistent** —
  seen in the wild: `<item_id>_config`, `<item_id_minus_"_named">_config_named`, even one literal
  authoring typo merging tokens into `_namedconfig`. Don't guess a naming transform; instead
  match by **token multiset** — split both on `_`, lowercase, sort — since every real config name
  is exactly the item id's tokens plus one extra `config` token, in any order/position. Case can
  also mismatch entirely.
- **Inside that config**, under `myAttributeSlots → QualityAttributeSlots Orange → mySlots →
  ItemAttributeSlot`: a slot with `myPresetAttribute <uid>` **and a positive** `myPresetPercentage`
  is a guaranteed, always-maxed bonus (the `myIsNamedAttribute TRUE/FALSE` flag is inconsistent
  across items — key off `myPresetPercentage`'s *sign* instead: a **negative** value, seen as
  `-1.0`, is a sentinel for "this slot's preset isn't actually active here"; the all-zero UID is
  independently filtered as a null placeholder too). The `Core` slot (`myIsCoreAttribute TRUE`)
  also carries a `myPresetAttribute` but no percentage — that's the ordinary guaranteed core stat
  every item of that slot type has, not a named-only bonus; exclude it. **Gloves/Holster/
  Kneepads/Mask items get 1–2 fixed bonuses; Backpack/Chest items get none at all** — their named
  identity is purely a talent instead (`myAttributeSlots` is simply absent on those configs). This
  is a real game-design fact, not a data gap.
- **A unique talent**, when present, is `myTalentSlots → QualityTalentSlots Orange → mySlots →
  ItemTalentSlot → myPresetTalent < uid=... > = <slug> <guid>` — the FIRST token is the
  `.mtalent` file's own instance-id/slug to look the talent up by; the trailing hex GUID is
  captured but never used. **`QualityAttributeSlots`/`QualityTalentSlots`'s own instance label is
  not reliably the quality name** — many blocks use a generic editor-default label
  (`"New QualityTalentSlots (0)"`) even though their *contents* are the real Orange-tier block (a
  `myQuality Orange` field inside confirms it). Match every such block regardless of its own
  label, then filter by the `myQuality` field inside (see `_orange_quality_blocks`) — anchoring a
  regex on the literal label `Orange` silently finds nothing for these, indistinguishable from
  "genuinely no talent," a worse failure mode than a flagged `MISSING_TALENT`.
- **Do not try to derive a talent's real display name from `myPresetTalent`'s slug** when its
  `.mtalent` file is missing — checked directly against items whose real name is known via other
  means, the slug describes the underlying mechanic, not the flavor name, and bears no
  resemblance whatsoever (one slug containing "damage"/"status"/"increased" turned out to be
  "Perfectly Wicked"). A humanized guess would be actively misleading.
- **The exact numeric value behind a fixed attribute isn't resolvable from any export used so
  far.** The `AttributeListContainer` a preset attribute's UID belongs to (e.g. "NamedAttributes")
  is only a *reference*; the actual value lives in
  `itemgeneration/attributelists/*.mitemgenerationattributelists` as a **gear-score-dependent
  curve formula** (`ItemGenerationBracketedCurveFormula`), not a flat number — there is no single
  "the value" without first picking a target gear score to evaluate the curve at. A max-gear-score
  extraction attempt got as far as a formula (`topBracketC(myRangeMax's curve) × (myPresetPercentage
  / 100) × qualityModifier`) but only matched 2 of 6 real in-game values the user confirmed —
  `myPresetPercentage` values above 100 (seen: 145–900) clearly aren't a simple linear multiplier,
  and two ~1-point misses on otherwise-clean 100%-preset cases were unexplained too. Dropped
  rather than shipped a partially-wrong number; if revisited, start from "the modifier story is
  more complicated than `pct/100 × qualityModifier`" rather than re-deriving this from scratch.
  So this stays a deliberate, understood scope limit ("which stat, not how much") rather than an
  open bug.
- **`myUIName`/`myDescription` field parsing** needs the both-quote-styles handling described in
  the self-embedding landmines above. One item (The Hollow Man) also has a literal stray `\"`
  inside its name value in the source data itself (a dev typo) — strip any leftover quote
  character from the final cleaned name.
- **A handful of older (Y1-era) named items never got their real `myDescription` written** — its
  `text` field is literally the placeholder string `"INSERT TEXT HERE"`, and the actual
  drop-source/talent info lives only in that field's `contextComment` (an internal dev note under
  a different sub-key). Extract both; fall back to `contextComment` whenever `text` is empty or an
  obvious placeholder. Some `contextComment`s go further and spell out `Talent: <name>\n<description>`
  — a usable fallback for a talent whose `.mtalent` file is otherwise missing.
- **The same unfilled-placeholder problem can hit `myUIName` itself** — one item's raw `text` value
  was literally `INSERT NAME HERE` (its real name, "The Gift," hadn't synced into that export
  snapshot; no separate localization/string-table export exists to cross-reference). A genuine
  content gap in the source, not something parseable from data alone. Confirmed corrections like
  this go in `tools/named_items_manual_overrides.json` (instance_id → `{"name": ..., "note": ...}`),
  applied after parsing and logged as a `MANUAL_OVERRIDE` review note. The same file also supports
  a `talentName`/`talentNote` key for a talent that's otherwise fully unresolved (`.mtalent` file
  missing, no description fallback) — currently inert for every item since a fuller export (see
  "Session history" below) resolved all of them via datamining, but kept as a safety net if a
  future export ever regresses; the datamined path is always tried first.
- **Brand isn't always in `myGearBrand`** — items that subclass their own non-named base item
  often don't redeclare it. Fall back to the file's own top-of-file `include
  ".../gearbrand/gearbrand_<code>.mgearbrand"` line, which is present regardless of inheritance;
  join `<code>` (lowercased) against the Brand entries already in `data/combined_sets.json` by
  stripping their `gear_brand_set_` prefix.
- **Each Named Item also shows its civilian brand's normal 1pc/2pc/3pc bonuses** alongside its own
  Fixed attribute — e.g. Salvo (a Unit Alloys holster) surfaces under both its own Fixed "Rate of
  Fire" and Unit Alloys' brand bonuses (Assault Rifle Damage, Magazine Size). `build_named_items`
  takes a `brand_tiers` dict (brand code → the matching Brand entry's `tiers` list, sourced from
  `combined_sets.json`) and writes it to each item's `brandBonuses` field; `index.html` folds
  `fixedAttributes` (`pieces: null`) and `brandBonuses` (real piece count) into one `tiers` array
  so the existing chip-filter logic needs no change — the card renderer distinguishes them by
  `pieces === null` ("Fixed" label) vs. a real piece count.

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
Armor" as the real name from in-game knowledge.

Extraction (`parse_core_attributes` in `extract_named_items.py`, shared by all pipelines): scan
the item's own quality-tier `QualityAttributeSlots` block (Orange for named items, Exotic for
exotics, GearSet for gear sets — **do not** scan all quality tiers, see below for why) for every
`ItemAttributeSlot` with `myIsCoreAttribute TRUE`, resolve each one's `myPresetAttribute` UID,
dedupe by UID.

Landmines, each discovered the hard way:
- **A named item's Core UID can genuinely differ across quality tiers** (seen on Caesar's Guard
  and Henri). Named items are always Orange quality in practice, so only the Orange tier's value
  is meaningful — aggregating across all 4 tiers falsely looks like "this item has 2 cores."
- **Backpack/Chest named items' own dedicated config has no Core at all** (same "no fixed bonus
  either" fact — talent only, no `myAttributeSlots` block). This does NOT mean these items have no
  Core in-game — every item does. The real Core lives on the regular, non-named civilian-brand
  piece the item's model/identity is drawn from, reliably found by stripping `_named` out of the
  named item's own instance_id anywhere it occurs (not always a trailing suffix, e.g.
  `player_gear_back_g_named_02` → `player_gear_back_g_02` — a plain substring removal, not a
  suffix-anchored regex). This resolves strictly more cases than an earlier attempt that followed
  the item's own `: base_id` subclass declaration instead (that one sometimes subclassed the
  generic `player_gear_<slot>_template` even when a real, correctly-named base item existed).
  2 of 62 named items (Force Multiplier, Door-Kicker's Knock) can't be resolved even this way —
  their base item's own Core slot has no `myPresetAttribute` either, i.e. even the regular,
  non-named drop rolls a random core — so those two are confirmed instead from the user's own
  in-game knowledge (Yellow, Red) via `named_items_manual_overrides.json`'s `core`/`coreNote` keys,
  a last-resort fallback after both datamined attempts come up empty.
- **A screenshot of an item's Core in-game isn't necessarily its default (datamined) Core.**
  Division 2 lets players recalibrate an item's Core after acquisition — one screenshot the user
  first cited as ground truth turned out to show a recalibrated copy, and the datamined answer was
  right all along once this was realized. Worth asking specifically "on an unmodified,
  un-recalibrated copy" when confirming this stat in-game, not just "what does it show now."
- **`myPresetPercentage`'s sign does NOT reliably distinguish an active core from a decoy** on
  multi-slot exotics, unlike its role on regular (non-core) attribute slots. A few exotic
  Backpacks (Memento, and — same data shape, not independently confirmed — Harrier Pride and Ninja
  Bike Messenger Bag) declare all 3 `myIsCoreAttribute TRUE` slots simultaneously, with percentages
  that don't follow the usual "-1.0 = inactive" convention (Memento's real, always-active Total
  Armor slot is itself marked -1.0). Confirmed in-game: these items genuinely support all three
  cores at once, a real design quirk. `parse_core_attributes` therefore treats **every**
  `myIsCoreAttribute TRUE` slot as active regardless of its percentage — deliberately different
  from how regular attribute slots are filtered.

**Gear Sets** (Striker's Battlegear, Foundry Bulwark, etc.) also have a Core per piece
(`tools/update_from_hunter_export.py`'s `parse_gearset_items` + `parse_gearset_cores`; Brand
entries deliberately do NOT get a `cores` field, since a civilian brand spans many different items
with no single fixed Core):
- **A Gear Set's 6 pieces are `myQuality GearSet`, not `Orange`** — passing `quality="GearSet"` to
  `parse_core_attributes` is the whole fix; without it every piece silently resolves to zero cores.
- **A Gear Set's own `.mgearset` file lists its 6 concrete pieces directly** (`myItems { Item Mask
  = player_gear_set_j_mask_01 <guid>; ... }`) — one clean slot→instance_id map, no fragile
  naming-convention guessing needed.
- **24 of 27 Gear Sets share one single Core across all 6 pieces** (confirmed correct in-game by
  the user for Striker's Battlegear = Red, Foundry Bulwark = Blue); 3 are real exceptions:
  **Refactor** and **System Corruption** each genuinely split two different Cores across their
  pieces (every piece's own Core slot has an explicit, non-random preset, just not the same one),
  and **Core Strength** is a deliberately flexible set — its own 4-piece talent text says so
  directly ("All pieces except the Backpack feature random Cores"), and the data matches: 5 of 6
  pieces carry the null-UID "not preset" sentinel while its Backpack alone declares all three
  cores active, the same "flexible core" pattern as the exotic Backpacks above.
  `parse_gearset_cores` returns the **union of every Core resolved across all 6 pieces**, deduped
  by color — this reduces to the single common case for 24/27 sets and reads correctly for the 3
  exceptions too, without fabricating one answer that isn't real for them.
- **Circular import note**: `parse_gearset_cores` needs `find_generation_config_block` and
  `parse_core_attributes` from `extract_named_items.py`, which already imports FROM
  `update_from_hunter_export.py` at its own top level — the import is deferred inside
  `parse_gearset_cores` itself (function-local) to avoid a real cycle.

## Exotic Items — datamining notes

Distinct item category from Named Items: gear whose *unique talent* never appears on any Brand
Set, Gear Set, or Named Item, and which usually carries exactly two guaranteed bonus **types** (not
values — the roll is always random by design, unlike a Named Item's guaranteed-max Fixed
attribute). `tools/extract_exotic_items.py` reuses almost all of `extract_named_items.py`'s
parsing machinery directly (imported, not copied) — the schema turned out to be nearly identical:

- **Item files**: `game system data/juice/item/player_gear_*exotic*.mitem` (no `_named`
  requirement in the glob — exotics use their own naming). Same `blueprint_*`/`_aprilfools`
  exclusions as Named Items. `parse_named_item_file` parses these with **no changes needed** — slot
  detection, name/description extraction, and DZ-tag detection all just work. The one field that
  must be **ignored**: `parse_named_item_file`'s brand-fallback logic picks up unrelated
  shared-asset includes for exotics (e.g. Catharsis's file includes a gearbrand file that isn't
  actually Catharsis's brand) — exotics don't have a civilian brand at all.
- **Config lookup**: same token-multiset matching as Named Items, unchanged — exotics' real
  configs live in the same `itemgeneration/configs/` directory, whose index globs the whole
  directory flatly (so the dedicated `configs_exotics_code1_data*` family is always included
  automatically). This family matters for exotics whose own `.mitem` file is missing from the
  export entirely, since their config exists *only* there — see "Potential Bonuses" below for what
  that means for `extract_all_talents.py`'s own exotic-talent classification.
- **Talent**: exactly one `ItemTalentSlot` under `QualityTalentSlots Exotic` (not `Orange`) —
  `parse_preset_talent`/`_quality_blocks` both take a `quality` parameter for this.
- **Bonus slots**: `ItemAttributeSlot`s (excluding the Core one) with a `myPresetAttribute` —
  reuses `parse_preset_attributes(config_body, quality="Exotic")`, but **deliberately does not
  check `has_preset_percentage`** the way Named Items' Fixed-attribute extraction does: an
  exotic's guaranteed bonus slot never carries `myPresetPercentage` at all (nothing to gate on —
  the type is fixed, the value stays random). Only the null/placeholder-UID sentinel is filtered.
- **Core**: `parse_core_attributes(config_body, uid_dict, quality="Exotic")` — see "Core attribute"
  above, this is where the "not everything follows the percentage-sign convention" and "some items
  have several simultaneously" complications were found.
- **Excluded/special-cased items** (none guessed at, all structurally detected or user-confirmed):
  - `player_gear_gloves_exotic_02` ("Rathbone's Gloves") — `myItemGenerationConfig` is a literal
    `NULLREFERENCE`. Detected automatically (`find_generation_config_block` returns `None`); unlike
    Named Items, where a missing config so far has always meant "real item, file just isn't in the
    export" and the item is still included, Exotics **skip the item entirely** here, since this is
    a dead, unfinished item, not an export gap.
  - `player_gear_kneepads_exotic_04` — `myUIName`'s `text` is literally `"TBD"`. Caught by a
    placeholder-name check, but only after fixing a real bug where the shared `extract_field_text`
    helper's contextComment-fallback (meant for `myDescription`) was also applying to `myUIName`,
    silently replacing "TBD" with an internal editor label before the placeholder check could ever
    see the raw value. Fixed with an `allow_comment_fallback` parameter, `False` for `myUIName`.
  - `player_gear_mask_exotic_06` ("Investor") — a real, released item confirmed by the user via its
    own talent text ("Slotted") to be intentionally fully-random: any Core, a third random
    attribute instead of a mod slot. Included (not excluded) since its Core/bonus slots all
    genuinely carry this dataset's usual null-UID "not preset" sentinel — confirmed structurally,
    not fabricated — so `bonuses: []`/`cores: []` is an honest answer here. `CONFIRMED_RANDOM_
    BONUS_ITEMS` suppresses the normal "missing data" review-note for this item's null-UID slots
    specifically, and a `bonusesRandom: true` field drives an explicit "confirmed fully random"
    note in the UI instead of the "not yet resolved" language used for a genuine gap.
  - `player_gear_back_exotic_01` ("Acosta's Go Bag") — has no `.mitem` file in any export used so
    far (only its crafting-recipe blueprint survives), but its `ItemGenerationConfig` is complete:
    two bonus slots, a Core, and **two** simultaneous `myPresetTalent` entries ("One in Hand..."
    and "...Two in the Bag" — a "bird in hand" wordplay pairing). Reconstructed via
    `build_manual_config_items()` from `tools/exotic_items_manual_additions.json`, which supplies
    only the name/DZ-flag (the two facts the config itself can never provide) and takes bonuses/
    cores/every preset talent straight from the config. Schema addition: `extraTalents` (empty for
    every other item) holds any talent beyond the primary `talent`/`talentId` pair; `index.html`
    folds each extra talent's `potentialBonuses` into the item's `potentialTiers` the same way.
  - A sibling case remains only partially resolved: `talent_exotic_kneepads_mk1_a` ("Grace Under
    Fire") is confirmed real the same way (its own config exists, its own `.mitem` doesn't) but
    hasn't had its owning item's name confirmed in-game yet — would take exactly one entry in
    `exotic_items_manual_additions.json` once it is.
- **Two more bugs surfaced by exotic-item flavor/description text specifically**, both fixed in
  shared code (`update_from_hunter_export.py`):
  - `extract_braced`'s quote-tracking desynced on text containing an apostrophe combined with a
    nested `\\"..."` escape (one level deeper than the common case) — read as closing the *outer*
    field's string early, then everything after silently miscounted braces. Since no field in this
    format legitimately spans multiple lines, the fix resets quote-tracking state at every newline
    rather than modeling arbitrarily-nested escaping.
  - `naive_substitute`'s percent-formatting heuristic and the talent-tooltip parser had two more
    quote/escape gaps of the same family as the self-embedding landmines above — consolidated to
    reuse `extract_localized_text` instead of maintaining a third copy of the same logic.

## All Talents — the "Talent Browser" tab

A second view within the same page (`index.html`'s view-tabs — no second HTML page, just two
`<div>`s toggled by JS) covering every weapon/gear Talent, not just the ones already reachable by
following a reference from a Brand/Gear Set/Named/Exotic Item. `tools/extract_all_talents.py`
walks *every* `.mtalent` file in the export (~770 as of the fullest export used so far) and
classifies each one, rather than being handed a specific instance_id to look up — a fundamentally
different traversal from the other three pipelines, all of which start from a known reference and
resolve outward.

- **Output**: `data/all_talents.json`/`_min.json`, embedded as `ALL_TALENTS` (same self-embedding
  landmines as the other two scripts, see above). **Schema per talent**: `{id, name, description,
  kind, slot, weaponType, tier}`. `kind` is one of `gear` / `weapon` / `exotic-gear` /
  `exotic-weapon` / `exotic-other` / `other`. `slot` and `weaponType` are mutually exclusive but
  `slot` can itself be a `" / "`-joined pair (currently only `"Backpack / Chest"`, confirmed via
  the pool data below). `tier` is `"Perfect"` when the instance id ends `_perfect`, else
  `"Standard"`. Current total: 352 talents (`gear`: 93, `weapon`: 113, `exotic-gear`: 40,
  `exotic-weapon`: 48, `exotic-other`: 13, `other`: 45).
- **A non-Exotic item only ever rolls a Talent on Chest or Backpack — never Mask/Gloves/Holster/
  Kneepads.** Confirmed both by the user's in-game knowledge and structurally: every
  `configs_gear_mask_*`/`gloves_*`/`holster_*`/`kneepads_*` file's own base `ItemGenerationConfig`
  has a completely empty `myTalentSlots {}` block, while `ChestBase`/`BackPackBase` populate
  theirs — matching this codebase's Named Items finding (those 4 slots get a Fixed attribute
  instead) and extending it to regular/civilian gear too. Talent files literally named
  `talent_mask_*`/`talent_gloves_*`/etc. with real names do exist in the export (50+) — they're
  leftover/legacy data, not real obtainable content, and are excluded rather than shown on a slot
  that can't roll them.
- **The authoritative source for "which talents actually roll on Chest vs. Backpack" is the
  game's own random-roll talent-pool data, not the talent's own filename slot token — which is
  frequently wrong or absent entirely** (e.g. Headhunter, Chest-only, filed with no slot token at
  all; Tag Team, also Chest-only, filed under a `mask` token). The real per-slot pool lives at: a
  Chest/Backpack item's `ItemGenerationConfig` → `myTalentSlots` → `QualityTalentSlots` →
  `ItemTalentSlot` → `myPossibleTalentLists` → a `TalentListContainer` *reference* (e.g.
  `= warlock_chest_talents <guid>`), whose actual body — a flat list of `Talent "label" =
  <instance_id> <guid>` entries — lives in a **separate directory**,
  `itemgeneration/talentlists/*.mitemgenerationtalentlists`. `build_gear_talent_pools` unions
  every `Talent = <id>` entry across every declaration of the real container names actually
  referenced by live Chest/Backpack configs (grepped directly from those configs' own
  `myTalentSlots`, not guessed) — the same "many near-duplicate files, index every declaration"
  pattern as `configs/`. This pool override runs for every non-exotic talent and **only ever adds
  or corrects a slot, never removes one an item actually confirms** — a named item's own preset
  talent (e.g. Festive Delivery's Fireworks Show) doesn't need to appear in the random-roll pool
  at all, since it's assigned directly via `myPresetTalent`, a separate mechanism; absence from
  the pool only means "not obtainable via random roll," narrower than "not a real talent."
  - A `talentlist_dev_testing_only_*` family also exists, with plausible-looking containers and
    real-sounding talent names (Aegis, Second Primary Weapon) — but no real Chest/Backpack config
    ever references these containers. Deliberately excluded from the pool query rather than
    trusted, even though some contents might be genuine — no structural way to tell otherwise.
- **Exclusions** (`EXCLUDE_PREFIXES`), each checked by hand against real file content, not guessed:
  `talent_gearset_*` (already covered by `combined_sets.json`), `talent_specialization_*`/
  `specialization_*` (skill tree, different system), `warlock_skill_talent_*` (Skill Tier 7
  unlocks, tied to a skill not equipped gear), `dz_*` (Dark Zone rank perks, account-level),
  `boo_*` (battle-pass rewards), `test*` (literal test data), `talent_watch_*` (a cut "Watch" gear
  slot that never shipped), `talent_sd_*` (a Dungeon Arena roguelike-mode pool, confirmed via
  `contextComment`, not obtainable on regular gear), `talent_augment_*` (Skill Augments, a
  distinct equip system), placeholder/unfilled names (6 files), and files with no usable
  description after `naive_substitute` (5 files).
- **Classification (`classify_talent`)**: strips a known prefix alias first (`virginia_talent_exotic_`,
  `warlock_talent_exotic_`, `talent_exotic_`, `talent_gear_`, `warlock_talent_`, `talent_`, tried
  longest/most-specific first — `warlock_`/`virginia_` are internal dev codenames that can prefix
  an otherwise-normal `talent_exotic_`/`talent_gear_` id), then matches an ordered list of
  gear-slot/weapon-type prefixes (longest-match-first). This is only the *first pass* for
  non-exotic gear — the pool override above runs afterward and is authoritative whenever it finds
  a match. No match at all → `kind: "other"` (a real, in-scope talent not restricted to one
  slot/weapon, e.g. `talent_basic_*`/`talent_slot_*` universal weapon-stat talents). One hardcoded
  special case: `ninja_backpack_talent_exotic` has no recognizable prefix structure at all.
- **Exotic gear talents whose filename carries no slot token at all** (e.g. Tinkerer mask's talent
  is `talent_exotic_abridged`, no `mask` token) are resolved by inverting the Named/Exotic Item
  talent-resolution path: walk every exotic armor `.mitem` file, resolve each one's own preset
  Exotic-tier talent, and invert into `{talent_id: slot}` (`build_exotic_gear_talent_slots`). A
  second, independent source (`build_exotic_gear_talent_slots_from_configs`) does the same by
  walking every `ItemGenerationConfig` declaration directly instead of requiring the `.mitem` file
  — this is what resolves a talent like Acosta's Go Bag's even when its owning item file is
  missing (see "Exotic Items" above), and (unlike `parse_preset_talent`, which only returns the
  first match) collects every `myPresetTalent` per config, since one config can assign more than
  one. Both cross-references run **universally, first, for every kind** — not only ones
  `classify_talent` already suspected were exotic — because one real talent (Collector's own
  "Hoarder") had no exotic-style filename token at all and was silently misclassified as a
  generic, any-brand-rollable `gear` talent until this ran unconditionally.
- **A bare `weapon` filename token on an exotic talent does NOT mean "Any Weapon."** Unlike the
  real universal weapon-talent pool (`talent_weapon_*`, genuinely droppable on any weapon), an
  exotic weapon's talent is always tied to exactly one specific gun — `EXOTIC_WEAPON_PREFIXES` (a
  copy of `WEAPON_PREFIXES` with the generic "Any Weapon" entry removed) is used for the exotic
  path instead; an unrecognized token there falls through to the item cross-reference, then
  `kind: "exotic-other"` (both `slot`/`weaponType` null) rather than mislabeling a dozen real
  exotic weapons' talents as usable on any weapon.
- **Known limitation, accepted rather than solved**: `naive_substitute`'s percent-vs-flat-number
  heuristic is applied to all included talents' description text with no per-talent manual review
  the way gear-set talents get — occasionally produces a wrong-looking value (e.g. a 3-second
  duration rendered as `300%`) since a value's type genuinely can't be inferred from the raw number
  alone. Flagged in the page's own "About the Talent Browser" note.
- **Weapon-side talent-pool liveness checking has never been attempted** — this tool has no weapon
  `.mitem` parsing at all, and a quick investigation found weapon items have their own per-model
  talent-slot data but in a meaningfully different, unproven shape (a base weapon config assigns
  one `myPresetTalent` directly at Orange quality, with Blue/Purple quality referencing a shared,
  not-yet-traced template) — left as a distinct, dedicated follow-up. `kind: "other"` is labeled
  "Legacy / Removed" in the UI on the user's own observation that it looks like cut content, but
  that's not independently structurally verified the way Chest/Backpack liveness now is (see
  "Potential Bonuses" below) — the page's own note says so explicitly.

## Potential Bonuses — inferred conditional attributes (Talent Browser, Part 2)

A talent's tooltip text often grants a real bonus attribute (Weapon Damage, Skill Damage, Bonus
Armor, ...) *conditionally* — e.g. Composure: "increases total weapon damage by 15% while in
cover." Since no script can reliably map free-form flavor text to a named attribute + trigger
condition, this is a judgment call done **once**, by hand (an AI read every gear-slotted talent's
description and classified it), persisted in `tools/talent_bonus_inferences.json` — the same
"persist the one-time judgment call, let the script only ever check for drift" pattern as
`attribute_uid_dictionary.json` and `named_items_manual_overrides.json`. The script only ever
*points out* new/changed talents for a future interpretation pass; it never re-derives the
interpretation itself.

- **Schema**: `{talent_id: {"fingerprint": md5(description), "bonuses": [{"attribute",
  "condition"}, ...]}}`. `bonuses: []` is a real, meaningful answer — "reviewed, genuinely grants
  nothing mappable to a named attribute" (e.g. a pure unlock, or a proc with no clean stat
  equivalent like a stun immunity) — distinct from "not yet reviewed" (id absent from the
  dictionary). `condition` is a short human-readable trigger description, not a parseable format.
- **Scope: `kind` in `{gear, exotic-gear}` only** (133 talents, after excluding 5 confirmed-dead
  ones — see below), not all 352. This mirrors the Attribute Finder's own scope: it only answers
  "which gear should I equip for bonus X," and this tool tracks no weapons, so a weapon-side
  talent's potential bonus has no "equip this" answer to attach it to.
- **Attribute vocabulary**: reuses the exact names in `attribute_uid_dictionary.json` wherever a
  talent's wording matches a real guaranteed-bonus stat, but isn't limited to that vocabulary —
  talents also introduce their own new-but-consistent names for mechanics no Brand/Gear Set/Named/
  Exotic Item ever grants as a guaranteed roll: `Amplified Damage` (kept separate from `Weapon
  Damage`/`Skill Damage` whenever a tooltip says "amplifies," since the game treats it as a
  distinct calculation layer), `Bonus Armor` (temporary overshield procs, kept separate from
  `Armor Regeneration`, which is reserved for talents that literally repair a % of armor —
  different mechanics that just sound similar), `Damage Resistance`, `Movement Speed`, `Grenade
  Damage`/`Radius`/`Capacity`, `Armor Kit Capacity`, `Revive Speed`. The same name is deliberately
  reused across every talent describing the same effect so a future cross-reference can group them.
- **Unconditional talent-granted bonuses are still recorded**, with `condition: "Always active"` —
  a handful of talents (mostly exotics, e.g. "...Two in the Bag": +1 Armor Kit Capacity, +3 Grenade
  Capacity, +25% Ammo Capacity, etc.) grant a flat, guaranteed stat purely through their talent
  text, the same way a Named Item's Fixed attribute slot does, and are worth surfacing even with no
  everyday "condition." (The Armor Kit/Grenade Capacity numbers here were corrected 2026-08-27 —
  see the `naive_substitute` bug note above; they used to incorrectly show as +100%/+300%.)
- **Drift detection**: `apply_bonus_inferences()` hashes each in-scope talent's *current*
  description and compares against the stored fingerprint. A mismatch (rebalance changed the
  wording) or missing id (new talent) means the persisted `bonuses` are stale/absent — flagged in
  `tools/all_talents_report.md`'s "Potential-bonus inference coverage" section, and no
  `potentialBonuses` field is attached until re-interpreted. Never auto-edited, only read/diffed.
- **UI**: each Talent Browser card with a non-empty `potentialBonuses` array gets a "Potential
  Bonuses (Conditional)" block (distinct dashed divider, cyan `--accent2` — deliberately different
  from the orange `--accent` used for a confirmed/guaranteed match, so the two can't be confused
  at a glance).
- **Wired into the main Attribute Finder tab**: an Exotic Item's own talent(s) fold their
  `potentialBonuses` into `potentialTiers` on that item's existing card (via `TALENT_BY_ID`, an
  id → `ALL_TALENTS` entry map, looked up by each item's `talentId`/`extraTalents`). Any
  gear-slotted talent not tied to one specific item — generic Chest/Backpack talents rollable on
  any brand, plus any `exotic-gear` talent with no matching `EXOTIC_ITEMS` entry — gets its own
  standalone result card (`GENERIC_TALENT_ENTRIES`, `kind: "Talent"`), styled like a Talent
  Browser card. `ALL_STATS` (the chip list) and the ANY/ALL matching logic both fold in
  `potentialTiers` alongside `tiers`, so a stat that only ever comes from a conditional talent
  effect (`Amplified Damage`, `Armor Kit Capacity`, ...) is still selectable and matches correctly.
- **Liveness filtering**: the user's general rule — don't surface anything not currently used in
  the game — applied to the gear side (weapon-side talents are a separate, deferred question, see
  "All Talents" above). Two real categories of gear-scoped talent needed resolving beyond the
  random-roll-pool/Named-Item-preset checks already covered above:
  - **5 confirmed-dead `gear`-kind talents are excluded outright**: Aegis, Lazarus, Patched,
    Second Primary Weapon, Selfless — checked against both the live random-roll pool and every
    Named Item's own preset talent (the two structural ways a Chest/Backpack talent is actually
    obtainable) and matched neither. Independently corroborated: Aegis and Second Primary Weapon's
    names appear verbatim in the `dev_testing_backpack_talents`/`dev_testing_chest_talents`
    containers already confirmed never referenced by any real config (see "All Talents" above) —
    two separate pieces of archaeology agreeing. `talent_bonus_inferences.json` keeps its
    now-orphaned entries for these rather than deleting them, ready to reapply if a patch revives
    any of them.
  - **`exotic-gear` talents with no matching `EXOTIC_ITEMS` entry** split into three real
    categories, not one: (a) confirmed real via their own `ItemGenerationConfig` and now fully
    resolved into an item — Acosta's Go Bag (2 talents), via `exotic_items_manual_additions.json`;
    (b) confirmed real the same way but not yet name-confirmed — Grace Under Fire (kneepads); (c)
    belong to an item already known and excluded for unrelated reasons — Ostracize (the "TBD"
    kneepad) and Slotted (Investor, now included instead, see "Exotic Items" above); (d) genuinely
    unconfirmed — 7 talents (gloves/holster/kneepads `mk1_b`/`mk1_c` variants,
    `virginia_talent_exotic_mask_byzantine_inferno_wrath`) that only ever appear as a same-file
    `include` line across the `configs_exotics_*` shards, never as an actual `myPresetTalent`
    assignment anywhere — the one structural signal that distinguishes a real-but-unnamed item
    from a talent truly never wired to anything. Only category (d) is accurately "legacy/likely
    unused."

## Data provenance / licensing

The dataset was originally bootstrapped from two community sources before being replaced by direct
datamining: [mx-division-builds](https://github.com/mxswat/mx-division-builds) (CC BY-NC-SA 4.0)
and [The Division Wiki](https://thedivision.fandom.com/). Because of that lineage, treat
`data/*.json` (and the copy embedded in `index.html`) as non-commercial/share-alike/attribution
content, distinct from the tool's own MIT-licensed code — see `LICENSE` and `README.md`.

## Environment notes (Windows-specific gotchas)

- Bash tool here is Git Bash; `python3`/`node` aren't on `PATH`. Windows Python is at
  `C:\Users\mario\AppData\Local\Programs\Python\Python311\python.exe` — call it by full path.
  When passing paths *into* a Python script string, use Windows style (`C:\...` / raw strings);
  the Bash tool's own commands use POSIX style (`/c/...`) — don't mix them up.
- `gh` (GitHub CLI) isn't on `PATH` either; it's at `C:\Program Files\GitHub CLI\gh.exe`.
- Windows console is cp1252 — printing non-ASCII (e.g. "Česká Výroba") from Python crashes with
  `UnicodeEncodeError`. Write results to UTF-8 files instead of `print()`-ing them when they might
  contain non-ASCII.

## Current state

65 Brand Set / Gear Set entries (37 Brand Sets, 28 Gear Sets — Ember Engine added in the 2026-08-27
rebalance), 66 Named Items (47 with a unique talent, all fully datamined name + description; Keeper,
Melon Baller, Rushdown, and Trick Shot added in the same update), 31 Exotic Items (29 via the normal
per-item pipeline — Iron Will added in the same update — plus Acosta's Go Bag and Investor via the
manual-reconstruction paths described above), and 359 catalogued Talents in the Talent Browser (136
of them gear-slotted and interpreted for conditional/potential bonuses). No known data gaps remain
except: Ongoing Directive's backpack companion talent (`.mtalent` file missing from every export so
far), Grace Under Fire's owning item name (confirmed real, not yet name-confirmed in-game), and 7
genuinely-unconfirmed exotic-gear talent variants (see "Potential Bonuses" above) — all flagged
in-page rather than guessed at.

### `naive_substitute`'s percent-vs-flat heuristic — a real, partially-fixed bug (2026-08-27)

`naive_substitute` (shared by all four extraction scripts) decides whether a `{n}` placeholder's
`myValue` should be formatted as a percent (`v*100`, e.g. `0.35` → `"35%"`) purely from the value's
own **magnitude** (`abs(v) < 5`), not from anything in the template itself. This silently breaks on
any talent whose {n} is a genuinely small flat number rather than a fraction-of-one — a duration
under 5 seconds (`2.0` → wrongly `"200%"`), a small stack/kill/mark count (`3.0` → wrongly `"300%"`),
a small distance in meters, etc. — because those also satisfy `abs(v) < 5`. This turned out to be a
long-standing bug, not something the 2026-08-27 update introduced: **~70 pre-existing talent
descriptions had this wrong before this session**, most invisibly (e.g. Rushdown's "Perfect Tag
Team" showed `"Cooldown: 400%s"` instead of `"Cooldown: 4s"`; Adrenaline Rush's stack cap showed
`"300%"` instead of `"3"`). This session hand-fixed every instance found — see `git log` for the
2026-08-27 commit — using the following, more reliable signal instead: **does the template have a
literal `%` character right after the placeholder** (skipping any `</color>` tag in between, and
allowing for a `{a}-{b}%` range where only the trailing `{b}` carries the visible `%`)? If yes,
format as percent (still gated on `abs(v) < 5`, to avoid re-breaking a talent like Autentico's
`"+{0}% Weapon Damage"` where `{0}` is *already* a whole percent number, `35.0`, not a fraction);
if no, format as a raw number.

**This new rule is not itself airtight** — a handful of confirmed exceptions where the template has
*no* `%` marker at all but the value still needed `*100` to read sensibly were found and hand-fixed
individually (not via the rule): Empathic Resolve's buff duration, Kinetic Momentum's stack cap
(base *and* Perfect), Breathe Free's stack cap, Gangland Hit's mark cap. Conversely, two talents
were found where the template has *no* `%` marker for a value that plausibly should still read as a
percent (Combat Medic's "Damage Resistance", Symbiosis's shield-repair share) but the correct
answer couldn't be confirmed either way — left as literal flat numbers (the template's own literal
reading), flagged here rather than guessed. One raw-data typo was also found and hand-fixed:
`talent_back_skill_kills_increase_skill_duration_and_damage` ("Tech Support")'s own tooltip reuses
`{0}` for both its percent *and* its duration placeholder (should be `{0}%`/`{1}s`) — confirmed via
the file's own `contextComment` and cross-checked against Percussive Maintenance's "Perfect Tech
Support" (a different, correctly-templated file) landing on the same ballpark duration.
**`naive_substitute` itself was deliberately left unpatched** — the exceptions above make "template
has an adjacent `%`" not a fully general rule either, and this class of ambiguity is exactly what
the "Known limitation, accepted rather than solved" note (Talent Browser section, above) already
describes as needing human judgment per-talent rather than a better one-size-fits-all heuristic. A
future session re-running any of the four extraction scripts will regenerate every touched talent's
description **from scratch** with the *original* buggy heuristic (none of the four scripts have a
"keep hand-reviewed text" fingerprint mechanism for talent descriptions the way gear-set 4pc/
companion talents do in `combined_sets.json` — named/exotic/all-talents descriptions are always
freshly regenerated) — re-apply this same review pass (or equivalent hand fixes) afterward rather
than assuming today's fixes persist across a future run.

### Ember Engine's "Flashpoint" (chest) looks backwards from its own patch notes — likely a real game bug, left as-is (2026-08-27)

Ember Engine's base 4pc talent "Spontaneous Combustion" and its Chest talent "Flashpoint" both come
from the raw files with an internally-consistent set of numbers that nonetheless read as backwards:
the 4pc's own `myBonusList` sets `burn_chance` to `0.4` (40%), while Flashpoint's own `myBonusList`
sets the *same* attribute UID to `0.2` (20%) — and Flashpoint's own tooltip literally reads "Increase
the chance of applying Burn of Spontaneous Combustion to {0}%," i.e. an *upgrade* piece that actually
lowers the proc chance from 40% to 20%. The user found the official patch notes for this set, which
state the intended design as the reverse — 20% base, 40% via Flashpoint — matching neither number's
*position* in our data but confirming the *values themselves* (20/40) are the right pair, just
seemingly swapped between the two talent files in what actually shipped.

This was checked directly against the raw `.mtalent` file bytes (not just the extracted JSON) and
confirmed **not** a parsing/extraction bug on this project's side — `talent_gearset_
spontaneous_combustion_4pc`'s own `myBonusList` really does contain `0.4`, and `talent_gearset_
spontaneous_combustion_chest`'s own `myBonusList` really does contain `0.2`, for the identical
attribute UID (`EACD811D6A622A8400037D4A2609EF8E`). Given a chest-slot "upgrade" that's a strict
downgrade would make the piece actively harmful to equip, this looks like the developers swapped the
two `myValue` fields when implementing the set — a bug in the shipped game data, not in its design
intent. **Deliberately left un-"fixed" here** (per the user, 2026-08-27) since this tool's job is to
reflect what's actually live in the game, and Massive is likely to patch this themselves soon — if a
future rebalance changes these two specific values, treat it as this bug being fixed upstream rather
than a normal balance pass, and this note can be retired once that happens.

## Session history

Condensed changelog — see the topical sections above for full technical detail on any of these.

- Replaced the original community-sourced dataset with direct datamining from the game's own
  files; reached full Brand/Gear Set coverage (64 entries) with no known gaps.
- Added Named Items (62), then their civilian-brand bonuses (`brandBonuses`), then closed the
  "35 items' unique talent unresolvable" gap down to zero by fixing four real parsing bugs (the
  Perfect-tier subclass-syntax regex, a quote-delimiter-style gap, a greedy self-embed regex that
  was silently corrupting `NAMED_ITEMS` on every run, and a `re.sub` backslash-escaping bug that
  corrupted embedded text containing literal `\n`) — see "Self-embedding landmines" above. A
  fuller Hunter export was the trigger; the gap was never actually a missing-file problem.
- Added the Core attribute for Named/Exotic Items, then Gear Sets; fixed a real bug where 19
  Backpack/Chest named items showed no Core at all (the base-item Core-inheritance logic wasn't
  wired up yet), and a card-layout bug where long Core badges could overflow and hide behind a
  neighboring card (fixed by stacking badges in a column).
- Added Exotic Items (28 initially) with Fixed bonus types + unique talent, and a Red/Blue/Yellow
  Core filter row.
- Added the Talent Browser tab (full weapon/gear Talent catalog) — three rounds of user-caught
  classification bugs before the Chest/Backpack slot assignment was trusted (filename-based
  guessing was frequently wrong; switched to the game's own random-roll talent-pool data).
- Added inferred conditional ("potential") bonus attributes for gear-slotted talents, wired into
  both tabs. This surfaced and fixed a real misclassification (Collector's own talent, "Hoarder",
  was showing as generically rollable), excluded 5 confirmed-dead talents, and — via two rounds of
  the user spotting an orphaned talent with no matching item card and asking about it directly —
  recovered Acosta's Go Bag (a real item missing only its `.mitem` file, reconstructed from its
  config) and un-excluded Investor (confirmed genuinely fully-random rather than an export gap).
  Exotic Items: 28 → 30.
- Fixed a broken inline `<img>` core-attribute icon tag rendering as raw HTML in 4 talent
  descriptions (the shared markup-stripping helper only handled `<color>` tags before this).
- Ran a full rescan against the 2026-08-27 game update (a major itemization rebalance): re-ran all
  four extraction scripts in order, resolved one new attribute UID (`Defence from Elites`), picked
  up 1 new Gear Set (Ember Engine), 4 new Named Items (Keeper, Melon Baller, Rushdown, Trick Shot),
  and 1 new Exotic Item (Iron Will). While reviewing the auto-drafted talent text this triggered,
  found and fixed `naive_substitute`'s percent-vs-flat formatting bug — see the dedicated note under
  "Current state" above — both in the ~25 talents the update itself touched and, once the pattern
  was recognized, in ~70 more pre-existing talent descriptions across all four datasets that had
  been silently wrong since long before this session (durations/counts showing as absurd 3-digit
  percentages, e.g. `"Cooldown: 400%s"` instead of `"Cooldown: 4s"`). Also caught and fixed one
  raw-game-data authoring typo (Tech Support's tooltip reuses `{0}` for two different placeholders)
  and one index-misalignment bug (Overflowing/Perfectly Overflowing's tooltip references `{1}`/`{2}`
  but the first `BonusAttributeRef` in its `myBonusList` has no `myValue` at all, shifting every
  later index down by one).
