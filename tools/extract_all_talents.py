"""
Extract every weapon/gear Talent from a Hunter "raw files" export and write
data/all_talents.json (+ min copy) -- the full talent catalog for the page's "Talent Browser"
view. Distinct from update_from_hunter_export.py (Brand/Gear Set 4pc+companion talents only) and
extract_named_items.py/extract_exotic_items.py (a single item's own unique talent only): this
script walks *every* .mtalent file and classifies it, rather than following a reference from a
gear-set/item file. See CLAUDE.md's "All Talents" section for the taxonomy this encodes.

Usage:
    python tools/extract_all_talents.py --raw-dir "E:\\Temp\\Hunter\\raw_files\\hunter"

Never commits/pushes anything. Review tools/all_talents_report.md and data/all_talents.json
yourself before trusting the embedded result.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from update_from_hunter_export import parse_mtalent_file, naive_substitute, extract_braced  # noqa: E402
from extract_named_items import (  # noqa: E402
    strip_inline_markup, SLOT_MAP, parse_named_item_file,
    find_generation_config_block, parse_preset_talent, _index_generation_configs,
    _load_config_body, _quality_blocks,
)


# The container names actually referenced by the live Chest/Backpack ItemGenerationConfig's own
# myTalentSlots block (confirmed by grepping every configs_gear_chest_*/configs_gear_back_*
# file's own TalentListContainer references -- Mask/Gloves/Holster/Kneepads configs reference
# none at all, see CLAUDE.md). Deliberately excludes the superficially-similar
# "dev_testing_backpack_talents"/"dev_testing_chest_talents"/etc. containers that live in the
# same *.mitemgenerationtalentlists files -- those are never referenced by any real item config,
# confirmed by the same grep, so despite containing real-looking talents (Aegis, Second Primary
# Weapon) they're not used as a classification signal here.
GEAR_TALENT_POOL_CONTAINERS = {
    "Chest": {"WarlockChestTalents", "warlock_chest_talents", "active_chest_talents", "common_chest_talents"},
    "Backpack": {"WarlockBackTalents", "warlock_back_talents", "active_backpack_talents", "common_backpack_talents"},
}


def build_gear_talent_pools(raw_dir):
    """{'Chest': {instance_id, ...}, 'Backpack': {...}} -- the actual random-roll talent pool for
    each slot, per the game's own data (see GEAR_TALENT_POOL_CONTAINERS). This is the ground truth
    for Chest/Backpack talent membership, NOT the talent's own filename -- many real Chest/Backpack
    talents are filed under a totally unrelated slot token (e.g. Headhunter, a Chest-only talent
    confirmed by the user, is filed as `warlock_talent_headshot_kills_increase_next_weapon_hit`
    with no slot token at all; Tag Team, also Chest-only, is filed as
    `talent_mask_hits_reduce_cooldown`). Multiple *.mitemgenerationtalentlists files declare the
    same container name with a different uid each (looks like one per content shard, same
    "~20 near-duplicate files" situation the configs directory already has) -- unioned across all
    of them rather than picking one, same spirit as the rest of this codebase's config indexing."""
    talentlists_dir = os.path.join(raw_dir, "game system data", "juice", "itemgeneration", "talentlists")
    wanted = {name: slot for slot, names in GEAR_TALENT_POOL_CONTAINERS.items() for name in names}
    pools = {slot: set() for slot in GEAR_TALENT_POOL_CONTAINERS}
    container_re = re.compile(r'TalentListContainer\s+"?([A-Za-z0-9_]+)"?\s*<[^>]*>\s*\{')
    for path in glob.glob(os.path.join(talentlists_dir, "*.mitemgenerationtalentlists")):
        text = open(path, encoding="utf-8", errors="replace").read()
        for m in container_re.finditer(text):
            name = m.group(1)
            if name not in wanted:
                continue
            body, _ = extract_braced(text, text.index("{", m.end() - 1))
            refs = re.findall(r'=\s*(\S+)\s+[0-9A-Fa-f]{20,}', body)
            pools[wanted[name]].update(r.lower() for r in refs)
    return pools


