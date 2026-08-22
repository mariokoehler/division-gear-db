"""
Extract "Exotic Item" metadata (e.g. Catharsis, Deathgrips-tier-but-Exotic gear) from a Hunter
"raw files" export and write data/exotic_items.json (+ min copy). Sibling to
extract_named_items.py, reusing almost all of its parsing machinery -- see CLAUDE.md for
background on the Snowdrop text-config format and known landmines, and the "Exotic Items"
section specifically for what's different about this category.

Usage:
    python tools/extract_exotic_items.py --raw-dir "E:\\Temp\\Hunter\\raw_files\\hunter"

Never commits/pushes anything, re-embeds EXOTIC_ITEMS into index.html the same safe way
extract_named_items.py re-embeds NAMED_ITEMS (see the comment on that substitution for why a
plain-string re.sub replacement and a DOTALL/greedy match are both unsafe here).
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_named_items import (
    extract_braced, strip_inline_markup, strip_color_tags, parse_named_item_file,
    find_generation_config_block, parse_preset_attributes, parse_preset_talent,
    parse_core_attributes, build_talent_index, SLOT_MAP, _quality_blocks,
)

# Exotics known to be unreleased/non-functional in every export seen so far -- excluded by
# instance_id rather than silently guessed around:
#   - player_gear_gloves_exotic_02 ("Rathbone's Gloves"): myItemGenerationConfig is a literal
#     NULLREFERENCE in the item file itself; find_generation_config_block correctly returns None
#     for it, so this is actually excluded automatically (listed here only for documentation).
#   - player_gear_kneepads_exotic_04: myUIName is literally "TBD" -- excluded automatically by
#     the placeholder-name check below (same treatment as named items' "INSERT NAME HERE").
EXCLUDED_INSTANCE_IDS = set()

# player_gear_mask_exotic_06 ("Investor") used to be excluded outright (a real, released Y8S1
# item, but its own talent text says "This item can feature any Core Attribute" / "features a
# third random Attribute instead of a mod slot" -- confirmed by the user, 2026-08-18, to be
# intentionally fully-random, with no fixed bonus types or fixed Core at all, unlike this
# dataset's usual "always X and Y" model). That left its talent, "Slotted", permanently
# unattachable to any card -- the same "orphaned talent" symptom Acosta's Go Bag had, but for a
# different underlying reason (this item's own .mitem file IS present; it was a deliberate
# design-fit exclusion, not a missing-file gap). The user asked to include it anyway once there
# was something to connect "Slotted" to. Structurally this is safe: every one of its bonus/Core
# slots really does carry the null-UID sentinel this codebase already uses everywhere else for
# "not actually preset" (confirmed by reading its config directly), so `parse_core_attributes`
# and the bonus-slot loop below both naturally produce an honest, correct `cores: []` /
# `bonuses: []` -- nothing needs to be invented. The only real risk was the null-UID bonus slots
# being logged as MISSING_BONUS_ATTRIBUTE (this codebase's usual meaning for that signal: a real
# export gap needing research) when here it's neither a gap nor unresolved, so those 3 slots are
# suppressed from that review-note path specifically for this item (see the loop below) and the
# item instead carries `"bonusesRandom": true`, which index.html renders as an explicit note
# instead of the misleading "not yet resolved" language used for genuine gaps.
CONFIRMED_RANDOM_BONUS_ITEMS = {"player_gear_mask_exotic_06"}

PLACEHOLDER_NAMES = {"TBD", "INSERT NAME HERE"}


def build_exotic_items(raw_dir, uid_dict):
    item_dir = os.path.join(raw_dir, "game system data", "juice", "item")
    configs_dir = os.path.join(raw_dir, "game system data", "juice", "itemgeneration", "configs")
    talent_index, naive_substitute = build_talent_index(raw_dir)

    unresolved_uids = set()
    review_notes = []
    output = []

    paths = sorted(glob.glob(os.path.join(item_dir, "player_gear_*exotic*.mitem")))
    # blueprint_*/appearance_*/layer_gear_* are crafting recipes / cosmetics, not the item itself
    # (same landmine as named items); "_aprilfools" variants are joke reskins of a real item, not
    # a separate item.
    paths = [p for p in paths
             if "blueprint" not in os.path.basename(p).lower()
             and "aprilfools" not in os.path.basename(p).lower()]

    for path in paths:
        entry = parse_named_item_file(path)
        if not entry or not entry["slot"]:
            review_notes.append(("STRUCTURAL", os.path.basename(path), "could not parse slot"))
            continue
        if not entry["name"] or entry["name"] in PLACEHOLDER_NAMES:
            continue
        if entry["instance_id"] in EXCLUDED_INSTANCE_IDS:
            continue

        # Exotics don't belong to a civilian brand -- parse_named_item_file's brand_code fallback
        # (matching this file's own top-of-file gearbrand include) picks up unrelated shared-asset
        # includes for exotics (e.g. Catharsis includes gearbrand_set_c.mgearbrand, which is NOT
        # actually Catharsis's brand -- exotics simply don't have one), so it's deliberately
        # ignored here rather than reused the way named items reuse it.

        bonuses = []
        talent = None
        talent_id = None
        talent_status = None
        cores = []

        config_body = find_generation_config_block(configs_dir, entry["instance_id"])
        if config_body is None:
            # Unlike named items (where a missing config has so far always meant "genuinely real
            # item, export just doesn't have this one file"), the one exotic seen with no config
            # (Rathbone's Gloves) has a literal NULLREFERENCE for myItemGenerationConfig in its
            # own .mitem file -- i.e. this item was never finished, not merely under-exported.
            # Exclude entirely rather than including a talent-less, bonus-less, core-less card.
            review_notes.append(("EXCLUDED", entry["name"],
                                  "no ItemGenerationConfig found for '%s' -- likely unreleased, excluded"
                                  % entry["instance_id"]))
            continue
        else:
            cores = parse_core_attributes(config_body, uid_dict, quality="Exotic")

            for slot in parse_preset_attributes(config_body, quality="Exotic"):
                # Unlike named items' fixed attributes, an exotic's guaranteed bonus TYPE slot
                # never carries myPresetPercentage at all (the exact value stays randomized on
                # roll -- that's the whole point) -- so, unlike parse_preset_attributes's callers
                # in extract_named_items.py, has_preset_percentage is deliberately NOT checked
                # here; only is_core and the null-UID sentinel matter.
                if slot["is_core"]:
                    continue
                if re.match(r'^0+$', slot["uid"]):
                    if entry["instance_id"] in CONFIRMED_RANDOM_BONUS_ITEMS:
                        # Investor: every bonus/Core slot is null-UID by design (confirmed by the
                        # user, see CONFIRMED_RANDOM_BONUS_ITEMS above) -- not a gap, so no
                        # MISSING_BONUS_ATTRIBUTE note here; bonuses_random gets set below instead.
                        continue
                    # seen on Acosta's Kneepads: both bonus slots reference the null UID in this
                    # export, an export gap (the item is real, Y6S1) rather than a design quirk --
                    # flag it instead of silently shipping a 0- or 1-entry bonus list unexplained.
                    review_notes.append(("MISSING_BONUS_ATTRIBUTE", entry["name"],
                                          "a bonus slot's myPresetAttribute is the null UID -- "
                                          "not resolvable from this export"))
                    continue
                stat = uid_dict.get(slot["uid"])
                if stat:
                    bonuses.append(stat)
                else:
                    unresolved_uids.add(slot["uid"])
                    bonuses.append("Unknown Attribute (%s)" % slot["uid"])

            preset_talent = parse_preset_talent(config_body, quality="Exotic")
            if preset_talent:
                talent_id = preset_talent["ref_file"]
                t = talent_index.get(preset_talent["ref_file"])
                if t:
                    desc = strip_inline_markup(naive_substitute(t["tooltip"], t["values"]))
                    talent = {"name": strip_color_tags(t["ui_name"]) or "(unnamed)", "desc": desc}
                    talent_status = "datamined"
                else:
                    talent_status = "MISSING"
                    review_notes.append((
                        "MISSING_TALENT", entry["name"],
                        "unique talent file '%s.mtalent' referenced but not present in "
                        "this export -- needs manual research" % preset_talent["ref_file"],
                    ))
            else:
                review_notes.append(("STRUCTURAL", entry["name"], "no Exotic-tier Talent reference found"))

        flavor = entry["description"] or None

        out = {
            "instance_id": entry["instance_id"],
            "name": entry["name"],
            "slot": entry["slot"],
            "isDarkZoneExclusive": entry["is_dz"],
            "flavorText": flavor,
            "bonuses": bonuses,
            # True only for items confirmed to have no fixed bonus types or Core at all by design
            # (see CONFIRMED_RANDOM_BONUS_ITEMS) -- `bonuses`/`cores` are correctly empty for these,
            # not unresolved, so index.html shows an explicit "fully random" note instead of the
            # "not yet resolved" language used for a genuine export gap.
            "bonusesRandom": entry["instance_id"] in CONFIRMED_RANDOM_BONUS_ITEMS,
            "cores": cores,
            "talent": talent,
            # The .mtalent instance id behind `talent` (present even when talent_status is
            # "MISSING" -- it's the id that WAS referenced, just not resolvable from this export).
            # Lets index.html cross-reference this item's own talent against ALL_TALENTS'
            # `potentialBonuses` (see tools/talent_bonus_inferences.json) to show the item's
            # conditional bonuses on its Attribute Finder card, not just its Talent Browser card.
            "talentId": talent_id,
            "source": "datamined",
        }
        if talent_status == "MISSING":
            out["talentStatus"] = "needs_manual_research"
        output.append(out)

    return output, unresolved_uids, review_notes


_PRESET_TALENT_RE = re.compile(r'myPresetTalent\s*<[^>]*>\s*=\s*(\S+)\s+[0-9A-Fa-f]{10,}')


def load_exotic_manual_additions(repo_dir):
    path = os.path.join(repo_dir, "tools", "exotic_items_manual_additions.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_manual_config_items(raw_dir, uid_dict, repo_dir, talent_index, naive_substitute):
    """Reconstructs a full Exotic Item entry directly from its ItemGenerationConfig, for the rare
    case where the item's own .mitem file (name, flavor text, DZ flag) is missing from every
    export used so far but its config is fully present. See
    tools/exotic_items_manual_additions.json for the confirmed name/DZ flag this can never
    datamine on its own (a user in-game check, since there's no export data to read it from), and
    CLAUDE.md's "Potential Bonuses" section for how this was discovered -- Acosta's Go Bag, found
    because the user asked why its "orphaned" talent, "... Two in the Bag", showed up with no item
    card at all. Everything else -- bonuses, cores, and (unlike build_exotic_items's single-talent
    assumption, since this item genuinely has two active talents at once, confirmed by the user)
    EVERY preset talent in the config -- comes straight from the config, same as the main
    pipeline; nothing here is guessed."""
    configs_dir = os.path.join(raw_dir, "game system data", "juice", "itemgeneration", "configs")
    manual = load_exotic_manual_additions(repo_dir)
    output = []
    review_notes = []
    unresolved_uids = set()

    for instance_id, info in manual.items():
        config_body = find_generation_config_block(configs_dir, instance_id)
        if config_body is None:
            review_notes.append(("MANUAL_ADDITION_FAILED", info["name"],
                                  "no ItemGenerationConfig found for '%s' -- manual addition entry "
                                  "is stale, remove it or re-check" % instance_id))
            continue

        slot = next((SLOT_MAP[t] for t in instance_id.lower().split("_") if t in SLOT_MAP), None)
        if not slot:
            review_notes.append(("MANUAL_ADDITION_FAILED", info["name"],
                                  "could not derive a slot from instance_id '%s'" % instance_id))
            continue

        cores = parse_core_attributes(config_body, uid_dict, quality="Exotic")

        bonuses = []
        for bslot in parse_preset_attributes(config_body, quality="Exotic"):
            if bslot["is_core"]:
                continue
            if re.match(r'^0+$', bslot["uid"]):
                continue
            stat = uid_dict.get(bslot["uid"])
            if stat:
                bonuses.append(stat)
            else:
                unresolved_uids.add(bslot["uid"])
                bonuses.append("Unknown Attribute (%s)" % bslot["uid"])

        # Unlike parse_preset_talent (which only ever returns the FIRST myPresetTalent match --
        # correct for every other exotic, which has exactly one), this collects every one, since
        # this item's config genuinely assigns two talent slots at once.
        talents = []
        for qbody in _quality_blocks(config_body, "QualityTalentSlots", "Exotic"):
            for m in _PRESET_TALENT_RE.finditer(qbody):
                ref_file = m.group(1)
                t = talent_index.get(ref_file)
                if not t:
                    review_notes.append(("MANUAL_ADDITION_MISSING_TALENT", info["name"],
                                          "talent file '%s.mtalent' referenced but not present in "
                                          "this export" % ref_file))
                    continue
                desc = strip_inline_markup(naive_substitute(t["tooltip"], t["values"]))
                talents.append({
                    "name": strip_color_tags(t["ui_name"]) or "(unnamed)",
                    "desc": desc,
                    "talentId": ref_file,
                })

        if not talents:
            review_notes.append(("MANUAL_ADDITION_FAILED", info["name"], "no talent resolved at all"))
            continue

        out = {
            "instance_id": instance_id,
            "name": info["name"],
            "slot": slot,
            "isDarkZoneExclusive": info.get("isDarkZoneExclusive", False),
            "flavorText": None,
            "bonuses": bonuses,
            "bonusesRandom": False,
            "cores": cores,
            "talent": {"name": talents[0]["name"], "desc": talents[0]["desc"]},
            "talentId": talents[0]["talentId"],
            # Present only for the rare item with more than one simultaneously-active preset
            # talent (see the docstring above) -- every other item's entry simply omits this, and
            # index.html treats an absent/empty extraTalents exactly like the old schema.
            "extraTalents": [{"name": t["name"], "desc": t["desc"], "talentId": t["talentId"]}
                              for t in talents[1:]],
            "source": "datamined+manual_item_reconstruction",
        }
        output.append(out)

    return output, unresolved_uids, review_notes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--repo-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()

    repo_dir = args.repo_dir
    uid_dict_path = os.path.join(repo_dir, "tools", "attribute_uid_dictionary.json")
    out_path = os.path.join(repo_dir, "data", "exotic_items.json")
    min_path = os.path.join(repo_dir, "data", "exotic_items_min.json")
    report_path = os.path.join(repo_dir, "tools", "exotic_items_report.md")

    uid_dict = json.load(open(uid_dict_path, encoding='utf-8'))

    items, unresolved, review_notes = build_exotic_items(args.raw_dir, uid_dict)

    talent_index, naive_substitute = build_talent_index(args.raw_dir)
    manual_items, manual_unresolved, manual_notes = build_manual_config_items(
        args.raw_dir, uid_dict, repo_dir, talent_index, naive_substitute)
    items.extend(manual_items)
    unresolved |= manual_unresolved
    review_notes.extend(manual_notes)

    items.sort(key=lambda e: (e["slot"], e["name"]))

    json.dump(items, open(out_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(items, open(min_path, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)

    html_path = os.path.join(repo_dir, "index.html")
    min_json = open(min_path, encoding="utf-8").read()
    html = open(html_path, encoding="utf-8").read()
    new_line = "const EXOTIC_ITEMS = " + min_json + ";"
    # See extract_named_items.py's own NAMED_ITEMS re-embed for why [^\n]* (never DOTALL .*) and a
    # replacement *function* (never a plain string) are both load-bearing here.
    html2, n = re.subn(r"const EXOTIC_ITEMS = \[[^\n]*\];", lambda m: new_line, html, count=1)
    structural_notes = []
    if n == 1:
        open(html_path, "w", encoding="utf-8").write(html2)
    else:
        structural_notes.append(("STRUCTURAL", "index.html", "could not find 'const EXOTIC_ITEMS = [...]' to replace"))

    lines = []
    lines.append("# Exotic items extraction report\n")
    lines.append("Total exotic items found: %d\n" % len(items))
    with_talent = sum(1 for i in items if i["talent"])
    with_full_talent = sum(1 for i in items if i["talent"] and i["talent"].get("desc"))
    lines.append("With a talent resolved: %d (full description: %d)\n" % (with_talent, with_full_talent))
    all_notes = review_notes + structural_notes
    lines.append("## Review notes (%d)\n" % len(all_notes))
    for kind, name, detail in all_notes:
        lines.append("- [%s] %s: %s" % (kind, name, detail))
    lines.append("\n## Unresolved attribute UIDs (%d)\n" % len(unresolved))
    for uid in sorted(unresolved):
        lines.append("- %s" % uid)
    lines.append("\n## All items\n")
    for i in items:
        core_str = "/".join("%s(%s)" % (c["color"], c["stat"]) for c in i["cores"]) or "?"
        lines.append("- **%s** (%s)%s -- bonuses: %s | core: %s | talent: %s" % (
            i["name"], i["slot"],
            " [DZ]" if i["isDarkZoneExclusive"] else "",
            ", ".join(i["bonuses"]) or "(none found)",
            core_str,
            i["talent"]["name"] if i["talent"] else "MISSING",
        ))

    report = "\n".join(lines) + "\n"
    open(report_path, "w", encoding="utf-8").write(report)
    print("Wrote %d exotic items to %s" % (len(items), out_path))
    print("Re-embedded EXOTIC_ITEMS into %s" % html_path if n == 1 else "WARNING: index.html NOT updated -- see report")
    print("Report: %s" % report_path)


if __name__ == "__main__":
    main()
