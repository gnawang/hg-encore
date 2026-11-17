#!/usr/bin/env python3
"""Rebuild every roster Pokémon's level-up moves in data/learnsets/base/custom.json. See Learnsets in documentation/ENCORE_CHANGES.md.

1. HeartGold's level-up moves are the base, at HeartGold's levels.
2. Moves the Pokémon learns by level-up in Scarlet/Violet or Legends Z-A are added at their Scarlet/Violet level, else their Z-A level.
   An evolved Pokémon's level-1 moves in those games that only repeat a pre-evolution's moves aren't added.
3. A short list of critical moves the Pokémon can't otherwise learn (CRITICAL) is added.
Then the level rules run:
- An attack too strong for its level moves later, by effective power (multi-hit moves count three hits, two-hit moves two).
  A HeartGold move never moves past HeartGold's own level for it. Fixed-damage moves have a minimum level, HeartGold's included.
  Added recovery and setup moves have a minimum level. A Pokémon's earliest possible level (from evolution) counts.
- An added attack is dropped when the Pokémon already learns a same-type, same-category attack at least as strong within 3 levels,
  with no drawback. An added status move is dropped when one with the same effect is already learned. HeartGold's moves and
  CRITICAL moves are never dropped.
- Added moves that land on a level already taken move up to the next free level, at most 3 later, to spread the moves out.

Run from the repo root: python3 scripts/build_level_moves.py [--write] [SPECIES_X ...]
It prints what it would build; --write saves custom.json. Egg moves aren't touched. Then regenerate learnsets.json (see ENCORE_CHANGES.md).
"""
import re, json, sys, collections

CUSTOM = 'data/learnsets/base/custom.json'
custom = json.load(open(CUSTOM))
games = {name: json.load(open('data/learnsets/base/%s.json' % name)) for name in ('10_hgss', '21_sv', '22_za')}
config = dict(re.findall(r'#define (\w+) +(\d+)', open('include/config.h').read()))

# moves hg-engine hasn't implemented are left out; Rage Fist becomes Shadow Punch
REPLACE = {'MOVE_RAGE_FIST': 'MOVE_SHADOW_PUNCH'}

CRITICAL = {  # (species, move): level before the level rules. Moves nothing else in the game teaches, key to the Pokémon's usual set
    'MORNING_SUN': {'ARCANINE': 1, 'RAPIDASH': 1, 'SUNFLORA': 1},
    'STRENGTH_SAP': {'VILEPLUME': 1, 'BELLOSSOM': 1, 'VICTREEBEL': 1, 'JUMPLUFF': 1},
    'WISH': {'CLEFABLE': 1}, 'RECOVER': {'QUAGSIRE': 20}, 'PAIN_SPLIT': {'DUSCLOPS': 40, 'DUSKNOIR': 40},
    'FAKE_OUT': {'RAICHU': 1, 'MEDICHAM': 1, 'INFERNAPE': 1, 'AMBIPOM': 1, 'LOPUNNY': 1, 'TOXICROAK': 1, 'WEAVILE': 1},
    'MACH_PUNCH': {'HITMONTOP': 1}, 'BULLET_PUNCH': {'HITMONTOP': 1, 'HARIYAMA': 1}, 'ICE_SHARD': {'DONPHAN': 1},
    'AQUA_JET': {'CRAWDAUNT': 1, 'AZUMARILL': 24}, 'SUCKER_PUNCH': {'ARBOK': 32}, 'EXTREME_SPEED': {'LINOONE': 52},
    'BELLY_DRUM': {'AZUMARILL': 50}, 'SHELL_SMASH': {'TORTERRA': 50, 'GOREBYSS': 30, 'HUNTAIL': 30},
    'RAPID_SPIN': {'TENTACRUEL': 1, 'KABUTOPS': 1, 'ARMALDO': 1, 'CLOYSTER': 1}, 'SPORE': {'BRELOOM': 30},
    'ROCK_BLAST': {'CLOYSTER': 1}, 'FIRE_FANG': {'LUXRAY': 1}, 'ICE_FANG': {'LUXRAY': 1}, 'FREEZE_DRY': {'LAPRAS': 42},
    'ICICLE_CRASH': {'MAMOSWINE': 30, 'WEAVILE': 36}, 'TRIPLE_AXEL': {'WEAVILE': 46}, 'MOONBLAST': {'MEGANIUM': 48},
}
CRITICAL = {('SPECIES_' + s, 'MOVE_' + m): lv for m, d in CRITICAL.items() for s, lv in d.items()}

