"""Rol bazli gorunum havuzunu uretir (soul + skald_character + storm appearance + lua havuz tablosu).

Kullanim:  python tools/gen_appearance.py [--mercenaries "<Mercenaries kaynak klasoru>"]

Spawn ozellikleri (hair/beard/head/bodyType) oyunda etkisiz; gorunumu yalnizca soul'a bagli
Storm "appearance" kurallari belirler. Rastgelelik spawn aninda havuzdan soul secilerek saglanir.
Erkek kombinasyonlari Mercenaries'in kanitlanmis (body, head, hair, beard) uclulerinden secilir;
kadinlar (servant) Mercenaries'in fitted kadin kafa/sac bilesenlerini kullanir.
"""
import argparse
import glob
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

POOL_SIZE = {"guard_melee": 10, "guard_ranged": 10, "quartermaster": 10, "blacksmith": 10, "servant": 10}
ROLE_INDEX = {rid: i + 1 for i, rid in enumerate(POOL_SIZE)}
FEMALE_ROLES = {"servant"}
GUARD_ROLES = {"guard_melee", "guard_ranged"}

BRAIN_ID = "4b914d1c-724a-a92d-3e6b-d183d35b8b98"
FACTION = "trosecko_settlements_tvrzNebakov_soldiers"
SOCIAL_CLASS = "108"
MALE_VOICES = [100, 102, 106, 108, 132, 140]

RNG = random.Random(20261022)


def soul_guid(role, n):
    return "6e656261-%04x-4b00-9000-%012x" % (ROLE_INDEX[role], n)


def read(path):
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(text)


def male_tuples(merc):
    tuples = set()
    for f in glob.glob(os.path.join(merc, "libs", "Storm", "appearance", "*.xml")):
        for m in re.finditer(r"<operations>(.*?)</operations>", read(f), re.S):
            d = {}
            for k in ("Body", "Head", "Hair", "Beard"):
                mm = re.search(r'<set%s name="([^"]+)"' % k, m.group(1))
                if mm:
                    d[k] = mm.group(1)
            if len(d) != 4:
                continue
            if not (d["Head"].startswith("m_head") and d["Body"].startswith("m_body")):
                continue
            if "godwin" in d["Hair"] or "zachary" in d["Hair"] or "zachary" in d["Beard"]:
                continue
            tuples.add((d["Body"], d["Head"], d["Hair"], d["Beard"]))
    return sorted(tuples)


def pick_male(tuples, role, count, used_heads):
    old = [t for t in tuples if "_old_" in t[0]]
    young = [t for t in tuples if "_old_" not in t[0]]
    pool = old if role == "quartermaster" else young
    RNG.shuffle(pool)
    rest = [t for t in tuples if t not in pool]
    RNG.shuffle(rest)
    chosen, heads = [], set()
    for t in pool + rest:
        if t[1] in heads or t[1] in used_heads:
            continue
        chosen.append(t)
        heads.add(t[1])
        if len(chosen) == count:
            break
    used_heads.update(heads)
    return chosen


