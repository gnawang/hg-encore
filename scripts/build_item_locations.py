#!/usr/bin/env python3
# Writes scripts/item_locations.json: where each item lies in the field (item balls and hidden items) and which places'
# people give it, for the reference pages. It reads a pret/pokeheartgold checkout, which isn't part of this repo, so the
# JSON is committed and only needs regenerating if items move. Run from the repo root:
#
#   python3 scripts/build_item_locations.py path/to/pokeheartgold
#
# Item IDs are pret's, which hg-engine keeps for every HeartGold item. Encore's own maps in data/eventdata/zone_event/
# only hide HM obstacles, so pret's maps are the right source for items.
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from build_reference_docs import encounter_area_name  # noqa: E402
from build_trainer_locations import group_place, read_map_names  # noqa: E402

OUTPUT = "scripts/item_locations.json"
ITEM_BALL_BASE = 7000
HIDDEN_ITEM_BASE = 8000
GIVE_CALLS = ("std_give_item_verbose", "std_obtain_item_verbose")
# maps that copy another map's items: National Park during the Bug-Catching Contest, and the Japanese version's Game Corner
DUPLICATE_MAPS = {"National Park Bug Catching Contest", "Goldenrod Game Corner Jp"}


def read_item_constants(pret):
    # ITEM_* and the TM_*/HM_* aliases, as numbers
    text = open(os.path.join(pret, "include/constants/items.h")).read()
    values = {name: int(value) for name, value in re.findall(r"#define ((?:ITEM|TM|HM)_\w+)\s+(\d+)\b", text)}
    for name, alias in re.findall(r"#define ((?:ITEM|TM|HM)_\w+)\s+((?:ITEM|TM|HM)_\w+)\b", text):
        if alias in values:
            values[name] = values[alias]
    return values


def resolve(value, items):
    value = value.strip()
    return int(value) if value.isdigit() else items.get(value)