# Moves Legends Z-A gives only for a Mega's ability or new type. Encore has no Mega Evolution, so they're removed:
# from level-up unless HeartGold teaches the move by level-up, and from TM compatibility unless a game other than Z-A gives it.
MEGA_ONLY = {
    'HERACROSS': ['ROCK_BLAST'],                                        # Skill Link
    'STARYU': ['AQUA_JET'],                                             # Huge Power (Mega Starmie is a physical attacker)
    'STARMIE': ['AQUA_JET', 'TAKE_DOWN', 'LIQUIDATION', 'TRIPLE_AXEL', 'BULK_UP'],
    'PINSIR': ['TAKE_DOWN', 'AERIAL_ACE', 'DUAL_WINGBEAT'],             # Aerilate, Bug/Flying
    'GLALIE': ['EXPLOSION'],                                            # Refrigerate
    'CHARMANDER': ['DRAGON_RUSH'], 'CHARMELEON': ['DRAGON_RUSH'], 'CHARIZARD': ['DRAGON_RUSH'],  # Mega Charizard X, Fire/Dragon
    'CLEFABLE': ['AIR_SLASH'],                                          # Fairy/Flying
    'ABSOL': ['SHADOW_SNEAK', 'PHANTOM_FORCE', 'CONFUSE_RAY', 'SHADOW_CLAW'],  # Mega Absol Z, Dark/Ghost
}
MEGA_ONLY = {('SPECIES_' + s, 'MOVE_' + m) for s, ms in MEGA_ONLY.items() for m in ms}


def cfg(v):
    m = re.fullmatch(r'\(\((\w+)\) \? \((\w+)\) : \((\w+)\)\)', v.strip())
    return (m.group(2) if config.get(m.group(1), '0') != '0' else m.group(3)) if m else v.strip()


moves, unimplemented = {}, set()
for key, body in re.findall(r'\n    \[(MOVE_\w+)\] = \{(.*?)\n    \},', open('data/Moves.c').read(), re.S):
    if 'FLAG_UNUSABLE_UNIMPLEMENTED' in body:
        unimplemented.add(key)
    g = lambda f: cfg(re.search(r'\.' + f + r' = ([^\n]+),\n', body).group(1))
    try:
        moves[key] = dict(effect=g('effect'), split=g('split'), power=int(g('power')), type=g('type'), priority=int(g('priority')),
                          accuracy=int(g('accuracy')))
    except AttributeError:
        pass

FIXED = {'MOVE_SONIC_BOOM': 20, 'MOVE_DRAGON_RAGE': 25, 'MOVE_SEISMIC_TOSS': 15, 'MOVE_NIGHT_SHADE': 15, 'MOVE_PSYWAVE': 25,
         'MOVE_SUPER_FANG': 25, 'MOVE_ENDEAVOR': 25, 'MOVE_FINAL_GAMBIT': 30}