def female_looks(merc):
    txt = read(os.path.join(merc, "libs", "Storm", "appearance", "mercenariesappearance.xml"))
    looks = {}
    for m in re.finditer(r'<rule name="appearance_mercenary_female_(\d+)">(.*?)</rule>', txt, re.S):
        looks[int(m.group(1))] = tuple(
            re.search(r'<set%s name="([^"]+)"' % k, m.group(2)).group(1) for k in ("Body", "Head", "Hair", "Beard"))
    sk = read(os.path.join(merc, "libs", "tables", "skald", "skald_character__mercenaries.xml"))
    voices = {}
    for m in re.finditer(r'<skald_character [^>]*?skald_character_name="char_mercenary_female_(\d+)"[^>]*>', sk):
        tag = m.group(0)
        voices[int(m.group(1))] = (re.search(r'voice_categories="([^"]*)"', tag).group(1),
                                   re.search(r'voice_id="(\d+)"', tag).group(1))
    return [(looks[i], voices.get(i, ("generic christian", "148"))) for i in sorted(looks)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mercenaries", default=r"C:\Users\musta\Desktop\KCD2 Mod Sources\Mercenaries")
    merc = ap.parse_args().mercenaries

    tuples = male_tuples(merc)
    females = female_looks(merc)
    used_heads = set()
    entries = []  # (role, n, look, gender, voice)
    for role, count in POOL_SIZE.items():
        if role in FEMALE_ROLES:
            for n in range(1, count + 1):
                look, voice = females[(n - 1) % len(females)]
                entries.append((role, n, look, 1, voice))
        else:
            for n, look in enumerate(pick_male(tuples, role, count, used_heads), 1):
                entries.append((role, n, look, 0, ("generic christian", str(MALE_VOICES[(n + len(entries)) % len(MALE_VOICES)]))))

    souls = []
    for role, n, look, gender, voice in entries:
        vg = ' voice_group_name="Guards"' if role in GUARD_ROLES else ""
        souls.append(
            '\t\t<soul brain_id="%s" combat_level="0.5" digestion_multiplier="0" factionName="%s" '
            'initial_clothing_dirt="0" skald_character_name="char_nebakov_%s_%02d" social_class_id="%s" '
            'soul_archetype_id="0" soul_id="%s" soul_name="soul_nebakov_%s_%02d" soul_vip_class_id="0"%s '
            'xp_multiplier="0" />' % (BRAIN_ID, FACTION, role, n, SOCIAL_CLASS, soul_guid(role, n), role, n, vg))
    write(os.path.join(SRC, "libs", "tables", "rpg", "soul__nebakovrising.xml"),
          '<?xml version="1.0" encoding="us-ascii"?>\n'
          '<database xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'name="barbora" xsi:noNamespaceSchemaLocation="../database.xsd">\n'
          '\t<souls version="2">\n' + "\n".join(souls) + "\n\t</souls>\n</database>\n")

    tmpl = ('\t\t<skald_character age="2" body_type="4" description_string_name="char_dumb_dumb_uiName" gender="%d" '
            'image1="false" image2="false" image3="false" image4="false" mortality_id="0" owner="Dummy" '
            'script_owner="Dummy" skald_character_full_name_string_name="char_dumb_dumb_uiName" '
            'skald_character_name="%s" ui_name_string_name="char_dumb_dumb_uiName" unique_assets="" '
            'voice_categories="%s" voice_id="%s" />')
    chars = [tmpl % (0, "char_dumb_dumb", "generic christian", "106")]
    for role, n, look, gender, voice in entries:
        chars.append(tmpl % (gender, "char_nebakov_%s_%02d" % (role, n), voice[0], voice[1]))
    write(os.path.join(SRC, "libs", "tables", "skald", "skald_character__nebakovrising.xml"),
          '<?xml version="1.0" encoding="us-ascii"?>\n'
          '<database name="barbora" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'xsi:noNamespaceSchemaLocation="../database.xsd">\n'
          '\t<skald_characters version="1">\n' + "\n".join(chars) + "\n\t</skald_characters>\n</database>\n")

    rules = []
    for role, n, (body, head, hair, beard), gender, voice in entries:
        rules.append(
            '        <rule name="appearance_nebakov_%s_%02d">\n'
            '            <selectors><hasName Name="soul_nebakov_%s_%02d" /></selectors>\n'
            '            <operations>\n'
            '                <setBody name="%s" />\n                <setHead name="%s" />\n'
            '                <setHair name="%s" />\n                <setBeard name="%s" />\n'
            '            </operations>\n        </rule>' % (role, n, role, n, body, head, hair, beard))
    write(os.path.join(SRC, "libs", "storm", "appearance", "nebakovappearance.xml"),
          '<?xml version="1.0"?>\n<!DOCTYPE storm SYSTEM "..\\storm.dtd">\n<storm>\n    <rules>\n'
          + "\n".join(rules) + "\n    </rules>\n</storm>\n")

    lines = ["-- GENERATED by tools/gen_appearance.py - elle duzenleme.",
             "nebakovrising = nebakovrising or {}", "nebakovrising.AppearancePools = {"]
    for role in POOL_SIZE:
        lines.append("    %s = {" % role)
        lines += ['        "%s",' % soul_guid(role, n) for r, n, *_ in entries if r == role]
        lines.append("    },")
    lines.append("}")
    write(os.path.join(SRC, "Scripts", "mods", "AppearancePools.lua"), "\n".join(lines) + "\n")

    print("souls:", len(entries))
    for role in POOL_SIZE:
        print(role, [e[2][1] for e in entries if e[0] == role])


if __name__ == "__main__":
    main()
    from build_npc_names import build, build_localization
    build(); build_localization()
