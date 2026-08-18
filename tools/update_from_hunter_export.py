"""
Rebuild data/combined_sets.json (+ min) and re-inject into index.html from a fresh
Hunter "raw files" export of the game's Snowdrop game-system-data archives.

Usage:
    python tools/update_from_hunter_export.py --raw-dir "E:\\Temp\\Hunter\\raw_files\\hunter"

Run from anywhere; --repo-dir defaults to this script's grandparent (the repo root).
Never commits or pushes anything -- review the printed report and data/index.html
diff yourself, then commit as usual.
"""
import argparse
import glob
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# Low-level brace-aware parsing helpers (Snowdrop's text config format)
# ---------------------------------------------------------------------------

def extract_braced(s, start):
    """s[start] must be '{'. Returns (substring_including_braces, index_after_close).

    Quote-aware: braces inside a double-quoted string literal are ignored, since the
    export occasionally contains a literal (unescaped-for-our-purposes) '}' inside a
    text value -- e.g. Negotiator's Dilemma / Striker's Battlegear / Hunter's Fury all
    have myUIName values ending in the literal sequence \\"MenuLine\\"}" -- a naive
    brace counter closes the outer block right there, silently truncating everything
    (myUnlocks included) that follows."""
    depth = 0
    i = start
    string_quote = None  # '"' or "'" while inside a string literal, else None
    while i < len(s):
        c = s[i]
        # Some text fields nest another level of escaping on top of the field's own quoting
        # (e.g. a myDescription value containing `\\"..."` -- an escaped-backslash immediately
        # followed by a genuinely unescaped quote, one level deeper than usual) which desyncs a
        # simple single-level quote tracker: it reads that inner unescaped quote as closing the
        # *outer* myDescription string early, then everything after silently miscounts braces
        # until the file appears unbalanced (seen on 9 exotic-item files with an apostrophe +
        # escaped-backslash-quote combination in their flavor text). No field in this format
        # legitimately spans multiple lines, so a still-open string_quote at a newline is always
        # a mis-tracking artifact, never real data -- reset there rather than trying to correctly
        # model arbitrarily-nested escaping.
        if c == '\n':
            string_quote = None
        elif string_quote:
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


def extract_localized_text(field_line):
    """Given a line like myUIName "... text = \\"Some Name\\", type = ..." return the text value.
    The `text = ` value can be delimited either by a backslash-escaped quote of the same type as
    the enclosing field's own quotes (text=\\"...\\", the common case) or an unescaped quote of
    the *other* type (text='...', seen on Perfect-tier .mtalent files) -- same ambiguity already
    handled by extract_marked_value in extract_named_items.py; mirror that approach here rather
    than assume one delimiter style."""
    marker = "text " + chr(61) + " "  # text =
    i = field_line.find(marker)
    if i == -1:
        return None
    rest = field_line[i + len(marker):]
    if rest[:1] == chr(92):
        quote, opening_len = rest[1:2], 2
    else:
        quote, opening_len = rest[:1], 1
    if quote not in ('"', "'"):
        return None
    opening = rest[:opening_len]
    end = rest.find(opening + ", type", opening_len)
    if end == -1:
        end = rest.rfind(opening)
    if end < opening_len:
        return None
    raw = rest[opening_len:end]
    for q in ('"', "'"):
        raw = raw.replace(chr(92) + chr(92) + q, q).replace(chr(92) + q, q)
    return raw.replace(chr(92) + 'n', chr(10))


# ---------------------------------------------------------------------------
# .mgearset parsing (Brand Sets and Gear Sets)
# ---------------------------------------------------------------------------

