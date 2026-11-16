#!/usr/bin/env python3
"""Audit level-up learnsets in data/learnsets/base/custom.json. See Learnsets in documentation/ENCORE_CHANGES.md.

- Attacks too strong for the level they're learned at move later, by effective power (multi-hit and two-hit moves count
  their usual total). A move HeartGold also teaches this Pokemon never moves past HeartGold's level.
- Fixed-damage moves (Sonic Boom, Dragon Rage, Night Shade and so on) have a minimum level, HeartGold's own included.
- Added recovery and setup moves have a minimum level.
- A Pokemon's earliest possible level (its evolution level) counts, so moves an evolved Pokemon learns at level 1 only
  move if it could exist earlier than their minimum level.
- An added attack is dropped when the Pokemon already learns a same-type, same-category attack at least as strong
  within 3 levels with no drawback, and an added status move is dropped when it learns one with the same effect.
  HeartGold's own moves and the documented additions in KEEP are never dropped.

Run from the repo root: python3 scripts/audit_learnsets.py [--write] [SPECIES_X ...]
It prints what it would change; --write saves custom.json. Then regenerate learnsets.json (see ENCORE_CHANGES.md).
Rerunning it on its own output changes nothing.
"""
import re, json, sys, collections
R = ''
CUSTOM = R + 'data/learnsets/base/custom.json'
custom = json.load(open(CUSTOM))
hgss = json.load(open(R + 'data/learnsets/base/10_hgss.json'))
config = dict(re.findall(r'#define (\w+) +(\d+)', open(R + 'include/config.h').read()))

def cfg(v):
    m = re.fullmatch(r'\(\((\w+)\) \? \((\w+)\) : \((\w+)\)\)', v.strip())
    return (m.group(2) if config.get(m.group(1), '0') != '0' else m.group(3)) if m else v.strip()

moves = {}
for key, body in re.findall(r'\n    \[(MOVE_\w+)\] = \{(.*?)\n    \},', open(R + 'data/Moves.c').read(), re.S):
    g = lambda f: cfg(re.search(r'\.' + f + r' = ([^\n]+),\n', body).group(1))
    try:
        moves[key] = dict(effect=g('effect'), split=g('split'), power=int(g('power')), type=g('type'), priority=int(g('priority')), accuracy=int(g('accuracy')))
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
OHKO = 35
RECOVERY = {'MOVE_RECOVER', 'MOVE_ROOST', 'MOVE_SOFT_BOILED', 'MOVE_MILK_DRINK', 'MOVE_SLACK_OFF', 'MOVE_SYNTHESIS', 'MOVE_MOONLIGHT',
            'MOVE_MORNING_SUN', 'MOVE_SHORE_UP', 'MOVE_STRENGTH_SAP', 'MOVE_WISH', 'MOVE_HEAL_ORDER', 'MOVE_LIFE_DEW'}
SETUP = {'MOVE_SWORDS_DANCE', 'MOVE_DRAGON_DANCE', 'MOVE_NASTY_PLOT', 'MOVE_CALM_MIND', 'MOVE_BULK_UP', 'MOVE_QUIVER_DANCE',
         'MOVE_SHELL_SMASH', 'MOVE_BELLY_DRUM', 'MOVE_COIL', 'MOVE_SHIFT_GEAR', 'MOVE_TAIL_GLOW', 'MOVE_VICTORY_DANCE', 'MOVE_TIDY_UP',
         'MOVE_GROWTH', 'MOVE_WORK_UP', 'MOVE_HONE_CLAWS', 'MOVE_ROCK_POLISH', 'MOVE_AGILITY', 'MOVE_COTTON_GUARD'}
RECOVERY_FLOOR, SETUP_FLOOR = 20, 30

def eff_power(m):
    d = moves[m]
    if m in VARIABLE: return VARIABLE[m]
    p = d['power']
    if 'MULTI_HIT' in d['effect']: return p * 3
    if 'HIT_TWICE' in d['effect'] or m == 'MOVE_TWINEEDLE': return p * 2
    return p

def power_floor(p):
    for limit, level in ((40, 1), (50, 8), (60, 14), (70, 20), (80, 26), (90, 32), (100, 38), (110, 42), (120, 46)):
        if p <= limit: return level
    return 50

def floor(m, injected):
    d = moves.get(m)
    if m in FIXED: return FIXED[m]          # applies to every learnset, HeartGold's included
    if not injected or d is None: return 1
    if d['split'] == 'SPLIT_STATUS':
        if m in RECOVERY: return RECOVERY_FLOOR
        if m in SETUP: return SETUP_FLOOR
        return 1
    if 'ONE_HIT_KO' in d['effect']: return OHKO
    if m in ('MOVE_COUNTER', 'MOVE_MIRROR_COAT', 'MOVE_METAL_BURST', 'MOVE_COMEUPPANCE', 'MOVE_BIDE'): return 1
    return power_floor(eff_power(m))