VARIABLE = {'MOVE_LOW_KICK': 60, 'MOVE_GRASS_KNOT': 60, 'MOVE_HEAVY_SLAM': 80, 'MOVE_HEAT_CRASH': 80, 'MOVE_GYRO_BALL': 80,
            'MOVE_ELECTRO_BALL': 70, 'MOVE_RETURN': 80, 'MOVE_FRUSTRATION': 80, 'MOVE_FLAIL': 60, 'MOVE_REVERSAL': 60,
            'MOVE_WRING_OUT': 80, 'MOVE_CRUSH_GRIP': 80, 'MOVE_PUNISHMENT': 60, 'MOVE_TRUMP_CARD': 60, 'MOVE_NATURAL_GIFT': 60,
            'MOVE_FLING': 50, 'MOVE_MAGNITUDE': 70, 'MOVE_PRESENT': 40, 'MOVE_BEAT_UP': 40, 'MOVE_SPIT_UP': 60,
            'MOVE_ROLLOUT': 50, 'MOVE_ICE_BALL': 50, 'MOVE_STORED_POWER': 60, 'MOVE_POWER_TRIP': 60, 'MOVE_TRIPLE_KICK': 60,
            'MOVE_TRIPLE_AXEL': 100, 'MOVE_FURY_CUTTER': 50}
REACTIVE = {'MOVE_COUNTER', 'MOVE_MIRROR_COAT', 'MOVE_METAL_BURST', 'MOVE_COMEUPPANCE', 'MOVE_BIDE'}
RECOVERY = {'MOVE_RECOVER', 'MOVE_ROOST', 'MOVE_SOFT_BOILED', 'MOVE_MILK_DRINK', 'MOVE_SLACK_OFF', 'MOVE_SYNTHESIS', 'MOVE_MOONLIGHT',
            'MOVE_MORNING_SUN', 'MOVE_SHORE_UP', 'MOVE_STRENGTH_SAP', 'MOVE_WISH', 'MOVE_HEAL_ORDER', 'MOVE_LIFE_DEW', 'MOVE_PAIN_SPLIT'}
SETUP = {'MOVE_SWORDS_DANCE', 'MOVE_DRAGON_DANCE', 'MOVE_NASTY_PLOT', 'MOVE_CALM_MIND', 'MOVE_BULK_UP', 'MOVE_QUIVER_DANCE',
         'MOVE_SHELL_SMASH', 'MOVE_BELLY_DRUM', 'MOVE_COIL', 'MOVE_SHIFT_GEAR', 'MOVE_TAIL_GLOW', 'MOVE_VICTORY_DANCE', 'MOVE_TIDY_UP',
         'MOVE_GROWTH', 'MOVE_WORK_UP', 'MOVE_HONE_CLAWS', 'MOVE_ROCK_POLISH', 'MOVE_AGILITY', 'MOVE_COTTON_GUARD'}
POWER_LEVELS = ((40, 1), (50, 8), (60, 14), (70, 20), (80, 26), (90, 32), (100, 38), (110, 42), (120, 46))
OHKO_LEVEL, RECOVERY_LEVEL, SETUP_LEVEL = 35, 20, 30
WINDOW = 3

DROPPABLE = re.compile(r'MOVE_EFFECT_(HIT|FLINCH_HIT|BURN_HIT|FREEZE_HIT|PARALYZE_HIT|POISON_HIT|CONFUSE_HIT|LOWER_\w+_HIT|HIGH_CRITICAL\w*|MULTI_HIT|HIT_TWICE)$')
# a move only counts as the better option if it has no drawback: no recoil, lock-in, charge turn, crash or stat drop on the user
DOMINATOR = re.compile(r'MOVE_EFFECT_(HIT|FLINCH_HIT|BURN_HIT|FREEZE_HIT|PARALYZE_HIT|POISON_HIT|CONFUSE_HIT|LOWER_\w+_HIT|HIGH_CRITICAL\w*|MULTI_HIT|HIT_TWICE'
                       r'|RAISE_\w+_HIT|\w*DRAIN\w*|THAW_AND_BURN_HIT|FLINCH_\w+_HIT|DOUBLE_DAMAGE_\w+)$')
