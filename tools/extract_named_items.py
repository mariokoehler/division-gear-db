"""
Extract "Named Item" metadata (e.g. Deathgrips, Turmoil) from a Hunter "raw files" export and
write data/named_items.json (+ min copy). Companion to update_from_hunter_export.py -- see
CLAUDE.md for background on the Snowdrop text-config format and known landmines.

Usage:
    python tools/extract_named_items.py --raw-dir "E:\\Temp\\Hunter\\raw_files\\hunter"

Never commits/pushes anything, never touches index.html. Review tools/named_items_report.md
and data/named_items.json yourself before wiring the results into the page.
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from update_from_hunter_export import extract_braced as _extract_braced_strict  # noqa: F401


# A few named-item .mitem files (~6 of 64) put a *double*-escaped quote in myDescription's
# flavor text -- e.g. `text = \"\\"Don't fear...\\"\"` -- to make the in-game tooltip itself
# display literal quote marks around a line of dialogue. Read left-to-right, `\\` consumes as
# one escaped backslash, so the very next `"` reads as an *unescaped* real quote under normal
# backslash-doubling rules and prematurely closes the field's outer string -- which then makes
# the stray literal `}` some of these same lines end with (the landmine already known from
# gear-set files, see CLAUDE.md) get miscounted as a real structural brace. Since myUIName/
# myDescription/myIcon/etc. are always confined to a single line in every sample seen, the
# robust fix is to not character-scan those lines for quotes/braces at all -- just skip them
# wholesale before falling back to the normal quote-aware scan for everything else.
_TEXT_FIELD_LINE = re.compile(r'^[ \t]*my[A-Za-z]+\s+["\']')


def extract_braced(s, start):
    assert s[start] == '{'
    depth = 0
    i = start
    string_quote = None
    n = len(s)
    while i < n:
        if string_quote is None:
            line_end = s.find('\n', i)
            if line_end == -1:
                line_end = n
            line = s[i:line_end]
            if _TEXT_FIELD_LINE.match(line):
                i = line_end + 1
                continue
        c = s[i]
        if string_quote:
            if c == '\\':
                i += 2
                continue
            if c == string_quote:
                string_quote = None
        else:
            if c in ('"', "'"):
                string_quote = c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return s[start:i + 1], i + 1
        i += 1
    raise ValueError("unbalanced braces starting at %d" % start)


# ---------------------------------------------------------------------------
# Text-field extraction (handles BOTH text = \"...\" and text = '...' forms --
# named-item files switch to single-quote wrapping whenever the value itself
# contains a double-quoted <color name="..."> tag, which the plain gear-set
# parser never has to deal with)
# ---------------------------------------------------------------------------

def extract_marked_value(field_str, marker, end_marker):
    """`<marker> ` is followed either directly by a quote (when its delimiter differs from the
    enclosing field's own quote type, e.g. text='...' inside myUIName "...") or by a
    backslash-escaped quote of the SAME type (when it doesn't, e.g. text=\\"...\\" inside
    myUIName "..."). In the latter case a value that itself embeds a quoted sub-string (a
    <color name="..."> tag) gets escaped *again*, e.g. name=\\\\"orange\\\\". Rather than track
    escape depth char-by-char (ambiguous -- see extract_braced above), search pragmatically for
    the known trailing marker (`, type` / `, enabled`) in whichever representation matches the
    opening, same approach already proven for .mtalent tooltips in update_from_hunter_export.py."""
    i = field_str.find(marker)
    if i == -1:
        return None
    rest = field_str[i + len(marker):]
    if rest[:1] == '\\':
        quote, opening_len = rest[1:2], 2
    else:
        quote, opening_len = rest[:1], 1
    if quote not in ('"', "'"):
        return None
    opening = rest[:opening_len]
    end = rest.find(opening + end_marker, opening_len)
    if end == -1:
        end = rest.rfind(opening)
    if end < opening_len:
        return None
    raw = rest[opening_len:end]
    # unescape both quote types, not just the delimiter's own -- embedded <color name="..">
    # tags need the *other* quote character unescaped too regardless of which one delimits
    # this particular field.
    for q in ('"', "'"):
        raw = raw.replace('\\\\' + q, q).replace('\\' + q, q)
    return raw.replace('\\n', '\n')


def extract_text_value(field_str):
    return extract_marked_value(field_str, "text = ", ", type")


def extract_context_comment(field_str):
    return extract_marked_value(field_str, "contextComment = ", ", enabled")


def extract_field_text(body, field_name):
    """Find `<field_name> "..."` (or '...') at top level of body and return its text= value,
    falling back to its contextComment= (an internal dev note) when text is empty or an obvious
    unfilled-localization placeholder -- a handful of older named items (Y1-era) never got their
    real in-game description written and instead carry the actual drop-source/talent info only
    in that dev comment."""
    m = re.search(re.escape(field_name) + r'\s+["\']', body)
    if not m:
        return None
    start = m.start()
    nl = body.find('\n', start)
    # myDescription can legitimately contain literal \n sequences (escaped, not real newlines)
    # within the same source line, so the whole field is on one line in the raw text -- just use
    # the rest of that line.
    end = nl if nl != -1 else len(body)
    line = body[start:end]
    text = extract_text_value(line)
    if text is None or text.strip().upper() in ("", "INSERT TEXT HERE", "TBD", "TODO"):
        comment = extract_context_comment(line)
        if comment and comment.strip():
            return comment.strip()
    return text


def strip_inline_markup(s):
    if s is None:
        return None
    return re.sub(r'</?color[^>]*>', '', s).strip()


def strip_color_tags(s):
    """Name-specific cleanup: also drops stray literal quote marks, which is wrong for
    descriptions/tooltips (which can legitimately quote in-game dialogue) but right for names --
    one item's name (The Hollow Man) carries a stray literal `"` before the closing tag in the
    source data itself, a dev typo, not a real part of the display name."""
    s = strip_inline_markup(s)
    if s is None:
        return None
    return s.replace('"', '').strip()


# ---------------------------------------------------------------------------
# .mitem (named item) parsing
# ---------------------------------------------------------------------------

SLOT_MAP = {
    "back": "Backpack", "chest": "Chest", "gloves": "Gloves",
    "holster": "Holster", "kneepads": "Kneepads", "mask": "Mask",
}


def parse_named_item_file(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'ArmorItem\s+(\S+)\s*<[^>]*>\s*(?::\s*\S+)?\s*\{', text)
    if not m:
        return None
    instance_id = m.group(1)
    body, _ = extract_braced(text, m.end() - 1)

    name = strip_color_tags(extract_field_text(body, "myUIName"))
    description = extract_field_text(body, "myDescription")

    fname = os.path.basename(path)
    parts = fname.split('_')
    slot = None
    if len(parts) >= 3 and parts[0] == "player" and parts[1] == "gear":
        slot = SLOT_MAP.get(parts[2])

    brand_m = re.search(r'myGearBrand\s*<[^>]*>\s*=\s*(\S+)\s+([0-9A-Fa-f]+)', body)
    brand_code = None
    if brand_m:
        ref = brand_m.group(1)
        bm = re.match(r'(?:gearbrand|GearBrand)_(.+)', ref, re.IGNORECASE)
        if bm:
            brand_code = bm.group(1).lower()
    if brand_code is None:
        # items that subclass their own non-named base item (`: player_gear_back_a_01`) don't
        # redeclare myGearBrand at all -- fall back to this file's own top-of-file include,
        # which every branded item (named or not) carries regardless of inheritance.
        inc_m = re.search(r'include\s+"[^"]*gearbrand/gearbrand_([^."]+)\.mgearbrand"', text, re.IGNORECASE)
        if inc_m:
            brand_code = inc_m.group(1).lower()

    tags = re.findall(r'ItemTag\s+"[^"]*"\s+(\S+)', body)
    is_dz = any(t.startswith("Named_Item_DZ") or t.startswith("DZ_Elite_Boss_Drop") for t in tags)

    cfg_m = re.search(r'myItemGenerationConfig\s*<[^>]*>\s*=\s*(\S+)\s+([0-9A-Fa-f]+)', body)
    config_link_name = cfg_m.group(1) if cfg_m else None

    return {
        "instance_id": instance_id,
        "name": name,
        "description": description,
        "slot": slot,
        "brand_code": brand_code,
        "is_dz": is_dz,
        "config_link_name": config_link_name,
    }


# ---------------------------------------------------------------------------
# ItemGenerationConfig lookup (preset/fixed attributes + preset talent)
# ---------------------------------------------------------------------------

def _index_generation_configs(configs_dir, _cache={}):
    if not _cache:
        for path in glob.glob(os.path.join(configs_dir, "*.mitemgenerationconfigs")):
            text = open(path, encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'ItemGenerationConfig\s+(\S+)\s*(?::\s*\S+)?\s*\{', text):
                _cache.setdefault(m.group(1), (path, m.end() - 1))
    return _cache


def _load_config_body(configs_dir, config_name):
    hit = _index_generation_configs(configs_dir).get(config_name)
    if not hit:
        return None
    path, start = hit
    text_cache = _load_config_body.__dict__.setdefault("_text_cache", {})
    text = text_cache.get(path)
    if text is None:
        text = open(path, encoding='utf-8', errors='replace').read()
        text_cache[path] = text
    body, _ = extract_braced(text, start)
    return body


def find_generation_config_block(configs_dir, item_instance_id):
    """The declared name of a named item's ItemGenerationConfig is always the item's own
    instance id (lowercased '_' tokens) plus one extra 'config' token -- but WHERE that token
    goes is inconsistent across items/eras (`..._named_01_config`, `..._01_config_named`,
    `..._config_named_01`, etc. all occur in the wild). Rather than enumerate every ordering,
    match by token multiset: any declared config name whose '_'-split tokens equal the item id's
    tokens plus exactly one 'config' token is our config, regardless of where it sits."""
    direct = _load_config_body(configs_dir, item_instance_id + "_config")
    if direct is not None:
        return direct
    index = _index_generation_configs(configs_dir)
    # config declarations are case-inconsistent with the item id they belong to (e.g.
    # "Player_gear_chest_z_01_named_config" vs the item's own "player_gear_chest_z_01_named")
    target = tuple(sorted(t.lower() for t in item_instance_id.split('_') + ["config"]))
    for name in index:
        if tuple(sorted(t.lower() for t in name.split('_'))) == target:
            return _load_config_body(configs_dir, name)
    # last resort: at least one config name has a genuine authoring typo in the source data
    # (a doubled underscore merging "named" and "config" into one "_namedconfig" token) --
    # fall back to a char-level anagram check ignoring underscores/case entirely.
    target_chars = sorted((item_instance_id + "config").replace('_', '').lower())
    for name in index:
        if sorted(name.replace('_', '').lower()) == target_chars:
            return _load_config_body(configs_dir, name)
    return None


def _orange_quality_blocks(config_body, block_keyword):
    """Yield the body of every `<block_keyword> <label> { ... myQuality Orange ... }` block.
    The block's own <label> (its instance name, e.g. 'Orange' or 'Purple') is NOT reliable --
    several configs use a generic editor-default label instead (`"New QualityTalentSlots (0)"`,
    `"New QualityAttributeSlots (0)"`) even for the Orange-tier block, so anchoring the regex on
    a literal `Orange` label silently finds nothing for those files (looks identical to "no
    talent/attribute here" -- a real bug, not a data gap, until this generalized). Named items
    are always Orange quality, so filter by the `myQuality Orange` field *inside* the block
    instead of trusting its label."""
    for qm in re.finditer(block_keyword + r'\s+(?:"[^"]*"|\S+)\s*\{', config_body):
        body, _ = extract_braced(config_body, qm.end() - 1)
        if re.search(r'myQuality\s+Orange\b', body):
            yield body


def parse_preset_attributes(config_body):
    """Return list of {uid, is_core} for every ItemAttributeSlot with a myPresetAttribute,
    restricted to the Orange QualityAttributeSlots block (named items are always Orange)."""
    out = []
    for qbody in _orange_quality_blocks(config_body, "QualityAttributeSlots"):
        for sm in re.finditer(r'ItemAttributeSlot\s+(?:"[^"]*"|\S+)\s*\{', qbody):
            sbody, _ = extract_braced(qbody, sm.end() - 1)
            pa_m = re.search(r'myPresetAttribute\s+([0-9A-Fa-f]+)', sbody)
            if not pa_m:
                continue
            is_core = 'myIsCoreAttribute TRUE' in sbody
            pct_m = re.search(r'myPresetPercentage\s+([\-0-9.]+)', sbody)
            # a negative value (seen as -1.0) is a sentinel for "not actually preset here" even
            # though the field is present -- only a positive percentage means genuinely fixed.
            has_pct = bool(pct_m) and float(pct_m.group(1)) > 0
            out.append({
                "uid": pa_m.group(1),
                "is_core": is_core,
                "has_preset_percentage": has_pct,
            })
    return out


def parse_preset_talent(config_body):
    """`myPresetTalent < uid=... > = <slug> <guid>` -- same shape as a Gear Set's 4pc talent
    reference (`Talent "label" < uid=... > = <file_id> <guid>` in update_from_hunter_export.py),
    where the FIRST token after `=` is the .mtalent file's own instance-id/slug (what
    talent_index is keyed by) and the trailing hex GUID is a separate, unused identifier. Bug
    history: an earlier version of this function stored the GUID as "ref_file" and looked talents
    up by that instead of the slug, so the lookup could never hit -- every named-item talent
    looked "missing" even when its .mtalent file was sitting right there in the export, keyed
    under its slug. Verified against talent_gear_back_firecrackers.mtalent (Festive Delivery):
    present, fully parseable, just never found because of the swapped key."""
    for qbody in _orange_quality_blocks(config_body, "QualityTalentSlots"):
        pt_m = re.search(r'myPresetTalent\s*<[^>]*>\s*=\s*(\S+)\s+([0-9A-Fa-f]+)', qbody)
        if pt_m:
            return {"ref_file": pt_m.group(1)}
    return None


# ---------------------------------------------------------------------------
# Talent lookup (reuse the same .mtalent parser/format as gear-set 4pc talents)
# ---------------------------------------------------------------------------

def build_talent_index(raw_dir):
    talent_dir = os.path.join(raw_dir, "game system data", "juice", "talent")
    from update_from_hunter_export import parse_mtalent_file, naive_substitute
    index = {}
    for path in glob.glob(os.path.join(talent_dir, "*.mtalent")):
        parsed = parse_mtalent_file(path)
        if parsed:
            index[parsed["instance_id"]] = parsed
    return index, naive_substitute


DESC_TALENT_RE = re.compile(r'Talent:\s*([^\n]+)\n(.+)$', re.DOTALL)


def fallback_talent_from_description(description):
    if not description:
        return None
    m = DESC_TALENT_RE.search(description)
    if not m:
        return None
    return {"name": m.group(1).strip(), "desc": m.group(2).strip(), "source": "item_description"}


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_named_items(raw_dir, uid_dict, brand_names, brand_tiers, manual_overrides=None):
    item_dir = os.path.join(raw_dir, "game system data", "juice", "item")
    configs_dir = os.path.join(raw_dir, "game system data", "juice", "itemgeneration", "configs")
    talent_index, naive_substitute = build_talent_index(raw_dir)

    unresolved_uids = set()
    review_notes = []
    output = []

    paths = sorted(glob.glob(os.path.join(item_dir, "player_gear_*_named*.mitem")))
    for path in paths:
        entry = parse_named_item_file(path)
        if not entry or not entry["slot"]:
            review_notes.append(("STRUCTURAL", os.path.basename(path), "could not parse slot"))
            continue
        if not entry["name"]:
            # a handful of files (e.g. *_alpha / *_charlie campaign-tier variants) are pure
            # ArmorItem subclasses of another named item file with no myUIName of their own --
            # they inherit everything from that parent and add nothing new, so skip silently.
            continue

        override = (manual_overrides or {}).get(entry["instance_id"])
        if override and override.get("name"):
            review_notes.append(("MANUAL_OVERRIDE", entry["name"],
                                  "name replaced with manually-confirmed '%s' (%s)"
                                  % (override["name"], override.get("note", "no note"))))
            entry["name"] = override["name"]

        brand = brand_names.get(entry["brand_code"]) if entry["brand_code"] else None
        # Every named item is also a member of its civilian brand and gets that brand's normal
        # piece-count bonuses on top of its own "Fixed" attribute/talent -- e.g. Salvo (a Unit
        # Alloys holster) grants Unit Alloys' 2pc Assault Rifle Damage and 3pc Magazine Size the
        # same as any other Unit Alloys piece would, even though only Rate of Fire is Salvo's own
        # guaranteed "Fixed" stat. Carried through so the page can surface named items under a
        # search for those brand-level bonuses too, not just their unique Fixed one.
        brand_bonus_tiers = brand_tiers.get(entry["brand_code"], []) if entry["brand_code"] else []

        fixed_attrs = []
        talent = None
        talent_status = None

        config_body = find_generation_config_block(configs_dir, entry["instance_id"])
        if config_body is None:
            review_notes.append(("STRUCTURAL", entry["name"],
                                  "no ItemGenerationConfig found for '%s'" % entry["instance_id"]))
        else:
            for slot in parse_preset_attributes(config_body):
                if slot["is_core"] or not slot["has_preset_percentage"]:
                    continue
                if re.match(r'^0+$', slot["uid"]):
                    continue  # null/placeholder UID -- not a real attribute assignment
                stat = uid_dict.get(slot["uid"])
                if stat:
                    fixed_attrs.append(stat)
                else:
                    unresolved_uids.add(slot["uid"])
                    fixed_attrs.append("Unknown Attribute (%s)" % slot["uid"])

            preset_talent = parse_preset_talent(config_body)
            if preset_talent:
                t = talent_index.get(preset_talent["ref_file"])
                if t:
                    desc = strip_inline_markup(naive_substitute(t["tooltip"], t["values"]))
                    talent = {"name": strip_color_tags(t["ui_name"]) or "(unnamed)", "desc": desc}
                    talent_status = "datamined"
                else:
                    fb = fallback_talent_from_description(entry["description"])
                    if fb:
                        talent = {"name": fb["name"], "desc": fb["desc"]}
                        talent_status = "from_description_fallback"
                    else:
                        override_talent_name = (override or {}).get("talentName")
                        if override_talent_name:
                            # Talent NAME confirmed by the user from in-game knowledge (see
                            # named_items_manual_overrides.json) even though the .mtalent file
                            # itself -- and so the full description -- is still missing from
                            # every export seen so far. Keep talent_status as MISSING-equivalent
                            # ("manual_name_only") so the page still shows "full text not yet
                            # catalogued" instead of fabricating a description from the name.
                            talent = {"name": override_talent_name, "desc": None}
                            talent_status = "manual_name_only"
                            review_notes.append((
                                "MANUAL_OVERRIDE_TALENT_NAME", entry["name"],
                                "talent name manually confirmed as '%s' (file '%s.mtalent' still "
                                "missing from export; description remains unresolved)"
                                % (override_talent_name, preset_talent["ref_file"]),
                            ))
                        else:
                            talent_status = "MISSING"
                            review_notes.append((
                                "MISSING_TALENT", entry["name"],
                                "unique talent file '%s.mtalent' referenced but not present in "
                                "this export -- needs manual research" % preset_talent["ref_file"],
                            ))

        flavor = entry["description"]
        drop_note = None
        if flavor and re.search(r'Talent:\s*', flavor):
            # description doubles as mechanical notes (drop source / talent dump) rather than
            # pure flavor text -- keep the part before "Talent:" as the drop note, if any.
            head = flavor.split("Talent:")[0].strip()
            drop_note = head or None
            flavor = None

        source = "datamined" if talent_status != "from_description_fallback" else "datamined+description"
        if override and override.get("name"):
            source += "+manual_name_override"
        if talent_status == "manual_name_only":
            source += "+manual_talent_name_override"

        out = {
            "instance_id": entry["instance_id"],
            "name": entry["name"],
            "slot": entry["slot"],
            "brand": brand,
            "brandBonuses": brand_bonus_tiers,
            "isDarkZoneExclusive": entry["is_dz"],
            "flavorText": flavor,
            "dropNote": drop_note,
            "fixedAttributes": fixed_attrs,
            "talent": talent,
            "source": source,
        }
        if talent_status in ("MISSING", "manual_name_only"):
            # Also covers manual_name_only: the name is confirmed but desc is still None, so the
            # page's "full text not yet catalogued" placeholder should still render for it.
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
    combined_path = os.path.join(repo_dir, "data", "combined_sets.json")
    overrides_path = os.path.join(repo_dir, "tools", "named_items_manual_overrides.json")
    out_path = os.path.join(repo_dir, "data", "named_items.json")
    min_path = os.path.join(repo_dir, "data", "named_items_min.json")
    report_path = os.path.join(repo_dir, "tools", "named_items_report.md")

    uid_dict = json.load(open(uid_dict_path, encoding='utf-8'))
    combined = json.load(open(combined_path, encoding='utf-8'))
    manual_overrides = json.load(open(overrides_path, encoding='utf-8')) if os.path.exists(overrides_path) else {}
    brand_names = {}
    brand_tiers = {}
    for e in combined:
        if e["kind"] == "Brand":
            code = e["instance_id"].replace("gear_brand_set_", "").lower()
            brand_names[code] = e["name"]
            brand_tiers[code] = e["tiers"]

    items, unresolved, review_notes = build_named_items(args.raw_dir, uid_dict, brand_names, brand_tiers, manual_overrides)
    items.sort(key=lambda e: (e["slot"], e["name"]))

    json.dump(items, open(out_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(items, open(min_path, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)

    html_path = os.path.join(repo_dir, "index.html")
    min_json = open(min_path, encoding="utf-8").read()
    html = open(html_path, encoding="utf-8").read()
    new_line = "const NAMED_ITEMS = " + min_json + ";"
    # [^\n]* (never DOTALL .*) and a replacement *function* (never a plain string) are both
    # load-bearing -- see the matching comment in update_from_hunter_export.py's own DATA-embed
    # code, which had both bugs and was confirmed to have silently corrupted a committed
    # index.html before the fix: a DOTALL greedy match spans past this array's own line ending to
    # the LAST "];" in the file, and re.sub/re.subn interpret backslash escapes (\n, \g<...>) in a
    # *string* replacement, turning named items' legitimate literal "\n" flavor-text sequences
    # into real embedded newlines that break the JSON mid-array. This used to be a manual,
    # undocumented-gotcha re-embed step; doing it here the same safe way DATA already is removes
    # that whole failure mode.
    html2, n = re.subn(r"const NAMED_ITEMS = \[[^\n]*\];", lambda m: new_line, html, count=1)
    structural_notes = []
    if n == 1:
        open(html_path, "w", encoding="utf-8").write(html2)
    else:
        structural_notes.append(("STRUCTURAL", "index.html", "could not find 'const NAMED_ITEMS = [...]' to replace"))

    lines = []
    lines.append("# Named items extraction report\n")
    lines.append("Total named items found: %d\n" % len(items))
    with_talent = sum(1 for i in items if i["talent"])
    with_full_talent = sum(1 for i in items if i["talent"] and i["talent"].get("desc"))
    missing_talent = sum(1 for i in items if i.get("talentStatus") == "needs_manual_research")
    lines.append("With a talent name resolved: %d (full description: %d)" % (with_talent, with_full_talent))
    lines.append("Talent referenced but full description still needing manual research: %d\n" % missing_talent)
    all_notes = review_notes + structural_notes
    lines.append("## Review notes (%d)\n" % len(all_notes))
    for kind, name, detail in all_notes:
        lines.append("- [%s] %s: %s" % (kind, name, detail))
    lines.append("\n## Unresolved attribute UIDs (%d)\n" % len(unresolved))
    for uid in sorted(unresolved):
        lines.append("- %s" % uid)
    lines.append("\n## All items\n")
    for i in items:
        lines.append("- **%s** (%s%s)%s -- fixed: %s%s" % (
            i["name"], i["slot"],
            (", " + i["brand"]) if i["brand"] else "",
            " [DZ]" if i["isDarkZoneExclusive"] else "",
            ", ".join(i["fixedAttributes"]) or "(none found)",
            "  | talent: " + i["talent"]["name"] if i["talent"] else
            ("  | talent: MISSING (needs research)" if i.get("talentStatus") == "needs_manual_research" else ""),
        ))

    report = "\n".join(lines) + "\n"
    open(report_path, "w", encoding="utf-8").write(report)
    print("Wrote %d named items to %s" % (len(items), out_path))
    print("Re-embedded NAMED_ITEMS into %s" % html_path if n == 1 else "WARNING: index.html NOT updated -- see report")
    print("Report: %s" % report_path)


if __name__ == "__main__":
    main()
