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
    parse_core_attributes, build_talent_index,
)

# Exotics known to be unreleased/non-functional in every export seen so far -- excluded by
# instance_id rather than silently guessed around:
#   - player_gear_gloves_exotic_02 ("Rathbone's Gloves"): myItemGenerationConfig is a literal
#     NULLREFERENCE in the item file itself; find_generation_config_block correctly returns None
#     for it, so this is actually excluded automatically (listed here only for documentation).
#   - player_gear_kneepads_exotic_04: myUIName is literally "TBD" -- excluded automatically by
#     the placeholder-name check below (same treatment as named items' "INSERT NAME HERE").
#   - player_gear_mask_exotic_06 ("Investor"): a real, released Y8S1 item, but confirmed by the
#     user (2026-08-18, from its own talent text) to be an intentionally fully-random exotic --
#     "This item can feature any Core Attribute" / "features a third random Attribute instead of
#     a mod slot" -- i.e. it has no fixed bonus types or fixed core at all, so it simply doesn't
#     fit this database's "always X and Y" model. Excluded explicitly since there's no generic
#     structural signal to detect this from (unlike the two above).
EXCLUDED_INSTANCE_IDS = {"player_gear_mask_exotic_06"}

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
            "cores": cores,
            "talent": talent,
            "source": "datamined",
        }
        if talent_status == "MISSING":
            out["talentStatus"] = "needs_manual_research"
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