def build_exotic_gear_talent_slots(raw_dir):
    """Reverse-lookup map {talent_instance_id (lowercased): slot} built by walking every exotic
    *armor* item (same glob extract_exotic_items.py uses) and resolving its own preset Exotic-tier
    talent reference -- the same item->talent resolution that pipeline already does per item, just
    inverted here since we're starting from the talent side. Exists because a real exotic item's
    own unique talent's filename often carries no slot/weapon-type token at all (e.g. Tinkerer
    mask's talent is just `talent_exotic_abridged`, not `talent_exotic_mask_abridged`) -- filename
    convention alone can't classify these, but the item's own config can. Weapon exotics aren't
    covered (this codebase has no weapon .mitem parsing anywhere -- out of scope, see CLAUDE.md),
    so a talent that turns out to belong to an exotic weapon instead simply won't resolve here."""
    item_dir = os.path.join(raw_dir, "game system data", "juice", "item")
    configs_dir = os.path.join(raw_dir, "game system data", "juice", "itemgeneration", "configs")
    result = {}
    paths = glob.glob(os.path.join(item_dir, "player_gear_*exotic*.mitem"))
    for path in paths:
        fname = os.path.basename(path).lower()
        if "blueprint" in fname or "aprilfools" in fname:
            continue
        entry = parse_named_item_file(path)
        if not entry or not entry["slot"]:
            continue
        config_body = find_generation_config_block(configs_dir, entry["instance_id"])
        if config_body is None:
            continue
        preset_talent = parse_preset_talent(config_body, quality="Exotic")
        if preset_talent and preset_talent.get("ref_file"):
            result[preset_talent["ref_file"].lower()] = entry["slot"]
    return result


_PRESET_TALENT_RE = re.compile(r'myPresetTalent\s*<[^>]*>\s*=\s*(\S+)\s+[0-9A-Fa-f]{10,}')


def build_exotic_gear_talent_slots_from_configs(raw_dir):
    """A second, independent source for the same {talent_instance_id (lowercased): slot} map as
    build_exotic_gear_talent_slots above -- this one keyed off every ItemGenerationConfig's own
    declared name instead of the owning item's .mitem file. Exists because a real exotic item's
    .mitem file can be missing from a given export (only its blueprint craft recipe survives) even
    though its ItemGenerationConfig -- and therefore its slot and its talent reference(s) -- is
    still fully present under itemgeneration/configs/. Found via a real example: a genuine,
    fully-designed Backpack config (`player_gear_back_exotic_01_config` -- two guaranteed bonus
    slots, a Core, TWO myPresetTalent entries) exists with no `player_gear_back_exotic_01.mitem`
    anywhere in the export at all, so build_exotic_gear_talent_slots (which can only ever walk
    real item files) has no way to ever find it -- its two talents, "... Two in the Bag" and
    "One in Hand...", were being shown as unresolved/orphaned even though they're demonstrably
    real, currently-designed content, not legacy/cut data (see CLAUDE.md's "Potential Bonuses"
    section for the fuller story and how this was caught).

    `_index_generation_configs` already indexes every `.mitemgenerationconfigs` file in the whole
    configs/ directory flatly (including the `configs_exotics_*` family) -- nothing needed there.
    This function's own job is just deriving the slot from the CONFIG's own name (same SLOT_MAP
    token match `parse_named_item_file` uses on an item's filename) instead of from an item file
    that might not exist, and -- unlike `parse_preset_talent`, which only ever returns the first
    match -- collecting EVERY `myPresetTalent` in the Exotic-tier block, since a single config can
    genuinely assign more than one (confirmed by the two-talent Backpack above)."""
    configs_dir = os.path.join(raw_dir, "game system data", "juice", "itemgeneration", "configs")
    result = {}
    for name in _index_generation_configs(configs_dir):
        tokens = name.lower().split("_")
        slot = next((SLOT_MAP[t] for t in tokens if t in SLOT_MAP), None)
        if not slot:
            continue
        body = _load_config_body(configs_dir, name)
        if body is None:
            continue
        for qbody in _quality_blocks(body, "QualityTalentSlots", "Exotic"):
            for m in _PRESET_TALENT_RE.finditer(qbody):
                result[m.group(1).lower()] = slot
    return result