def main():
    pret = sys.argv[1]
    items = read_item_constants(pret)
    std = {name: int(value) for name, value in re.findall(r"#define (std_\w+)\s+(\d+)", open(os.path.join(pret, "include/constants/std_script.h")).read())}
    map_names = read_map_names(pret)
    areas = {}
    for key in re.findall(r"^    \[(ENCDATA_\w+)\] = \{", open("data/Encounters.c").read(), re.M):
        areas.setdefault(re.match(r"ENCDATA_([A-Z0-9]+)_", key).group(1), encounter_area_name(key))

    def place(code):
        return group_place(areas.get(code) or map_names.get(code, code))

    # item ball script n: SetVar VAR_SPECIAL_x8008 (item) and x8009 (quantity)
    balls = {}
    ball_text = open(os.path.join(pret, "files/fielddata/script/scr_seq/scr_seq_0141.s")).read()
    for number, body in re.findall(r"^scr_seq_0141_(\d+):\n(.*?)\n\tGoTo", ball_text, re.M | re.S):
        item = re.search(r"VAR_SPECIAL_x8008, (\w+)", body)
        count = re.search(r"VAR_SPECIAL_x8009, (\d+)", body)
        if item:
            balls[ITEM_BALL_BASE + int(number)] = (resolve(item.group(1), items), int(count.group(1)) if count else 1)

    # hidden item n: the sHiddenItemParam entry whose index is n
    hidden = {}
    table = open(os.path.join(pret, "src/data/fieldmap/hidden_items.h")).read()
    for item, count, index in re.findall(r"\{ (ITEM_\w+),\s*(\d+), \d+, \d+, (\d+)\s*\}", table):
        hidden[HIDDEN_ITEM_BASE + int(index)] = (items.get(item), int(count))

    found = {}

    def add(item, where, how, count):
        if item:
            found.setdefault(item, []).append([where, how, count])

    for path in sorted(glob.glob(os.path.join(pret, "files/fielddata/eventdata/zone_event/*.json"))):
        code = re.match(r"\d+_(\w+)\.json", os.path.basename(path)).group(1)
        events = json.load(open(path))
        for obj in events.get("objects", []):
            number = std.get(str(obj.get("scriptId", "")).strip())
            if number in balls:
                add(balls[number][0], place(code), "Item ball", balls[number][1])
        for bg in events.get("bgs", []):
            number = std.get(str(bg.get("scriptId", "")).strip())
            if number in hidden:
                add(hidden[number][0], place(code), "Hidden", hidden[number][1])

    # People who give items, in each map's own scripts: GiveItemNoCheck ITEM, n, or a give call after the item is named,
    # by GoToIfNoItemSpace ITEM, n (which also sets it up) or SetVar VAR_SPECIAL_x8004, ITEM
    for path in sorted(glob.glob(os.path.join(pret, "files/fielddata/script/scr_seq/scr_seq_*.s"))):
        match = re.match(r"scr_seq_\d+_(\w+)\.s", os.path.basename(path))
        if not match:  # shared scripts with no map
            continue
        where = place(match.group(1))
        lines = open(path).read().split("\n")
        # Battle Point exchanges, in the Battle Frontier only, set the item, quantity and BP price together. The count is the BP price.
        for item, _, points in [] if match.group(1) != "D32" else re.findall(r"SetVar VAR_SPECIAL_x8004, (\w+)\n\tSetVar VAR_SPECIAL_x8005, (\d+)\n\tSetVar VAR_SPECIAL_x8006, (\d+)", "\n".join(lines)):
            add(resolve(item, items), where, "BP", int(points))
        for number, line in enumerate(lines):
            direct = re.match(r"\s*GiveItemNoCheck (\w+), (\d+)", line)
            if direct:
                add(resolve(direct.group(1), items), where, "Gift", int(direct.group(2)))
            # Game Corner prizes: GoToIfNoItemSpace ITEM, then TakeCoins N, then GiveItem VAR_SPECIAL_x8004. The count is the coin price.
            if re.match(r"\s*GiveItem VAR_SPECIAL_x8004,", line):
                coins = item = None
                for back in range(number - 1, max(number - 30, -1), -1):
                    coins = coins or re.match(r"\s*TakeCoins (\d+)", lines[back])
                    item = re.match(r"\s*GoToIfNoItemSpace (\w+), \d+,", lines[back])
                    if item:
                        break
                if item and coins:
                    add(resolve(item.group(1), items), where, "Prize", int(coins.group(1)))
            if any("CallStd " + call in line for call in GIVE_CALLS):
                for back in range(number - 1, max(number - 12, -1), -1):
                    space = re.match(r"\s*GoToIfNoItemSpace (\w+), (\d+),", lines[back])
                    setter = re.match(r"\s*SetVar VAR_SPECIAL_x8004, (\w+)", lines[back])
                    if space:
                        add(resolve(space.group(1), items), where, "Gift", int(space.group(2)))
                        break
                    if setter:
                        # A gift that depends on the version (GetGameVersion, Compare 7, GoToIfNe) sets the HeartGold item first
                        version = next((v for v in range(back - 1, max(back - 12, -1), -1) if "GetGameVersion" in lines[v]), None)
                        if version is not None:
                            setter = next(m for m in (re.match(r"\s*SetVar VAR_SPECIAL_x8004, (\w+)", x) for x in lines[version:back + 1]) if m)
                        count = re.search(r"SetVar VAR_SPECIAL_x8005, (\d+)", "\n".join(lines[back:number]))
                        add(resolve(setter.group(1), items), where, "Gift", int(count.group(1)) if count else 1)
                        break

    out = {}
    for item, entries in found.items():
        merged = {}
        for where, how, count in entries:
            if where in DUPLICATE_MAPS:
                continue
            key = (where, how)
            # several item balls in one place add up; a gift found on two script branches is still one gift
            merged[key] = max(merged.get(key, 0), count) if how in ("Gift", "Prize", "BP") else merged.get(key, 0) + count
        out[str(item)] = [[where, how, count] for (where, how), count in sorted(merged.items())]
    with open(OUTPUT, "w", encoding="utf-8") as target:
        json.dump({k: out[k] for k in sorted(out, key=int)}, target, indent=1, ensure_ascii=False)
        target.write("\n")
    print("Wrote %s with %d items in %d places" % (OUTPUT, len(out), sum(len(v) for v in out.values())))


if __name__ == "__main__":
    main()