NEVER_DROP = {'MOVE_FREEZE_DRY', 'MOVE_PSYSHOCK', 'MOVE_PSYSTRIKE', 'MOVE_SECRET_SWORD', 'MOVE_BODY_PRESS', 'MOVE_FOUL_PLAY', 'MOVE_NUZZLE'}


def eff_power(m):
    d = moves[m]
    if m in VARIABLE: return VARIABLE[m]
    if 'MULTI_HIT' in d['effect']: return d['power'] * 3
    if 'HIT_TWICE' in d['effect'] or m == 'MOVE_TWINEEDLE': return d['power'] * 2
    return d['power']


def min_level_for(m):
    d = moves.get(m)
    if m in FIXED: return FIXED[m]
    if d is None or m in REACTIVE: return 1
    if d['split'] == 'SPLIT_STATUS':
        return RECOVERY_LEVEL if m in RECOVERY else SETUP_LEVEL if m in SETUP else 1
    if 'ONE_HIT_KO' in d['effect']: return OHKO_LEVEL
    p = eff_power(m)
    return next((lv for limit, lv in POWER_LEVELS if p <= limit), 50)


# evolution families and the earliest level each species can exist at
evo = collections.defaultdict(list)
for src, body in re.findall(r'\[(SPECIES_\w+)\] = \{\s*\.entries = \{(.*?)\}\s*,?\s*\}', open('data/Evolutions.c').read(), re.S):
    for method, param, dst in re.findall(r'\{ (EVO_\w+), (\w+), (SPECIES_\w+) \}', body):
        if method != 'EVO_NONE' and dst != 'SPECIES_NONE': evo[src].append((method, param, dst))
parent = {}
for src, es in evo.items():
    for method, param, dst in es: parent.setdefault(dst, src)
_min = {}
def min_level(s):
    if s not in _min:
        if s not in parent:
            _min[s] = 1
        else:
            levels = [int(p) for m, p, d in evo[parent[s]] if d == s and m.startswith('EVO_LEVEL') and p.isdigit()]
            _min[s] = max([min_level(parent[s])] + levels)
    return _min[s]
def ancestors(s):
    out = []
    while s in parent: s = parent[s]; out.append(s)
    return out


def game_moves(game, s):
    out = {}
    for e in games[game].get(s, {}).get('LevelMoves', []):
        m = REPLACE.get(e['Move'], e['Move'])
        if m in moves and m not in unimplemented: out.setdefault(m, e['Level'])
    return out
def native(s):
    return set().union(*(game_moves(g, s) for g in games))


def build(s):
    """[level, move, source] with source 'hgss', 'new' or 'critical'"""
    hgss = game_moves('10_hgss', s)
    entries = {m: [lv, m, 'hgss'] for m, lv in hgss.items()}
    earlier = set().union(*[native(a) for a in ancestors(s)]) if ancestors(s) else set()
    sv, za = game_moves('21_sv', s), game_moves('22_za', s)
    for m in list(sv) + [m for m in za if m not in sv]:
        lv = sv.get(m, za.get(m))
        if m in entries or (lv == 1 and m in earlier) or (s, m) in MEGA_ONLY: continue
        entries[m] = [lv, m, 'new']
    for (sp, m), lv in CRITICAL.items():
        if sp == s and m not in entries: entries[m] = [lv, m, 'critical']
    return list(entries.values())