# ---------------------------------------------------------------------------
# Potential/conditional bonus-attribute inference -- Part 2 of the Talent Browser work.
#
# A talent's tooltip text often grants a bonus attribute (Weapon Damage, Skill Damage, Bonus
# Armor, ...) conditionally -- e.g. "increases total weapon damage by 15% while in cover". No
# script can reliably interpret free-form flavor text like that; only a human (or an AI reading
# it, same as this codebase's own author did for tools/talent_bonus_inferences.json) can. So the
# interpretation is done ONCE, by hand, and persisted in tools/talent_bonus_inferences.json --
# {talent_id: {"fingerprint": md5(description), "bonuses": [{"attribute", "condition"}, ...]}} --
# the same "persist the expensive judgment call, let the script only ever check for drift"
# pattern already used by tools/attribute_uid_dictionary.json and
# tools/named_items_manual_overrides.json.
#
# This script's own job is narrow: for every in-scope talent (kind in BONUS_INFERENCE_KINDS --
# only gear/exotic-gear, since only those ever appear on an equippable Chest/Backpack/exotic
# piece this tool can point a user at; weapon-side talents have no "which gear should I equip"
# answer in this dataset and are deliberately left out of the inference dictionary entirely),
# hash the CURRENT description and compare against the persisted fingerprint:
#   - fingerprint matches  -> attach the persisted bonuses as `potentialBonuses`, done.
#   - id missing entirely  -> flag as needing interpretation (new talent), no field attached.
#   - fingerprint mismatch -> flag as needing interpretation (description changed since it was
#                             last read), no field attached -- a changed description means the
#                             conditions/numbers may no longer be accurate, so it's safer to show
#                             nothing than a stale answer until it's re-interpreted by hand.
# Never invents or edits an interpretation itself -- only the dictionary file, hand-maintained,
# is allowed to change what a talent's potential bonuses are.
BONUS_INFERENCE_KINDS = {"gear", "exotic-gear"}