# evolution families and the earliest level each species can exist at
evo = collections.defaultdict(list)
for src, body in re.findall(r'\[(SPECIES_\w+)\] = \{\s*\.entries = \{(.*?)\}\s*,?\s*\}', open(R + 'data/Evolutions.c').read(), re.S):
    for method, param, dst in re.findall(r'\{ (EVO_\w+), (\w+), (SPECIES_\w+) \}', body):
        if method != 'EVO_NONE' and dst != 'SPECIES_NONE': evo[src].append((method, param, dst))
parent = {}
for src, es in evo.items():
    for method, param, dst in es: parent.setdefault(dst, (src, method, param))
minlevel = {}
def min_level(s):
    if s in minlevel: return minlevel[s]
    if s not in parent: minlevel[s] = 1; return 1
    src, method, param = parent[s]
    best = min_level(src)
    for m2, p2, d2 in evo[src]:
        if d2 == s and m2.startswith('EVO_LEVEL') and p2.isdigit():
            best = max(min_level(src), int(p2)) if m2 in ('EVO_LEVEL',) or True else best
    minlevel[s] = best; return best
def family(s):
    up = []; x = s
    while x in parent: x = parent[x][0]; up.append(x)
    down = []; q = [s]
    while q:
        y = q.pop(0)
        for _, _, d in evo.get(y, []): down.append(d); q.append(d)
    return up + down

def hgss_levels(s):
    d = {}
    for e in hgss.get(s, {}).get('LevelMoves', []): d.setdefault(e['Move'], e['Level'])
    return d

# documented level-up additions that the redundancy pass must keep (floors still apply)
KEEP = {('SPECIES_MAMOSWINE', 'MOVE_ICICLE_CRASH'), ('SPECIES_PILOSWINE', 'MOVE_ICICLE_CRASH'), ('SPECIES_BRELOOM', 'MOVE_SPORE'),
        ('SPECIES_MEGANIUM', 'MOVE_MOONBLAST'), ('SPECIES_LINOONE', 'MOVE_EXTREME_SPEED')}
for s in ['CHARIZARD', 'PIDGEOT', 'AERODACTYL', 'DRAGONITE', 'CROBAT', 'NINJASK', 'SALAMENCE', 'MOTHIM', 'VESPIQUEN', 'GLIGOR']:
    KEEP.add(('SPECIES_' + s, 'MOVE_DUAL_WINGBEAT'))
EGG_ADDS = {'MORNING_SUN': 'ARCANINE RAPIDASH SUNFLORA VENOMOTH', 'MOONLIGHT': 'EXEGGUTOR', 'STRENGTH_SAP': 'VILEPLUME BELLOSSOM VICTREEBEL JUMPLUFF',
            'WISH': 'CLEFABLE', 'RAPID_SPIN': 'TENTACRUEL KABUTOPS ARMALDO CLOYSTER', 'ROCK_BLAST': 'CLOYSTER',
            'FAKE_OUT': 'RAICHU MEDICHAM INFERNAPE AMBIPOM LOPUNNY TOXICROAK WEAVILE', 'MACH_PUNCH': 'HITMONTOP', 'BULLET_PUNCH': 'HITMONTOP HARIYAMA',
            'ICE_SHARD': 'DONPHAN', 'AQUA_JET': 'CRAWDAUNT', 'SUCKER_PUNCH': 'ARBOK', 'FIRE_FANG': 'LUXRAY', 'ICE_FANG': 'LUXRAY',
            'FREEZE_DRY': 'LAPRAS', 'BELLY_DRUM': 'AZUMARILL', 'SHELL_SMASH': 'TORTERRA'}
for m, ss in EGG_ADDS.items():
    for s in ss.split(): KEEP.add(('SPECIES_' + s, 'MOVE_' + m))

DROPPABLE = re.compile(r'MOVE_EFFECT_(HIT|FLINCH_HIT|BURN_HIT|FREEZE_HIT|PARALYZE_HIT|POISON_HIT|CONFUSE_HIT|LOWER_\w+_HIT|HIGH_CRITICAL\w*|MULTI_HIT|HIT_TWICE)$')
DOMINATE_WINDOW = 3
# a move only counts as the better option if it has no drawback: no recoil, lock-in, charge turn, crash or stat drop on the user
DOMINATOR = re.compile(DROPPABLE.pattern[:-2] + r'|RAISE_\w+_HIT|\w*DRAIN\w*|THAW_AND_BURN_HIT|FLINCH_\w+_HIT|DOUBLE_DAMAGE_\w+|HIGH_CRITICAL\w*)$')
NEVER_DROP = {'MOVE_FREEZE_DRY', 'MOVE_PSYSHOCK', 'MOVE_PSYSTRIKE', 'MOVE_SECRET_SWORD', 'MOVE_BODY_PRESS', 'MOVE_FOUL_PLAY', 'MOVE_NUZZLE'}