def audit(s, entries):
    base, report = min_level(s), []
    hgss = game_moves('10_hgss', s)
    for x in entries:
        lv, m, src = x
        floor = min_level_for(m)
        if max(lv, base) < floor:
            target = floor if (src != 'hgss' or m in FIXED) else min(floor, hgss[m])
            if target > lv:
                report.append('%s %d -> %d (min level %d)' % (m[5:], lv, target, floor)); x[0] = target
    order = {x[1]: i for i, x in enumerate(entries)}
    entries.sort(key=lambda x: (x[0], order[x[1]]))
    keep = []
    for x in entries:
        lv, m, src = x
        d, drop = moves[m], None
        if src == 'new' and m not in NEVER_DROP:
            for y in entries:
                n = y[1]; dn = moves[n]
                if n == m or y[0] > max(lv, base) + WINDOW: continue
                if d['split'] != 'SPLIT_STATUS':
                    if d['priority'] or m in FIXED or m in VARIABLE or not DROPPABLE.fullmatch(d['effect']): break
                    if dn['split'] != d['split'] or dn['type'] != d['type'] or n in VARIABLE or n in FIXED or n in NEVER_DROP \
                            or dn['priority'] < 0 or dn['accuracy'] < d['accuracy'] - 5 or not DOMINATOR.fullmatch(dn['effect']): continue
                    better = (eff_power(n), dn['power']) > (eff_power(m), d['power'])
                    if better or ((eff_power(n), dn['power']) == (eff_power(m), d['power']) and (y[2] != 'new' or order[n] < order[m])):
                        drop = n; break
                elif dn['split'] == 'SPLIT_STATUS' and dn['effect'] == d['effect'] and dn['priority'] >= d['priority'] \
                        and dn['accuracy'] >= d['accuracy'] and (y[2] != 'new' or order[n] < order[m]):
                    drop = n; break
        if drop:
            report.append('drop %s (%d): %s already learned' % (m[5:], lv, drop[5:]))
        else:
            keep.append(x)
    # spread added moves that share a level, keeping each at most WINDOW levels later
    used = collections.Counter(x[0] for x in keep if x[2] == 'hgss')
    for x in sorted(keep, key=lambda x: (x[2] != 'hgss', x[0])):
        if x[2] == 'hgss': continue
        if x[0] > 1 and used[x[0]]:
            free = next((l for l in range(x[0] + 1, x[0] + WINDOW + 1) if not used[l]), None)
            if free:
                report.append('%s %d -> %d (spread)' % (x[1][5:], x[0], free)); x[0] = free
        used[x[0]] += 1
    keep.sort(key=lambda x: (x[0], order[x[1]]))
    return keep, report


def mega_only_machine_moves(s):
    # MEGA_ONLY moves whose TM compatibility comes from Z-A alone; build_learnsets.py removes these (RemoveMachineMoves)
    other = set().union(*(set(d.get(s, {}).get('MachineMoves', [])) for name, d in all_games.items() if name not in ('20_la', '22_za', '99_go')))
    return sorted(m for sp, m in MEGA_ONLY if sp == s and m not in other)


all_games = {f.split('/')[-1][:-5]: json.load(open(f)) for f in __import__('glob').glob('data/learnsets/base/[0-9][0-9]_*.json')}

result, reports = {}, {}
for s, entry in custom.items():
    final, reports[s] = audit(s, build(s))
    result[s] = final
    result_entry = dict(entry, LevelMoves=[{'Level': x[0], 'Move': x[1]} for x in final])
    result_entry.pop('RemoveMachineMoves', None)
    if mega_only_machine_moves(s):
        result_entry['RemoveMachineMoves'] = mega_only_machine_moves(s)
    custom[s] = result_entry

if __name__ == '__main__':
    for s in sys.argv[1:]:
        if s.startswith('SPECIES_'):
            print(s, 'earliest level', min_level(s))
            print('\n'.join('  ' + r for r in reports[s]))
            print('  ' + ', '.join('%d %s%s' % (x[0], x[1][5:], {'hgss': '', 'new': '*', 'critical': '!'}[x[2]]) for x in result[s]))
    sizes = [len(v) for v in result.values()]
    print('species %d, average level-up moves %.1f, largest %d' % (len(sizes), sum(sizes) / len(sizes), max(sizes)))
    if '--write' in sys.argv:
        open(CUSTOM, 'w').write(json.dumps(custom, indent=2, ensure_ascii=False))