def load_bonus_inferences(repo_root):
    path = os.path.join(repo_root, "tools", "talent_bonus_inferences.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def apply_bonus_inferences(results, repo_root):
    """Attaches `potentialBonuses` to every in-scope talent whose persisted interpretation is
    still fresh (fingerprint matches its current description); returns a report-lines list
    covering everything that still needs a human/AI interpretation pass."""
    inferences = load_bonus_inferences(repo_root)
    needs_new = []
    needs_refresh = []
    applied = 0
    for t in results:
        if t["kind"] not in BONUS_INFERENCE_KINDS:
            continue
        entry = inferences.get(t["id"])
        fingerprint = hashlib.md5(t["description"].encode("utf-8")).hexdigest()
        if entry is None:
            needs_new.append((t["id"], t["name"]))
            continue
        if entry["fingerprint"] != fingerprint:
            needs_refresh.append((t["id"], t["name"]))
            continue
        t["potentialBonuses"] = entry["bonuses"]
        applied += 1

    lines = []
    lines.append("\nPotential-bonus inference coverage (gear/exotic-gear talents only): "
                  "%d applied, %d new, %d changed\n" % (applied, len(needs_new), len(needs_refresh)))
    if needs_new:
        lines.append("  Never interpreted -- add to tools/talent_bonus_inferences.json: %d\n" % len(needs_new))
        for iid, name in needs_new:
            lines.append("    - %s (%s)\n" % (iid, name))
    if needs_refresh:
        lines.append("  Description changed since last interpreted -- re-check in "
                      "tools/talent_bonus_inferences.json: %d\n" % len(needs_refresh))
        for iid, name in needs_refresh:
            lines.append("    - %s (%s)\n" % (iid, name))
    return "".join(lines)


# ---------------------------------------------------------------------------
# Exclusion rules -- prefixes/patterns that are NOT normal droppable weapon/gear talents.
# Each one was checked by hand against real file contents before being excluded; see
# CLAUDE.md for what was found for each bucket.
# ---------------------------------------------------------------------------
EXCLUDE_PREFIXES = (
    "talent_gearset_",       # already fully covered by combined_sets.json (4pc/companion talents)
    "talent_specialization_",# specialization skill tree, different system
    "specialization_",       # same system, filed without the "talent_" lead-in (e.g.
                              # "Specialization_Ammo_GL", "specialization_bonus_skillpower")
    "warlock_skill_talent_", # Skill Tier 7 unlocks, tied to a skill not to equipped gear/weapon
    "dz_",                   # Dark Zone rank/reputation perks, account-level
    "boo_",                  # battle-pass / account reward perks (inventory slots, loadouts, etc.)
    "test",                  # literal test data
    "talent_watch_",         # cut/unused "Watch" gear slot, never shipped
    "talent_sd_",            # "Dungeon Arena" (roguelike mode) temporary talent pool, not droppable gear
    "talent_augment_",       # Skill Augments, a different equip system from weapon/gear talents
)

PLACEHOLDER_NAME_RE = re.compile(
    r'\(PH\)|TBD|INSERT (NAME|TEXT)|TEMP NAME|^\[.*\]$', re.IGNORECASE
)

# longest-prefix-first; matched against the instance id with the recognized lead-in stripped.
GEAR_PREFIXES = [
    ("kneepads", "Kneepads"), ("holster", "Holster"), ("backpack", "Backpack"),
    ("gloves", "Gloves"), ("chest", "Chest"), ("mask", "Mask"), ("back", "Backpack"),
]
# Non-exotic gear only rolls a Talent on Chest/Backpack -- Mask/Gloves/Holster/Kneepads pieces
# only ever roll attributes (confirmed by the user's in-game knowledge; matches this codebase's
# own existing finding that non-exotic Named Items on those 4 slots carry Fixed attributes and
# never a talent -- see CLAUDE.md's Named Items section). A "talent_mask_*"/"talent_gloves_*"/
# etc. file with a real name/description DOES genuinely exist in the export for all 6 slots, but
# for the 4 that can't roll a talent in the live game that's leftover/legacy data (same situation
# as the confirmed-cut "Watch" slot), not real obtainable content -- excluded, not just
# recategorized as "other", so as not to imply they're some other kind of universal talent.
NONEXOTIC_GEAR_SLOTS = {"Backpack", "Chest"}
WEAPON_PREFIXES = [
    ("assault_rifle", "Assault Rifle"), ("marksman_rifle", "Marksman Rifle"),
    ("light_machine_gun", "LMG"), ("assault", "Assault Rifle"), ("marksman", "Marksman Rifle"),
    ("shotgun", "Shotgun"), ("pistol", "Pistol"), ("signature", "Signature Weapon"),
    ("smg", "SMG"), ("lmg", "LMG"), ("mmr", "Marksman Rifle"), ("rifle", "Rifle"),
    ("weapon", "Any Weapon"),
]
# An exotic weapon's talent is always tied to ONE specific weapon, never actually usable on "any
# weapon" the way the generic droppable pool is -- but its filename often only carries the bare
# "weapon" token (e.g. talent_exotic_weapon_big_alejandro, an LMG-only talent), with no way to
# recover which weapon from the filename alone (this codebase has no weapon .mitem parsing at
# all -- out of scope). Matching that bare token against a *specific* weapon type here would be a
# straightforward lie, so it's excluded from the exotic-side lookup; classify_talent leaves
# weapon_type unresolved (None) for these instead of mislabeling them "Any Weapon".
EXOTIC_WEAPON_PREFIXES = [p for p in WEAPON_PREFIXES if p[0] != "weapon"]


def _match_prefix(rest, table):
    for prefix, label in table:
        if rest == prefix or rest.startswith(prefix + "_"):
            return label
    return None


_PREFIX_ALIASES = (
    # longest/most-specific first -- "warlock_"/"virginia_" are internal dev codenames that
    # prefix an otherwise-normal "talent_exotic_"/"talent_gear_" id (see CLAUDE.md), so they
    # must be tried before the bare "talent_" fallback or they'd never strip correctly.
    ("virginia_talent_exotic_", "exotic"),
    ("warlock_talent_exotic_", "exotic"),
    ("talent_exotic_", "exotic"),
    ("talent_gear_", "plain"),
    ("warlock_talent_", "plain"),
    ("talent_", "plain"),
)


def classify_talent(instance_id):
    """Returns (kind, slot_or_none, weapon_type_or_none). Falls back to ('other', None, None)
    when the id doesn't carry a recognizable slot/weapon-type token at all -- a real, in-scope
    talent that just isn't restricted to one slot/weapon (see CLAUDE.md's 'other' bucket notes)."""
    iid = instance_id.lower()
    if iid == "ninja_backpack_talent_exotic":
        return "exotic-gear", "Backpack", None

    rest, base = None, None
    for prefix, kind in _PREFIX_ALIASES:
        if iid.startswith(prefix):
            rest, base = iid[len(prefix):], kind
            break
    if rest is None:
        return "other", None, None

    slot = _match_prefix(rest, GEAR_PREFIXES)
    if slot:
        if base == "exotic":
            return "exotic-gear", slot, None
        if slot in NONEXOTIC_GEAR_SLOTS:
            return "gear", slot, None
        return "invalid-nonexotic-slot", slot, None
    if base == "exotic":
        weapon_type = _match_prefix(rest, EXOTIC_WEAPON_PREFIXES)
        if weapon_type:
            return "exotic-weapon", None, weapon_type
        # bare "weapon" token, or no weapon-type token at all -- known to be an exotic talent,
        # but which specific item it belongs to needs the item-side cross-reference (gear) or
        # can't be resolved at all in this dataset (weapon exotics, out of scope structurally).
        return "exotic-unresolved", None, None
    weapon_type = _match_prefix(rest, WEAPON_PREFIXES)
    if weapon_type:
        return "weapon", None, weapon_type
    return "other", None, None


def load_named_item_talent_ids(repo_root):
    """{talentId, ...} for every Named Item with a preset talent -- the other place (besides an
    Exotic Item's own preset, see build_exotic_gear_talent_slots) a "gear"-kind talent absent from
    the live random-roll pool can still be genuinely obtainable rather than legacy/cut: it might be
    one specific Named Item's own directly-assigned talent instead of a random roll (e.g. Festive
    Delivery's Fireworks Show, `talent_gear_back_firecrackers` -- never in the Backpack pool, but
    real, confirmed by this cross-reference rather than guessed)."""
    path = os.path.join(repo_root, "data", "named_items.json")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {it["talentId"].lower() for it in items if it.get("talentId")}


def build_all_talents(raw_dir, repo_root):
    talent_dir = os.path.join(raw_dir, "game system data", "juice", "talent")
    paths = sorted(glob.glob(os.path.join(talent_dir, "*.mtalent")))
    # Item-file-based first (has real item context to fall back on if ever needed), then the
    # config-name-based map fills in any talent whose own item file is missing from this export
    # (see build_exotic_gear_talent_slots_from_configs) -- .update() lets the item-based result
    # win on the rare id both would resolve, though in practice they should never disagree. Kept
    # as two separate maps (not just the merged one) so the report below can call out specifically
    # which talents were ONLY resolvable via a config -- i.e. confirmed real (a full, live
    # ItemGenerationConfig exists) but with no owning .mitem file in this export to name it, a
    # genuine export gap rather than legacy/cut data.
    exotic_gear_talent_slots_from_configs = build_exotic_gear_talent_slots_from_configs(raw_dir)
    exotic_gear_talent_slots_from_items = build_exotic_gear_talent_slots(raw_dir)
    exotic_gear_talent_slots = dict(exotic_gear_talent_slots_from_configs)
    exotic_gear_talent_slots.update(exotic_gear_talent_slots_from_items)
    confirmed_item_missing_file = sorted(set(exotic_gear_talent_slots_from_configs)
                                          - set(exotic_gear_talent_slots_from_items))
    gear_pools = build_gear_talent_pools(raw_dir)
    named_item_talent_ids = load_named_item_talent_ids(repo_root)

    results = []
    excluded_by_prefix = 0
    excluded_placeholder = []
    excluded_empty = []
    excluded_invalid_slot = []
    excluded_unused_gear = []
    resolved_via_item_lookup = []
    resolved_via_pool = []
    parse_failures = []
    kind_counts = {}

    for path in paths:
        fname = os.path.basename(path)
        instance_id_guess = fname[:-len(".mtalent")]
        if instance_id_guess.startswith(EXCLUDE_PREFIXES):
            excluded_by_prefix += 1
            continue

        parsed = parse_mtalent_file(path)
        if not parsed:
            parse_failures.append(fname)
            continue

        instance_id = parsed["instance_id"]
        if instance_id.lower().startswith(EXCLUDE_PREFIXES):
            excluded_by_prefix += 1
            continue

        raw_name = parsed["ui_name"]
        name = strip_inline_markup(raw_name) if raw_name else None
        if not name or PLACEHOLDER_NAME_RE.search(name):
            excluded_placeholder.append((instance_id, raw_name))
            continue

        description = strip_inline_markup(naive_substitute(parsed["tooltip"], parsed["values"]))
        if not description or description == "(no tooltip text found)":
            excluded_empty.append(instance_id)
            continue

        kind, slot, weapon_type = classify_talent(instance_id)

        # Authoritative override #1: does this talent's id match some Exotic Item's OWN preset
        # talent (see build_exotic_gear_talent_slots)? Checked universally, for every kind, not
        # just ones classify_talent already suspected were exotic -- found by a real example:
        # Collector's own talent is `talent_back_hoarder_grenade_enhancements` ("Hoarder"), an id
        # with no "exotic" token anywhere in it, so classify_talent's prefix-alias step alone
        # (which only looks for an exotic cross-reference when the "exotic" base was already
        # detected from the filename) had no way to ever catch it -- it silently fell into the
        # generic "gear" bucket instead, implying it's obtainable via random Chest/Backpack roll
        # like any other, when it's really Collector's own unique, item-specific ability. An
        # item-preset match always wins over anything classify_talent or the gear-pool guessed.
        base_id = instance_id[:-len("_perfect")] if instance_id.endswith("_perfect") else instance_id
        found_slot = exotic_gear_talent_slots.get(instance_id.lower()) or exotic_gear_talent_slots.get(base_id.lower())
        if found_slot:
            if kind != "exotic-gear" or slot != found_slot:
                resolved_via_item_lookup.append((instance_id, kind, slot, found_slot))
            kind, slot, weapon_type = "exotic-gear", found_slot, None

        # Authoritative override #2: the game's own Chest/Backpack random-roll talent pool (see
        # build_gear_talent_pools) is ground truth for slot membership, and beats the filename
        # guess in both directions -- it rescues real Chest/Backpack talents classify_talent had
        # no slot token for (kind "other") or actively misclassified via a stale/wrong slot token
        # (kind "invalid-nonexotic-slot", e.g. Headhunter filed as `warlock_talent_...`, Tag Team
        # filed as `talent_mask_hits_reduce_cooldown`). A "_perfect" talent is never itself listed
        # in the pool (only its base talent is -- Perfect is a fixed upgrade, not a separate random
        # roll), so its base id is checked too. Only applied to non-exotic kinds -- an exotic's
        # talent comes from its own item config (myPresetTalent), never this general roll pool.
        pool_slots = []
        if not kind.startswith("exotic"):
            pool_slots = sorted(s for s, ids in gear_pools.items()
                                 if base_id.lower() in ids or instance_id.lower() in ids)
            if pool_slots:
                if kind != "gear" or slot not in pool_slots:
                    resolved_via_pool.append((instance_id, kind, slot, pool_slots))
                kind, slot = "gear", " / ".join(pool_slots)

        # Liveness check: a "gear"-kind talent absent from the live random-roll pool AND not any
        # Named Item's own preset talent (the two structurally-confirmable ways a Chest/Backpack
        # talent is actually obtainable right now) is legacy/cut data -- classify_talent's filename
        # guess or its own real .mtalent file existing in the export doesn't mean it's still live;
        # this codebase's own dev-testing-only talent lists (see CLAUDE.md) are proof the raw
        # export contains real, well-formed, but genuinely unused talent files. Excluded rather
        # than shown as if obtainable, matching the user's explicit "don't surface currently-unused
        # content" rule. Exotic-gear talents are exempt here (checked via override #1 above
        # instead, since they're never in this pool by design) as is anything not "gear" at all.
        if kind == "gear" and not pool_slots and instance_id.lower() not in named_item_talent_ids \
                and base_id.lower() not in named_item_talent_ids:
            excluded_unused_gear.append((instance_id, name))
            continue

        if kind == "invalid-nonexotic-slot":
            excluded_invalid_slot.append((instance_id, slot))
            continue
        if kind == "exotic-unresolved":
            # Filename carried the "exotic" prefix but no slot/weapon-type token (e.g. Tinkerer
            # mask's talent is just talent_exotic_abridged) AND override #1 above found no owning
            # item either -- genuinely can't place this one (almost always an exotic WEAPON talent,
            # out of scope structurally, see EXOTIC_WEAPON_PREFIXES).
            kind = "exotic-other"
        tier = "Perfect" if instance_id.endswith("_perfect") else "Standard"

        results.append({
            "id": instance_id,
            "name": name,
            "description": description,
            "kind": kind,
            "slot": slot,
            "weaponType": weapon_type,
            "tier": tier,
        })
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    results.sort(key=lambda t: (t["kind"], t["slot"] or "", t["weaponType"] or "", t["name"]))
    bonus_inference_report = apply_bonus_inferences(results, repo_root)

    report_lines = []
    report_lines.append("# All-Talents extraction report\n")
    report_lines.append("Files scanned: %d\n" % len(paths))
    report_lines.append("Excluded (out-of-scope prefix): %d\n" % excluded_by_prefix)
    report_lines.append("Excluded (placeholder/unnamed): %d\n" % len(excluded_placeholder))
    for iid, raw in excluded_placeholder:
        report_lines.append("  - %s (raw name: %r)\n" % (iid, raw))
    report_lines.append("Excluded (no usable description): %d\n" % len(excluded_empty))
    for iid in excluded_empty:
        report_lines.append("  - %s\n" % iid)
    report_lines.append("Excluded (non-exotic talent on a slot that can't roll one -- Mask/Gloves/"
                         "Holster/Kneepads only get Fixed attributes in the live game, confirmed "
                         "by the user; likely legacy/cut data): %d\n" % len(excluded_invalid_slot))
    for iid, slot in excluded_invalid_slot:
        report_lines.append("  - %s (%s)\n" % (iid, slot))
    report_lines.append("Excluded (Chest/Backpack talent absent from the live random-roll pool AND "
                         "not any Named Item's own preset talent -- legacy/cut, not currently "
                         "obtainable): %d\n" % len(excluded_unused_gear))
    for iid, nm in excluded_unused_gear:
        report_lines.append("  - %s (%s)\n" % (iid, nm))
    report_lines.append("Parse failures: %d\n" % len(parse_failures))
    for f in parse_failures:
        report_lines.append("  - %s\n" % f)
    report_lines.append("Reclassified to exotic-gear via item-side cross-reference (this talent "
                         "id is some Exotic Item's own preset talent, regardless of what its "
                         "filename suggested): %d\n" % len(resolved_via_item_lookup))
    for iid, old_kind, old_slot, slot in resolved_via_item_lookup:
        report_lines.append("  - %s: was (%s, %s) -> (exotic-gear, %s)\n" % (iid, old_kind, old_slot, slot))
    report_lines.append("Slot set/corrected via the authoritative Chest/Backpack talent pool "
                         "(filename token was missing, wrong, or incomplete): %d\n" % len(resolved_via_pool))
    for iid, old_kind, old_slot, pool_slots in resolved_via_pool:
        report_lines.append("  - %s: was (%s, %s) -> %s\n" % (iid, old_kind, old_slot, " / ".join(pool_slots)))
    if confirmed_item_missing_file:
        results_by_id = {t["id"].lower(): t for t in results}
        report_lines.append("\nConfirmed real (a full, live ItemGenerationConfig exists -- "
                             "attribute slots, Core, talent reference) but the owning item's own "
                             ".mitem file is missing from this export, so no name/flavor text is "
                             "available -- NOT legacy/cut, just an export gap like several other "
                             "already-documented ones (see CLAUDE.md): %d\n" % len(confirmed_item_missing_file))
        for tid in confirmed_item_missing_file:
            t = results_by_id.get(tid)
            report_lines.append("  - %s (%s, %s)\n" % (tid, t["name"] if t else "?", t["slot"] if t else "?"))
    report_lines.append("\nIncluded: %d\n" % len(results))
    for k in sorted(kind_counts):
        report_lines.append("  %s: %d\n" % (k, kind_counts[k]))
    report_lines.append(bonus_inference_report)

    return results, "".join(report_lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--index-html", default=None)
    args = ap.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results, report = build_all_talents(args.raw_dir, repo_root)

    data_dir = os.path.join(repo_root, "data")
    pretty_path = os.path.join(data_dir, "all_talents.json")
    min_path = os.path.join(data_dir, "all_talents_min.json")
    with open(pretty_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(min_path, "w", encoding="utf-8") as f:
        json.dump(results, f, separators=(",", ":"), ensure_ascii=False)

    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_talents_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    index_html_path = args.index_html or os.path.join(repo_root, "index.html")
    with open(min_path, "r", encoding="utf-8") as f:
        min_json = f.read()
    html = open(index_html_path, encoding="utf-8").read()
    # Same landmine as DATA/NAMED_ITEMS embedding (see CLAUDE.md): match must be scoped to a
    # single line (never .*/DOTALL, which would swallow adjacent const declarations), and the
    # replacement must be passed as a function so re.sub doesn't interpret backslash escapes
    # (\n, \g<...>) that legitimately occur inside talent flavor text.
    pattern = re.compile(r'const ALL_TALENTS = \[[^\n]*\];')
    new_line = "const ALL_TALENTS = %s;" % min_json
    if pattern.search(html):
        html, n = pattern.subn(lambda m: new_line, html)
    else:
        # first run: insert right after the NAMED_ITEMS/EXOTIC_ITEMS const block
        marker = re.compile(r'(const EXOTIC_ITEMS = \[[^\n]*\];\n)')
        html, n = marker.subn(lambda m: m.group(1) + new_line + "\n", html)
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(report)
    print("Wrote %s, %s, %s; embedded into %s (n=%d)" % (
        pretty_path, min_path, report_path, index_html_path, n))


if __name__ == "__main__":
    main()