report = collections.defaultdict(list)
new_custom = {}
for s, entry in custom.items():
    own = hgss_levels(s)
    fam = {}
    for f in family(s):
        for m, l in hgss_levels(f).items(): fam.setdefault(m, l)
    base = min_level(s)
    out = []
    for e in entry['LevelMoves']:
        m, lv = e['Move'], e['Level']
        injected = m not in own
        new, why = lv, ''
        f = floor(m, True)
        if max(lv, base) < f:
            # too strong for its level: push it later, but no later than HeartGold teaches it (fixed damage always moves)
            target = f if (injected or m in FIXED) else min(f, own[m])
            if target > lv:
                kind = 'fixed damage' if m in FIXED else 'recovery' if m in RECOVERY else 'setup' if m in SETUP else 'power %d' % eff_power(m)
                new, why = target, kind + ('' if target == f else ', HeartGold level')
        out.append([new, m, injected, lv, why])
    # one entry per move, at its earliest level
    seen = {}
    for x in sorted(out, key=lambda x: x[0]):
        seen.setdefault(x[1], x)
    out = sorted(seen.values(), key=lambda x: (x[0], [e['Move'] for e in entry['LevelMoves']].index(x[1])))
    # redundancy: drop an added attack when the Pokemon already has a same-type, same-category attack at least as strong by then
    keep = []
    for x in out:
        lv, m, injected = x[0], x[1], x[2]
        d = moves.get(m)
        drop = None
        if injected and d and (s, m) not in KEEP and d['split'] != 'SPLIT_STATUS' and d['priority'] == 0 and m not in FIXED and m not in VARIABLE \
                and DROPPABLE.fullmatch(d['effect']) and m not in NEVER_DROP:
            for y in out:
                n = y[1]; dn = moves.get(n)
                if n == m or not dn or dn['split'] != d['split'] or dn['type'] != d['type']: continue
                if n in VARIABLE or n in FIXED or n in NEVER_DROP or dn['priority'] < 0 or dn['accuracy'] < d['accuracy'] - 5 or not DOMINATOR.fullmatch(dn['effect']): continue
                if y[0] <= max(lv, base) + DOMINATE_WINDOW and (eff_power(n), moves[n]['power']) >= (eff_power(m), moves[m]['power']) and (y[2] is False or (eff_power(n), moves[n]['power']) > (eff_power(m), moves[m]['power']) or out.index(y) < out.index(x)):
                    drop = n; break
        if injected and d and not drop and (s, m) not in KEEP and d['split'] == 'SPLIT_STATUS':
            # an added status move with the same effect as one the Pokemon already learns by then, and no better priority or accuracy
            for y in out:
                n = y[1]; dn = moves.get(n)
                if n != m and dn and dn['split'] == 'SPLIT_STATUS' and dn['effect'] == d['effect'] and y[0] <= max(lv, base) + DOMINATE_WINDOW \
                        and dn['priority'] >= d['priority'] and dn['accuracy'] >= d['accuracy'] and (not y[2] or out.index(y) < out.index(x)):
                    drop = n; break
        if drop:
            report[s].append('drop %s (L%d): %s by L%d' % (m, x[3], drop, [y for y in out if y[1] == drop][0][0]))
        else:
            keep.append(x)
            if x[0] != x[3]: report[s].append('%s %d -> %d (%s)' % (m, x[3], x[0], x[4]))
    new_custom[s] = dict(entry, LevelMoves=[{'Level': x[0], 'Move': x[1]} for x in keep])

if __name__ == '__main__':
    if '--write' in sys.argv:
        open(CUSTOM, 'w').write(json.dumps(new_custom, indent=2, ensure_ascii=False))
    for s in sys.argv[1:]:
        if s.startswith('SPECIES_'):
            print(s, 'min level', min_level(s)); print('\n'.join('  ' + r for r in report[s]))
            print('  final:', ', '.join('%d %s' % (e['Level'], e['Move'][5:]) for e in new_custom[s]['LevelMoves']))
    n = sum(len(v) for v in report.values()); drops = sum(1 for v in report.values() for r in v if r.startswith('drop'))
    print('species changed', len(report), 'changes', n, 'drops', drops)