def parse_mgearset_file(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'GearSet\s+(\S+)\s*<[^>]*>\s*(?::\s*\S+)?\s*\{', text)
    if not m:
        return None
    instance_id = m.group(1)
    body, _ = extract_braced(text, m.end() - 1)

    name_line_m = re.search(r'myUIName\s+"[^\n]*"', body)
    ui_name = None
    if name_line_m:
        raw = extract_localized_text(name_line_m.group(0))
        ui_name = raw.strip() if raw else None

    unlocks_m = re.search(r'myUnlocks\s*\{', body)
    tiers = []
    if unlocks_m:
        unlocks_body, _ = extract_braced(body, unlocks_m.end() - 1)
        for gm in re.finditer(r'GearSetUnlock\s+"[^"]*"\s*\{', unlocks_body):
            block, _ = extract_braced(unlocks_body, gm.end() - 1)
            req_m = re.search(r'myRequiredNumberOfItems\s+(\d+)', block)
            pieces = int(req_m.group(1)) if req_m else None
            eff_m = re.search(r'myEffects\s*\{', block)
            effects = []
            if eff_m:
                eff_body, _ = extract_braced(block, eff_m.end() - 1)
                for am in re.finditer(
                        r'myAttributeUID\s+([0-9A-Fa-f]+)\s+myValue\s+([\-0-9.]+)', eff_body):
                    effects.append({"type": "attr", "uid": am.group(1), "value": float(am.group(2))})
                for tm in re.finditer(
                        r'Talent\s+(?:"([^"]+)"|(\S+))\s*<[^>]*>\s*=\s*(\S+)\s+([0-9A-Fa-f]+)', eff_body):
                    ref_name = tm.group(1) if tm.group(1) is not None else tm.group(2)
                    effects.append({"type": "talent", "ref_name": ref_name, "ref_file": tm.group(3)})
            tiers.append({"pieces": pieces, "effects": effects})
    return {"instance_id": instance_id, "ui_name": ui_name, "tiers": tiers}


# ---------------------------------------------------------------------------
# .mtalent parsing (4pc / backpack / chest talents)
# ---------------------------------------------------------------------------

def parse_mtalent_file(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    # "Perfect"-tier talents subclass their base talent (`Talent <id> < uid=... > : <base_id>
    # { ... }`) instead of declaring a bare block -- the optional `: base_id` must be allowed or
    # the instance-id match silently fails on every one of them (106 files in one export).
    m = re.search(r'Talent\s+(\S+)\s*<[^>]*>\s*(?::\s*(\S+)\s*)?\{', text)
    if not m:
        return None
    instance_id = m.group(1)
    base_id = m.group(2)
    body, _ = extract_braced(text, m.end() - 1)

    name_line_m = re.search(r'myUIName\s+"[^\n]*"', body)
    ui_name = None
    if name_line_m:
        raw = extract_localized_text(name_line_m.group(0))
        ui_name = raw.strip() if raw else None

    tip_line_m = re.search(r'myToolTipText\s+[\'"][^\n]*[\'"]', body)
    tooltip = None
    if tip_line_m:
        # Reuse extract_localized_text rather than a second hand-rolled quote-delimiter parser --
        # a hand-rolled copy here only ever handled the "text = " value being delimited by an
        # unescaped quote of the *other* type (`text = '...'`), not an escaped quote of the *same*
        # type (`text = \"...`, equally common), which left every myToolTipText using the latter
        # style with a None tooltip (seen on Ferocious Calm's Perfect Overwatch, whose own
        # tooltip line is real and present but simply used that other, unhandled style).
        tooltip = extract_localized_text(tip_line_m.group(0))

    # base (non-PVP) myBonusList, in file order
    values = []
    bl_m = re.search(r'(?<!Override)myBonusList\s*\{', body)
    if bl_m:
        bl_body, _ = extract_braced(body, bl_m.end() - 1)
        for vm in re.finditer(r'myValue\s+([\-0-9.]+)', bl_body):
            values.append(float(vm.group(1)))

    # back-reference to a base talent (present only on backpack/chest companion talents).
    # Two forms seen in the wild: a machine-readable `myTalent <instance_id>` (case can
    # mismatch the target file's own declared case -- compare case-insensitively), or only
    # a human-readable `myText "... text = \"<Talent Display Name>\" ..."` with no id at all.
    requires_talent = None
    requires_talent_name = None
    req_m = re.search(r'myRequirements\s*\{', body)
    if req_m:
        req_body, _ = extract_braced(body, req_m.end() - 1)
        rt_m = re.search(r'myTalent\s+(\S+)', req_body)
        if rt_m:
            requires_talent = rt_m.group(1)
        rtext_line_m = re.search(r'myText\s+"[^\n]*"', req_body)
        if rtext_line_m:
            raw = extract_localized_text(rtext_line_m.group(0))
            requires_talent_name = raw.strip() if raw else None

    return {
        "instance_id": instance_id,
        "ui_name": ui_name,
        "tooltip": tooltip,
        "values": values,
        "requires_talent": requires_talent,
        "requires_talent_name": requires_talent_name,
        "base_id": base_id,
    }


def build_talent_index(raw_dir):
    """Parse every .mtalent file once; return {instance_id: parsed}."""
    talent_dir = os.path.join(raw_dir, "game system data", "juice", "talent")
    index = {}
    for path in glob.glob(os.path.join(talent_dir, "*.mtalent")):
        parsed = parse_mtalent_file(path)
        if parsed:
            index[parsed["instance_id"]] = parsed

    # A "Perfect"-tier talent's own file often carries no myToolTipText at all for the base/PvE
    # tier (only a myTalentOverrides > TalentOverride PVP > myOverrideToolTipText) -- it relies on
    # inheriting its parent's tooltip *template* via the `: base_id` subclass reference, only its
    # own myBonusList numbers actually change. Without this, such a talent resolves a real name
    # but a placeholder "(no tooltip text found)" description with no way to tell it apart from a
    # genuinely-missing one (seen on 5 of 62 named items' talents once the subclass-syntax fix
    # above started finding these files at all). Keep the child's own already-extracted `values`;
    # only borrow the parent's tooltip string.
    for entry in index.values():
        if entry["tooltip"] is None and entry.get("base_id"):
            base = index.get(entry["base_id"])
            if base and base["tooltip"] is not None:
                entry["tooltip"] = base["tooltip"]
    return index


def find_companions(talent_index, four_pc_instance_id, four_pc_ui_name):
    """Find backpack/chest talents that require the given 4pc talent, via their
    myRequirements back-reference. Classify by 'back'/'chest' substring in their
    own instance id (holds even when the base talent's filename is unrelated,
    e.g. Refactor's talent_gearset_backpack_over_engineered).

    Primary match: myTalent <instance_id> (case-insensitive -- the game data itself
    is inconsistent about case between a talent's own declaration and back-references
    to it, e.g. talent_gearset_Season08_4pc vs talent_gearset_season08_4pc).
    Fallback match: some companions omit the id and only carry a human-readable
    myText talent name -- compare that against the 4pc talent's own display name."""
    target_id = (four_pc_instance_id or "").lower()
    target_name = norm_name(four_pc_ui_name)
    backpack = None
    chest = None
    for tid, t in talent_index.items():
        matched = False
        if t.get("requires_talent") and t["requires_talent"].lower() == target_id:
            matched = True
        elif not t.get("requires_talent") and t.get("requires_talent_name") and target_name \
                and norm_name(t["requires_talent_name"]) == target_name:
            matched = True
        if not matched:
            continue
        low = tid.lower()
        if "chest" in low:
            chest = t
        elif "back" in low:
            backpack = t
    return backpack, chest


# ---------------------------------------------------------------------------
# Attribute UID resolution + formatting
# ---------------------------------------------------------------------------

def fmt_val(stat, v):
    if stat == "Skill Tier":
        return "+%d Skill Tier" % int(round(v))
    return "+%s%% %s" % (("%g" % round(v * 100, 2)), stat)


def decode_tiers(entry, uid_dict, unresolved, allowed_pieces=None):
    out = []
    for t in entry["tiers"]:
        if allowed_pieces and t["pieces"] not in allowed_pieces:
            continue
        for eff in t["effects"]:
            if eff["type"] != "attr":
                continue
            name = uid_dict.get(eff["uid"])
            if name:
                out.append({"pieces": t["pieces"], "stat": name, "text": fmt_val(name, eff["value"])})
            else:
                unresolved.add(eff["uid"])
                out.append({
                    "pieces": t["pieces"], "stat": "Unknown Attribute",
                    "text": "+%s%% (unresolved attribute %s)" % ("%g" % round(eff["value"] * 100, 2), eff["uid"]),
                })
    return out


def naive_substitute(template, values):
    if not template:
        return "(no tooltip text found)"
    def repl(m):
        idx = int(m.group(1))
        if idx >= len(values):
            return m.group(0)
        v = values[idx]
        if abs(v) < 5:
            num = "%g" % round(v * 100, 2)
            # Some templates already carry their own literal "%" right after the placeholder
            # (e.g. Perfect-tier talents: "...by {0}%..."); appending another produced "7%%".
            # No pre-existing gear-set talent template does both (0 "%%" in combined_sets today),
            # so this only changes output for templates that already supply their own "%".
            if template[m.end():m.end() + 1] == '%':
                return num
            return num + "%"
        return "%g" % v
    return re.sub(r'\{(\d+)\}', repl, template)


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------

def norm_name(name):
    if not name:
        return ""
    return re.sub(r'[^a-z0-9]+', '', name.strip().lower().replace("&", "and"))


def build_talent_field(role_key, four_pc_talent, companion, old_by_key, join_key, uid_dict, unresolved):
    """role_key: 'talent4' | 'backpackTalent' | 'chestTalent'. Returns dict or None."""
    if companion is None and role_key == "talent4":
        t = four_pc_talent
    else:
        t = companion

    old_entry = old_by_key.get(join_key)
    old_talent = (old_entry or {}).get(role_key)

    if t is None:
        if old_talent:
            # file referenced/expected but missing from this export -- keep the last
            # trusted value rather than silently deleting it; the caller already logs
            # a STRUCTURAL/MISSING_FILE warning for this.
            kept = dict(old_talent)
            kept.pop("_values", None)
            return kept, "kept_stale"
        return None, None

    fresh_values = t["values"]

    if old_talent and old_talent.get("_values") == fresh_values:
        # unchanged since last run -- keep hand-written text as-is
        return {"name": old_talent["name"], "desc": old_talent["desc"], "_values": fresh_values}, "unchanged"
    elif old_talent and "_values" not in old_talent:
        # bootstrap: no prior fingerprint recorded, trust the existing hand-written text once
        return {"name": old_talent["name"], "desc": old_talent["desc"], "_values": fresh_values}, "bootstrapped"
    else:
        # new or changed -- best-effort draft, needs review
        desc = naive_substitute(t["tooltip"], fresh_values)
        return {
            "name": t["ui_name"] or "(unnamed)",
            "desc": desc,
            "_values": fresh_values,
            "needs_review": True,
        }, ("changed" if old_talent else "new")


def build_dataset(raw_dir, uid_dict, old_by_key, used_name_fallback):
    item_dir = os.path.join(raw_dir, "game system data", "juice", "item")
    talent_index = build_talent_index(raw_dir)
    unresolved = set()
    review_notes = []
    output = []

    for path in sorted(glob.glob(os.path.join(item_dir, "gear_brand_set_*.mgearset"))):
        if "template" in path:
            continue
        entry = parse_mgearset_file(path)
        if not entry or not entry["ui_name"]:
            review_notes.append(("STRUCTURAL", os.path.basename(path), "could not parse name/tiers"))
            continue
        tiers = decode_tiers(entry, uid_dict, unresolved)
        output.append({
            "instance_id": entry["instance_id"],
            "name": entry["ui_name"].strip(),
            "kind": "Brand",
            "tiers": tiers,
            "source": "datamined",
        })

    for path in sorted(glob.glob(os.path.join(item_dir, "gear_set_*.mgearset"))):
        if "template" in path:
            continue
        entry = parse_mgearset_file(path)
        if not entry or not entry["ui_name"]:
            review_notes.append(("STRUCTURAL", os.path.basename(path), "could not parse name/tiers"))
            continue
        tiers = decode_tiers(entry, uid_dict, unresolved, allowed_pieces={2, 3})
        out = {
            "instance_id": entry["instance_id"],
            "name": entry["ui_name"].strip(),
            "kind": "Gear Set",
            "tiers": tiers,
            "source": "datamined",
        }

        talent_tier = next((t for t in entry["tiers"] if t["pieces"] == 4), None)
        four_pc_ref = None
        if talent_tier:
            four_pc_ref = next((e for e in talent_tier["effects"] if e["type"] == "talent"), None)

        join_key = norm_name(entry["ui_name"]) if used_name_fallback else entry["instance_id"]

        if four_pc_ref is None:
            review_notes.append(("STRUCTURAL", entry["ui_name"], "no 4pc Talent reference found"))
        else:
            four_pc_talent = talent_index.get(four_pc_ref["ref_file"])
            if four_pc_talent is None:
                old_entry = old_by_key.get(join_key) or {}
                kept_any = False
                for role_key in ("talent4", "backpackTalent", "chestTalent"):
                    if role_key in old_entry:
                        kept = dict(old_entry[role_key])
                        kept.pop("_values", None)
                        out[role_key] = kept
                        kept_any = True
                review_notes.append((
                    "MISSING_FILE", entry["ui_name"],
                    "4pc talent file '%s.mtalent' referenced but not present in this export"
                    % four_pc_ref["ref_file"] + (" (kept last known talent values)" if kept_any else ""),
                ))
            else:
                backpack, chest = find_companions(talent_index, four_pc_talent["instance_id"], four_pc_talent["ui_name"])

                t4, status4 = build_talent_field("talent4", four_pc_talent, None, old_by_key, join_key, uid_dict, unresolved)
                if t4:
                    out["talent4"] = t4
                    if status4 in ("new", "changed"):
                        review_notes.append(("TALENT_REVIEW", entry["ui_name"] + " (4pc)", status4))

                if backpack is None:
                    review_notes.append(("STRUCTURAL", entry["ui_name"],
                                          "no backpack talent companion found in this export"
                                          + (" (kept last known value)" if old_by_key.get(join_key, {}).get("backpackTalent") else "")))
                tb, statusb = build_talent_field("backpackTalent", four_pc_talent, backpack, old_by_key, join_key, uid_dict, unresolved)
                if tb:
                    out["backpackTalent"] = tb
                    if statusb in ("new", "changed"):
                        review_notes.append(("TALENT_REVIEW", entry["ui_name"] + " (backpack)", statusb))

                if chest is None:
                    review_notes.append(("STRUCTURAL", entry["ui_name"],
                                          "no chest talent companion found in this export"
                                          + (" (kept last known value)" if old_by_key.get(join_key, {}).get("chestTalent") else "")))
                tc, statusc = build_talent_field("chestTalent", four_pc_talent, chest, old_by_key, join_key, uid_dict, unresolved)
                if tc:
                    out["chestTalent"] = tc
                    if statusc in ("new", "changed"):
                        review_notes.append(("TALENT_REVIEW", entry["ui_name"] + " (chest)", statusc))

        output.append(out)

    return output, unresolved, review_notes


# ---------------------------------------------------------------------------
# Diffing against the previous committed dataset
# ---------------------------------------------------------------------------

def load_old_dataset(path):
    if not os.path.exists(path):
        return [], {}
    data = json.load(open(path, encoding='utf-8'))
    has_instance_ids = bool(data) and all("instance_id" in e for e in data)
    by_key = {}
    for e in data:
        key = e["instance_id"] if has_instance_ids else norm_name(e["name"])
        by_key[key] = e
    return data, by_key


def tier_map(entry):
    m = {}
    for t in entry["tiers"]:
        m.setdefault(t["pieces"], []).append(t["text"])
    return m


def diff_datasets(old_list, old_by_key, new_list, used_name_fallback):
    old_keys = set(old_by_key.keys())
    new_by_key = {}
    for e in new_list:
        key = e["instance_id"] if not used_name_fallback else norm_name(e["name"])
        new_by_key[key] = e
    new_keys = set(new_by_key.keys())

    added = [new_by_key[k] for k in sorted(new_keys - old_keys)]
    removed = [old_by_key[k] for k in sorted(old_keys - new_keys)]
    changed = []
    for k in sorted(new_keys & old_keys):
        old_e, new_e = old_by_key[k], new_by_key[k]
        old_tm, new_tm = tier_map(old_e), tier_map(new_e)
        if old_tm != new_tm:
            changed.append((new_e["name"], old_tm, new_tm))
    return added, removed, changed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", required=True, help='Path to the exported "hunter" folder from Hunter raw-file export')
    ap.add_argument("--repo-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()

    repo_dir = args.repo_dir
    data_path = os.path.join(repo_dir, "data", "combined_sets.json")
    min_path = os.path.join(repo_dir, "data", "combined_sets_min.json")
    html_path = os.path.join(repo_dir, "index.html")
    uid_dict_path = os.path.join(repo_dir, "tools", "attribute_uid_dictionary.json")
    report_path = os.path.join(repo_dir, "tools", "last_update_report.md")

    uid_dict = json.load(open(uid_dict_path, encoding='utf-8'))
    old_list, old_by_key = load_old_dataset(data_path)
    used_name_fallback = bool(old_list) and not all("instance_id" in e for e in old_list)

    new_list, unresolved, review_notes = build_dataset(args.raw_dir, uid_dict, old_by_key, used_name_fallback)
    new_list.sort(key=lambda e: (e["kind"], e["name"]))

    added, removed, changed = diff_datasets(old_list, old_by_key, new_list, used_name_fallback)

    json.dump(new_list, open(data_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(new_list, open(min_path, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)

    min_json = open(min_path, encoding="utf-8").read()
    html = open(html_path, encoding="utf-8").read()
    new_line = "const DATA = " + min_json + ";"
    # [^\n]* (not DOTALL .*) is load-bearing: DATA and NAMED_ITEMS are each single minified-JSON
    # lines back to back. A DOTALL `.*` greedily matches past DATA's own line ending straight
    # through to the LAST "];" in the file -- i.e. NAMED_ITEMS's own closing bracket -- silently
    # deleting the entire NAMED_ITEMS array on every run. Confirmed this actually happened to a
    # committed index.html before this fix; excluding newlines from the match makes that bug
    # structurally impossible regardless of what else follows DATA in the file.
    # A plain-string replacement is also load-bearing: re.sub/subn interpret backslash escapes
    # (\n, \g<...>, etc.) INSIDE a string replacement, same as a raw regex pattern would -- so any
    # dataset text containing a literal `\n` (a multi-line talent tooltip, say) would silently
    # turn into a real embedded newline in the page, corrupting the JSON. A replacement *function*
    # is inserted verbatim with no escape processing, which is what we actually want here.
    html2, n = re.subn(r"const DATA = \[[^\n]*\];", lambda m: new_line, html, count=1)
    if n == 1:
        open(html_path, "w", encoding="utf-8").write(html2)
    else:
        review_notes.append(("STRUCTURAL", "index.html", "could not find 'const DATA = [...]' to replace"))

    # -- report --
    lines = []
    lines.append("# Update report\n")
    lines.append("Total entries: %d\n" % len(new_list))
    lines.append("## Added (%d)\n" % len(added))
    for e in added:
        lines.append("- %s (%s)" % (e["name"], e["kind"]))
    lines.append("\n## Removed (%d)\n" % len(removed))
    for e in removed:
        lines.append("- %s (%s)" % (e["name"], e["kind"]))
    lines.append("\n## Changed bonus values (%d)\n" % len(changed))
    for name, old_tm, new_tm in changed:
        lines.append("- **%s**" % name)
        pieces = sorted(set(old_tm.keys()) | set(new_tm.keys()))
        for p in pieces:
            ov, nv = old_tm.get(p, []), new_tm.get(p, [])
            if ov != nv:
                lines.append("  - %dpc: %s -> %s" % (p, ov, nv))
    lines.append("\n## Talents needing review (%d)\n" % sum(1 for n in review_notes if n[0] == "TALENT_REVIEW"))
    for kind, name, detail in review_notes:
        if kind == "TALENT_REVIEW":
            lines.append("- %s: %s" % (name, detail))
    lines.append("\n## Unresolved attribute UIDs (%d)\n" % len(unresolved))
    for uid in sorted(unresolved):
        lines.append("- %s -- add its stat name to tools/attribute_uid_dictionary.json" % uid)
    lines.append("\n## Structural warnings (%d)\n" % sum(1 for n in review_notes if n[0] in ("STRUCTURAL", "MISSING_FILE")))
    for kind, name, detail in review_notes:
        if kind in ("STRUCTURAL", "MISSING_FILE"):
            lines.append("- [%s] %s: %s" % (kind, name, detail))

    report = "\n".join(lines) + "\n"
    open(report_path, "w", encoding="utf-8").write(report)
    print(report)

    if unresolved or any(n[0] in ("STRUCTURAL", "MISSING_FILE") for n in review_notes):
        print("\n>>> ACTION NEEDED before trusting this output -- see unresolved/structural sections above.", file=sys.stderr)


if __name__ == "__main__":
    main()
