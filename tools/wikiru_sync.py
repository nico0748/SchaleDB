#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wikiru_sync.py — ブルアカ攻略 wikiru (https://bluearchive.wikiru.jp/) から
SchaleDB フォークに未登録の生徒を検出し、生徒データと画像を追加するツール。

サブコマンド:
  diff     wikiru のキャラクター一覧とローカル data/jp/students.json を名前で突き合わせ、
           未登録の生徒を表示する
  fetch    未登録（または --names で指定）の生徒ページと画像を wikiru から取得してキャッシュする
  build    キャッシュから SchaleDB 形式の生徒エントリを組み立て、data/*/students(.min).json と
           images/ に書き込む（--dry-run で書き込みなし）
  verify   既存生徒（例: コトネ）を wikiru から組み立て、ローカルの正式データと比較する
           （パーサが壊れていないかの確認用）

礼儀:
  - robots.txt を尊重（ページ閲覧と plugin=ref/attach2 の画像のみ使用、cmd= 系は叩かない）
  - リクエスト間隔は既定 3 秒（--delay）。取得物はキャッシュし、再実行時は再取得しない
  - User-Agent は汎用名のみ

作成されるエントリは "Source": "wikiru" / "DataPartial": true を持つ。
schaledb.com 側に正式データが出たら、同名の wikiru エントリは置き換え対象（DATA_NOTICE.md 参照）。
"""
import argparse
import html
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")
LANGS = ["jp", "en", "kr", "tw", "cn", "zh", "th"]
BASE = "https://bluearchive.wikiru.jp/"
LIST_PAGE = "キャラクター一覧"
UA = "Mozilla/5.0 (compatible; SchaleDB-fork-updater/1.0)"
DEFAULT_CACHE = os.environ.get("WIKIRU_CACHE", os.path.join(REPO, ".wikiru_cache"))

# ---------------------------------------------------------------- mappings
SCHOOL = {"アビドス": "Abydos", "アリウス": "Arius", "ゲヘナ": "Gehenna", "百鬼夜行": "Hyakkiyako",
          "ミレニアム": "Millennium", "レッドウィンター": "RedWinter", "山海経": "Shanhaijing",
          "SRT": "SRT", "トリニティ": "Trinity", "ヴァルキューレ": "Valkyrie", "その他": "ETC",
          "常盤台中学": "Tokiwadai", "柵川中学": "Sakugawa", "ハイランダー": "Highlander",
          "ワイルドハント": "WildHunt", "オデュッセイア": "Odyssey"}
ROLE = {"アタッカー": "DamageDealer", "タンク": "Tanker", "ヒーラー": "Healer",
        "サポーター": "Supporter", "T.S": "Vehicle"}
SQUAD = {"STRIKER": "Main", "SPECIAL": "Support"}
BULLET = {"爆発": "Explosion", "貫通": "Pierce", "神秘": "Mystic", "振動": "Sonic", "分解": "Chemical"}
ARMOR = {"軽装備": "LightArmor", "重装甲": "HeavyArmor", "特殊装甲": "Unarmed",
         "弾力装甲": "ElasticArmor", "複合装甲": "CompositeArmor"}
ADAPT = {"D": 0, "C": 1, "B": 2, "A": 3, "S": 4, "SS": 5}
EQUIP = {"帽子": "Hat", "ヘアピン": "Hairpin", "腕時計": "Watch", "シューズ": "Shoes",
         "バッグ": "Bag", "ネックレス": "Necklace", "グローブ": "Gloves", "バッジ": "Badge",
         "お守り": "Charm"}
TERRAIN = {"市街": "Street", "屋外": "Outdoor", "屋内": "Indoor"}
STAT = {"攻撃力": "AttackPower", "最大HP": "MaxHP", "治癒力": "HealPower", "防御力": "DefensePower"}
# 募集/入手 記号 → IsLimited（localization の IsLimited: 1限定 2イベント報酬 3周年 4アーカイブ）
RECRUIT = {"○": 0, "◇": 1, "☆": 3, "●": 4, "★": 1, "▽": 1}
# ★3 の限界突破倍率（js/common.js の既定 transcendence と同じ）
TRANS3 = {"AttackPower": 1.22, "MaxHP": 1.12, "HealPower": 1.175}


def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


# ---------------------------------------------------------------- fetching
class Fetcher:
    def __init__(self, cache, delay):
        self.cache, self.delay, self.last = cache, delay, 0.0
        os.makedirs(cache, exist_ok=True)

    def get(self, url, name):
        path = os.path.join(self.cache, name)
        if os.path.exists(path):
            return open(path, "rb").read()
        wait = self.last + self.delay - time.time()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                break
            except Exception as e:  # noqa
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
        self.last = time.time()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(data)
        return data

    def page(self, title):
        url = BASE + "?" + urllib.parse.quote(title)
        return self.get(url, f"pages/{title}.html").decode("utf-8")

    def attach(self, src):
        """src は attach2/xxxx.png（相対）"""
        return self.get(urllib.parse.urljoin(BASE, src), "attach/" + os.path.basename(src))


# ---------------------------------------------------------------- html helpers
def cell_text(c):
    c = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', lambda m: "[" + m.group(1) + "]", c)
    c = re.sub(r"<br[^>]*>", "\n", c)
    c = re.sub(r"<script.*?</script>|<style.*?</style>", "", c, flags=re.S)
    c = re.sub(r"<[^>]+>", "", c)
    return html.unescape(c).strip()


def tables(fragment):
    out = []
    for t in re.findall(r"<table.*?</table>", fragment, re.S):
        rows = []
        for r in re.findall(r"<tr.*?</tr>", t, re.S):
            rows.append([cell_text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)])
        out.append(rows)
    return out


def sections(page):
    """本文の見出し（content_1_N）ごとに HTML を分割。重複見出しは最初のみ。"""
    parts = re.split(r'(<h[2-4] id="content_1_\d+"[^>]*>.*?</h[2-4]>)', page, flags=re.S)
    out, order = {}, []
    for i in range(1, len(parts) - 1, 2):
        title = re.sub(r"\s+|†", "", cell_text(parts[i])).replace("[Edit]", "")
        key = title
        n = 2
        while key in out:
            key = f"{title}#{n}"
            n += 1
        out[key] = parts[i + 1]
        order.append(key)
    return out, order


def images(fragment):
    res = []
    for tag in re.findall(r"<img[^>]*>", fragment):
        src = re.search(r'data-src="([^"]+)"', tag) or re.search(r' src="([^"]+)"', tag)
        alt = re.search(r'alt="([^"]*)"', tag)
        if src and "attach2/" in src.group(1):
            res.append((html.unescape(alt.group(1)) if alt else "", src.group(1)))
    return res


# ---------------------------------------------------------------- list page
def parse_list(page):
    t = max(re.findall(r"<table.*?</table>", page, re.S), key=len)
    rows = re.findall(r"<tr.*?</tr>", t, re.S)
    hdr = [norm(cell_text(c)).strip("_") for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rows[0], re.S)]
    out = []
    for r in rows[1:]:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)
        v = [cell_text(c).replace("\n", "") for c in cells]
        if len(v) < 3 or not v[2]:
            continue
        d = dict(zip(hdr, v))
        m = re.search(r'href="\./\?([^"]+)"', cells[2])
        d["_page"] = urllib.parse.unquote(m.group(1)) if m else d["名前"]
        im = images(cells[1])
        d["_icon"] = im[0][1] if im else None
        out.append(d)
    return out


# ---------------------------------------------------------------- student page
def kv_pairs(rows):
    d = {}
    for r in rows:
        for i in range(0, len(r) - 1, 2):
            if r[i]:
                d.setdefault(r[i], r[i + 1])
    return d


def level_rows(rows):
    """スキル表 → [(lv, cost or None, text)]"""
    res, cost = [], None
    for r in rows:
        if not r or not re.fullmatch(r"\d+", r[0]):
            continue
        if len(r) >= 3 and re.fullmatch(r"\d+", r[1]):
            cost = int(r[1])
            res.append((int(r[0]), cost, r[2:]))
        else:
            res.append((int(r[0]), cost, r[1:]))
    return res


NUM = re.compile(r"\d+(?:\.\d+)?%?")


def templatize(texts):
    """各レベルの説明文から、レベルで変化する数値を <?n> に置き換える"""
    texts = [t.replace("/\n", "/\n").strip() for t in texts]
    base = texts[0]
    splits = [NUM.split(t) for t in texts]
    nums = [NUM.findall(t) for t in texts]
    if any(s != splits[0] for s in splits) or any(len(n) != len(nums[0]) for n in nums):
        return base, []  # 構造が揃わない → Lv1 の文をそのまま
    out, params = splits[0][0], []
    for i, n in enumerate(nums[0]):
        col = [x[i] for x in nums]
        if len(set(col)) > 1:
            params.append(col)
            out += f"<?{len(params)}>"
        else:
            out += n
        out += splits[0][i + 1]
    return out, params


def skill_icon(alt):
    name = alt.rsplit(".", 1)[0]
    if name.startswith("SKILLICON_") and not re.match(r"SKILLICON_CH\d+", name):
        return "COMMON_" + name
    return name


def parse_stats(rows):
    d = kv_pairs(rows)
    res = {}
    for jp, key in [("HP", "MaxHP"), ("攻撃力", "AttackPower"), ("治癒力", "HealPower")]:
        v = d.get(jp, "")
        lv1 = int(re.match(r"\d+", v).group())
        lv90 = int(re.search(r"/(\d+)\(★3Lv90\)", v.replace("\n", "")).group(1))
        s1 = round(lv1 / TRANS3[key])
        raw90 = lv90 / TRANS3[key]
        res[key + "1"] = s1
        res[key + "100"] = round(s1 + (raw90 - s1) * 99 / 89)
    dp = re.findall(r"\d+", d.get("防御力", "0/0"))
    res["DefensePower1"] = int(dp[0])
    res["DefensePower100"] = round(int(dp[0]) + (int(dp[1]) - int(dp[0])) * 99 / 89)
    num = lambda k: int(re.search(r"\d+", d.get(k, "0")).group())
    res.update({"DodgePoint": num("回避値"), "AccuracyPoint": num("命中値"),
                "CriticalPoint": num("会心値"),
                "CriticalDamageRate": num("会心ダメージ") * 100,
                "StabilityPoint": num("安定値"), "Range": num("射程距離"),
                "RegenCost": num("コスト回復力")})
    for jp, key in [("市街地戦闘力", "StreetBattleAdaptation"), ("屋外戦闘力", "OutdoorBattleAdaptation"),
                    ("屋内戦闘力", "IndoorBattleAdaptation")]:
        res[key] = ADAPT.get(d.get(jp, "D"), 0)
    return res


def parse_page(page):
    sec, order = sections(page)
    info = {"_images": images(page)}
    # --- 基本情報
    basic = tables(sec.get("基本情報", ""))
    prof = {}
    for t in basic:
        prof.update(kv_pairs(t))
    info["profile"] = prof
    for t in basic:
        flat = [c for r in t for c in r]
        if any("ステータス" in c for c in flat):
            info["stats"] = parse_stats(t)
        if "装備（装着可能Lv）" in flat:
            for r in t:
                if r and r[0] == "Lv1":
                    info["equipment"] = [EQUIP[norm(r[i])] for i in (1, 3, 5) if norm(r[i]) in EQUIP]
        for r in t:
            if r and r[0] == "基本情報" and len(r) == 1:
                pass
    # 基本情報（紹介文）・入手方法は「見出しセル → 次の行に本文」の形
    for t in basic:
        for i, r in enumerate(t):
            if len(r) == 1 and r[0] in ("基本情報", "入手方法") and i + 1 < len(t):
                info.setdefault("text", {})[r[0]] = t[i + 1][0]
    # --- スキル
    skills = {}
    for key, kind in [("EXスキル", "Ex"), ("ノーマルスキル", "Public"), ("パッシブスキル", "Passive"),
                      ("サブスキル", "ExtraPassive")]:
        frag = sec.get(key, "")
        ts = tables(frag)
        if not ts:
            continue
        t = ts[0]
        head = t[0]
        icon = re.match(r"\[(.+?)\]", head[0])
        names = [h for h in head[1:] if h]
        lv = level_rows(t)
        sk = {"Name": names[0] if names else "", "Icon": skill_icon(icon.group(1)) if icon else ""}
        desc, params = templatize([x[2][0] for x in lv])
        sk["Desc"], sk["Parameters"] = desc, params
        if kind == "Ex":
            sk["Cost"] = [x[1] for x in lv]
        skills[kind] = sk
        if kind == "Passive" and len(names) > 1 and lv and len(lv[0][2]) > 1:
            d2, p2 = templatize([x[2][1] for x in lv])
            skills["WeaponPassive"] = {"Name": names[1], "Icon": sk["Icon"], "Desc": d2, "Parameters": p2}
    info["skills"] = skills
    # --- 素材
    mats = {}
    for key in ("EXスキル#2", "その他スキル"):
        rows = tables(sec.get(key, ""))
        if not rows:
            continue
        rows = rows[0]
        lvl = []
        for i, r in enumerate(rows):
            if r and re.fullmatch(r"\d+", r[0]) and i + 1 < len(rows):
                items = [re.sub(r"^\[|\]$", "", c) for c in r[1:-1]]
                amts = rows[i + 1]
                pairs = [(it, int(re.sub(r"\D", "", a))) for it, a in zip(items, amts) if it and re.search(r"\d", a)]
                lvl.append(pairs)
        mats[key] = lvl
    info["materials"] = mats
    pm = tables(sec.get("必要素材", ""))
    if pm:
        for r in pm[0]:
            if r and r[0] == "1-5" and len(r) > 2:
                info["potential_item"] = re.sub(r"^\[|\]$", "", r[2])
    # --- 固有武器
    wfrag = sec.get("固有武器", "")
    wt = tables(wfrag)
    w = {}
    if wt:
        rows = wt[0]
        w["Name"] = rows[0][0]
        for i, r in enumerate(rows):
            if r and r[0] == "詳細" and i + 1 < len(rows):
                w["Desc"] = rows[i + 1][0]
            if r and r[0] == "★3" and len(r) > 1:
                for jp, en in TERRAIN.items():
                    if jp in r[1]:
                        w["AdaptationType"] = en
                w["AdaptationValue"] = 1
            if r and r[0] in STAT and len(r) >= 6:
                v1, v60 = int(r[1]), int(r[5])
                k = STAT[r[0]]
                w[k + "1"] = v1
                w[k + "100"] = round(v1 + (v60 - v1) * 99 / 59)
        icon = [a for a, _ in images(wfrag) if a.lower().startswith("weapon_icon")]
        w["_icon"] = icon[0] if icon else None
    info["weapon"] = w
    # --- 絆ランクボーナス
    bt = tables(sec.get("絆ランクボーナス", ""))
    bonus = []
    if bt:
        for r in bt[0]:
            if r and re.fullmatch(r"\d+-\d+", r[0]):
                bonus.append(dict((STAT.get(k, k), int(v)) for k, v in re.findall(r"(\D+?)\+(\d+)", norm(r[1]))))
    info["bond"] = bonus
    # --- 絆ストーリー（「メモリアルロビー解禁」の行の解放絆RANK）/ メモロビBGM
    for t in tables(sec.get("絆ストーリー", "")):
        for r in t:
            if len(r) >= 4 and "メモリアルロビー" in r[-1] and re.fullmatch(r"\d+", r[2]):
                info["lobby_rank"] = int(r[2])
    m = re.search(r"BGM[:：]\s*([^<\n]+)", cell_text(sec.get("メモリアルロビー", "")))
    info["lobby_bgm"] = m.group(1).strip() if m else None
    li = images(sec.get("メモリアルロビー", ""))
    info["lobby_img"] = li[0][1] if li else None
    bi = images(sec.get("基本情報", ""))
    info["portrait_img"] = bi[0][1] if bi else None
    if not info["lobby_img"]:
        info.pop("lobby_rank", None)
    return info


# ---------------------------------------------------------------- entry builder
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def item_index():
    items = load_json(os.path.join(DATA, "jp", "items.json"))
    items = items.values() if isinstance(items, dict) else items
    return {norm(i["Name"]): i["Id"] for i in items}


def bgm_id(name):
    if not name:
        return 0
    bgm = load_json(os.path.join(DATA, "jp", "localization.json")).get("BGM", {})
    return next((int(k) for k, v in bgm.items() if norm(v) == norm(name)), 0)


def club_key(jp, clubs):
    """部活名（日本語）→ localization の Club キー。未知なら clubs['_new'] に登録"""
    n = norm(jp)
    for k, v in clubs.items():
        if k != "_new" and norm(v) == n:
            return k
    for k, v in clubs.get("_new", {}).items():
        if norm(v) == n:
            return k
    sys.exit(f"未知の部活: {jp!r} → --club '{n}=ClubKey' で localization のキー名を指定してください")


def load_clubs(extra):
    clubs = dict(load_json(os.path.join(DATA, "jp", "localization.json"))["Club"])
    clubs["_new"] = {}
    for x in extra or []:
        jp, key = x.split("=", 1)
        if key not in clubs:
            clubs["_new"][key] = jp
    return clubs


def build_entry(row, info, sid, order, students, items, romaji, clubs):
    p, st = info["profile"], info["stats"]
    name = row["名前"]
    full = p.get("フルネーム", "")
    m = re.match(r"(.+?)\((.+?)\)(.+)", full)
    fam, ruby, given = (m.group(1), m.group(2), m.group(3)) if m else ("", "", name)
    school_line = p.get("学園", "")
    year = re.search(r"(\d年生|生徒会長|.年)", school_line)
    birthday = p.get("誕生日", "")
    bd = re.match(r"(\d+)月(\d+)日", birthday)
    weapon = info["weapon"]
    dev = None
    if weapon.get("_icon"):
        mm = re.search(r"(CH\d{4})", weapon["_icon"], re.I)
        dev = mm.group(1).upper() if mm else None
    sk = info["skills"]
    if not dev:  # 衣装違いは武器アイコンが元生徒と共用のことが多い → スキルアイコンの CHxxxx を使う
        for s_ in sk.values():
            mm = re.search(r"SKILLICON_(CH\d{4})", s_.get("Icon", ""))
            if mm:
                dev = mm.group(1)
                break
    base_name = re.sub(r"（.+）$", "", name)
    base = next((s for s in students.values() if s["Name"] == base_name), None)
    weapon_img = None
    if weapon.get("_icon") and not re.search(r"CH\d{4}", weapon["_icon"], re.I) and base:
        weapon_img = base["WeaponImg"]  # 元生徒と同じ武器アイコン
    elif weapon.get("_icon"):
        weapon_img = "weapon_icon_" + re.sub(r"\.png$", "", weapon["_icon"], flags=re.I).split("_")[-1].lower()
    # 通常攻撃は同じ武器種の既存生徒から流用（計算用）
    normal = next((s["Skills"]["Normal"] for s in students.values()
                   if s.get("WeaponType") == row["武器種"] and "Normal" in s.get("Skills", {})), None)
    skills = {}
    if normal:
        skills["Normal"] = normal
    for k in ("Ex", "Public", "Passive", "WeaponPassive", "ExtraPassive"):
        if k in sk:
            s = dict(sk[k])
            if k == "ExtraPassive" and dev and not s["Icon"].startswith("SKILLICON_CH"):
                pass
            s["Effects"] = []
            skills[k] = s
    # 素材
    def mat(levels, drop_last=False):
        ids, amts = [], []
        for lv in (levels[:-1] if drop_last else levels):
            i_, a_ = [], []
            for it, a in lv:
                iid = items.get(norm(it))
                if iid is None:
                    continue
                i_.append(iid)
                a_.append(a)
            ids.append(i_)
            amts.append(a_)
        return ids, amts
    ex_ids, ex_amt = mat(info["materials"].get("EXスキル#2", []))
    sk_ids, sk_amt = mat(info["materials"].get("その他スキル", []), drop_last=True)
    pot = items.get(norm(info.get("potential_item", ""))) or (ex_ids[0][1] if ex_ids and len(ex_ids[0]) > 1 else None)
    # 絆
    order_stats = []
    for b in info["bond"]:
        for k in b:
            if k not in order_stats:
                order_stats.append(k)
    order_stats = order_stats[:2]
    favor = [[b.get(k, 0) for k in order_stats] for b in info["bond"]]
    limited = RECRUIT.get(row.get("募集", "-"), None)
    if limited is None:
        limited = 2 if row.get("入手") == "◇" else 0
    school = SCHOOL.get(row["学校"], "ETC")
    bgs = [s["CollectionBG"] for s in students.values() if s["School"] == school and s.get("CollectionBG")]
    entry = {
        "Id": sid, "IsReleased": [True, False, False], "DefaultOrder": order,
        "PathName": romaji, "DevName": dev or romaji, "Name": name, "Icon": None,
        "SearchTags": [], "School": school, "Club": club_key(p.get("部活", ""), clubs),
        "StarGrade": int(row["レア"].lstrip("★")), "SquadType": SQUAD[row["役割"]],
        "TacticRole": ROLE[row["クラス"]], "Summons": [], "Position": row["ポジション"].capitalize(),
        "BulletType": BULLET[row["攻撃"]], "ArmorType": ARMOR[norm(row["防御"])],
        "StreetBattleAdaptation": st["StreetBattleAdaptation"],
        "OutdoorBattleAdaptation": st["OutdoorBattleAdaptation"],
        "IndoorBattleAdaptation": st["IndoorBattleAdaptation"],
        "WeaponType": row["武器種"],
        "WeaponImg": weapon_img or ("weapon_icon_" + (dev or romaji).lower()),
        "Cover": row["遮蔽物"] == "○", "Size": "Medium",
        "Equipment": info.get("equipment") or [EQUIP[norm(row[k])] for k in ("装備1", "装備2", "装備3")],
        "CollectionBG": max(set(bgs), key=bgs.count) if bgs else "",
        "FamilyName": fam, "PersonalName": given, "SchoolYear": year.group(1) if year else "",
        "CharacterAge": p.get("年齢", ""), "Birthday": birthday,
        "FamilyNameRuby": ruby, "PersonalNameRuby": "",
        "CharacterSSRNew": "",
        "ProfileIntroduction": info.get("text", {}).get("基本情報", ""),
        "Hobby": p.get("趣味", "").replace("\n", ""),
        "CharacterVoice": p.get("CV", ""),
        "BirthDay": f"{bd.group(1)}/{bd.group(2)}" if bd else "",
        "Illustrator": p.get("イラスト", ""), "Designer": p.get("デザイン", ""),
        "CharHeightMetric": p.get("身長", ""), "CharHeightImperial": None,
        "StabilityPoint": st["StabilityPoint"],
        "AttackPower1": st["AttackPower1"], "AttackPower100": st["AttackPower100"],
        "MaxHP1": st["MaxHP1"], "MaxHP100": st["MaxHP100"],
        "DefensePower1": st["DefensePower1"], "DefensePower100": st["DefensePower100"],
        "HealPower1": st["HealPower1"], "HealPower100": st["HealPower100"],
        "DodgePoint": st["DodgePoint"], "AccuracyPoint": st["AccuracyPoint"],
        "CriticalPoint": st["CriticalPoint"], "CriticalDamageRate": st["CriticalDamageRate"],
        "AmmoCount": 15, "AmmoCost": 1, "Range": st["Range"], "SightPoint": 800,
        "RegenCost": st["RegenCost"],
        "Skills": skills,
        "FavorStatType": order_stats, "FavorStatValue": favor, "FavorAlts": [],
        "MemoryLobby": [info["lobby_rank"], 0, 0] if info.get("lobby_rank") else [],
        "MemoryLobbyBGM": bgm_id(info.get("lobby_bgm")),
        "FurnitureInteraction": [[], [], []],
        "FavorItemTags": [], "FavorItemUniqueTags": [],
        "IsLimited": [limited, limited, limited],
        "Weapon": {
            "Name": weapon.get("Name", ""), "Desc": weapon.get("Desc", ""),
            "AdaptationType": weapon.get("AdaptationType", "Street"),
            "AdaptationValue": weapon.get("AdaptationValue", 1),
            "AttackPower1": weapon.get("AttackPower1", 0), "AttackPower100": weapon.get("AttackPower100", 0),
            "MaxHP1": weapon.get("MaxHP1", 0), "MaxHP100": weapon.get("MaxHP100", 0),
            "HealPower1": weapon.get("HealPower1", 0), "HealPower100": weapon.get("HealPower100", 0),
            "StatLevelUpType": "Standard"},
        "Gear": {},
        "SkillExMaterial": ex_ids, "SkillExMaterialAmount": ex_amt,
        "SkillMaterial": sk_ids, "SkillMaterialAmount": sk_amt,
        "PotentialMaterial": pot,
        "Source": "wikiru", "DataPartial": True,
    }
    # 弾数等は wikiru に無いので同武器種の既存生徒の中央値で埋める
    same = [s for s in students.values() if s.get("WeaponType") == row["武器種"]]
    if same:
        for k in ("AmmoCount", "AmmoCost"):
            vals = sorted(s[k] for s in same)
            entry[k] = vals[len(vals) // 2]
    return entry


# ---------------------------------------------------------------- images
def save_webp(data, dest, size=None, fit_height=None, mode=None):
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    im = im.convert("RGBA")
    if fit_height:
        w = round(im.width * fit_height / im.height)
        im = im.resize((w, fit_height), Image.LANCZOS)
    if size:
        im = im.resize(size, Image.LANCZOS)
    if mode:
        im = im.convert(mode)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    im.save(dest, "WEBP", quality=90, method=6)


def make_collection(portrait_data, dest):
    """立ち絵の頭部付近を切り出して 200x226 のコレクション画像（仮）を作る"""
    from PIL import Image
    im = Image.open(io.BytesIO(portrait_data)).convert("RGBA")
    bbox = im.getchannel("A").getbbox() or (0, 0, im.width, im.height)
    x0, y0, x1, y1 = bbox
    h = y1 - y0
    # 上端 18% の不透明部分の重心を頭の中心とみなす
    band = im.crop((x0, y0 + int(h * 0.04), x1, y0 + int(h * 0.18))).getchannel("A")
    cols = [sum(band.crop((i, 0, i + 1, band.height)).tobytes()) for i in range(band.width)]
    tot = sum(cols) or 1
    cx = x0 + sum(i * c for i, c in enumerate(cols)) / tot
    cw = int(h * 0.30)
    ch = int(cw * 226 / 200)
    left = int(cx - cw / 2)
    top = y0 + int(h * 0.02)
    crop = im.crop((left, top, left + cw, top + ch))
    bg = Image.new("RGBA", crop.size, (214, 232, 245, 255))
    bg.alpha_composite(crop)
    bg = bg.convert("RGB").resize((200, 226), Image.LANCZOS)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    bg.save(dest, "WEBP", quality=90, method=6)


def make_lobby(data, dest):
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    tw, th = 182, 144
    scale = max(tw / im.width, th / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left = (im.width - tw) // 2
    top = (im.height - th) // 2
    im = im.crop((left, top, left + tw, top + th))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    im.save(dest, "WEBP", quality=90, method=6)


def fetch_images(f, row, info, entry, dry):
    sid = entry["Id"]
    name = row["名前"]
    imgs = info["_images"]
    by_alt = {}
    for alt, src in imgs:
        by_alt.setdefault(alt, src)
    done = []
    out = lambda *p: os.path.join(REPO, "images", *p)
    # icon
    if row.get("_icon"):
        d = f.attach(row["_icon"])
        if not dry:
            save_webp(d, out("student", "icon", f"{sid}.webp"), size=(120, 120))
        done.append("icon")
    # portrait（ページ先頭のメイン画像: 「名前.png」 or 「名前_拡大.png」 等、プロフィール表の最初の画像）
    portrait_src = info.get("portrait_img")
    cand = [a for a, _ in imgs if a.startswith(name) and a.endswith(".png")
            and "_icon" not in a and "SD" not in a and "メモリアル" not in a and "家具" not in a]
    pref = [name + ".png", name + "_拡大.png"]
    cand.sort(key=lambda a: pref.index(a) if a in pref else len(pref))
    if not portrait_src and cand:
        portrait_src = by_alt[cand[0]]
    if portrait_src:
        d = f.attach(portrait_src)
        if not dry:
            save_webp(d, out("student", "portrait", f"{sid}.webp"), fit_height=1280)
            make_collection(d, out("student", "collection", f"{sid}.webp"))
        done += ["portrait", "collection(仮)"]
    if info.get("lobby_img"):
        d = f.attach(info["lobby_img"])
        if not dry:
            make_lobby(d, out("student", "lobby", f"{sid}.webp"))
        done.append("lobby")
    wi = info["weapon"].get("_icon")
    if wi and wi in by_alt and re.search(r"CH\d{4}", wi, re.I):
        d = f.attach(by_alt[wi])
        dest = out("weapon", entry["WeaponImg"] + ".webp")
        if not os.path.exists(dest):
            if not dry:
                save_webp(d, dest, size=(800, 205))
            done.append("weapon")
    for k, s in entry["Skills"].items():
        icon = s.get("Icon")
        if icon and not os.path.exists(out("skill", icon + ".webp")):
            alt = icon.replace("COMMON_", "") + ".png"
            if alt in by_alt:
                d = f.attach(by_alt[alt])
                if not dry:
                    save_webp(d, out("skill", icon + ".webp"))
                done.append("skill:" + icon)
    return done


# ---------------------------------------------------------------- io
def students_of(lang):
    return load_json(os.path.join(DATA, lang, "students.json"))


def write_students(lang, data):
    with open(os.path.join(DATA, lang, "students.json"), "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=4)
    with open(os.path.join(DATA, lang, "students.min.json"), "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, separators=(",", ":"))


def add_clubs(lang, new):
    """新しい部活キーを localization(.min).json に追加（値は日本語名。他言語は後で翻訳可）"""
    path = os.path.join(DATA, lang, "localization.json")
    raw = open(path, encoding="utf-8").read()
    loc = json.loads(raw)
    for k, v in new.items():
        loc["Club"].setdefault(k, v)
    ind = 4 if '\n    "' in raw[:200] else 1
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(loc, fp, ensure_ascii=False, indent=ind)
    with open(path.replace(".json", ".min.json"), "w", encoding="utf-8") as fp:
        json.dump(loc, fp, ensure_ascii=False, separators=(",", ":"))


def detect_indent():
    head = open(os.path.join(DATA, "jp", "students.json"), encoding="utf-8").read(200)
    m = re.search(r"\n( +)\"", head)
    return len(m.group(1)) if m else None


# ---------------------------------------------------------------- commands
def cmd_diff(a, f):
    rows = parse_list(f.page(LIST_PAGE))
    local = {s["Name"] for s in students_of("jp").values()}
    new = [r for r in rows if r["名前"] not in local]
    gone = sorted(local - {r["名前"] for r in rows})
    print(f"wikiru 一覧: {len(rows)} 行 / ローカル: {len(local)} 名")
    print(f"未登録: {len(new)} 名")
    for r in new:
        print(f"  {r['レア']} {r['名前']}  {r['学校']} {r['武器種']} {r['攻撃']}/{r['防御']} {r['クラス']}")
    if gone:
        print("ローカルのみ（名前表記ゆれの可能性）:", gone)
    return rows, new


def plan(a, rows, new):
    """新規 Id・PathName を決める。--map 'カナ=romaji' で PathName を指定"""
    st = students_of("jp")
    used = {int(k) for k in st}
    romaji = dict(x.split("=", 1) for x in (a.map or []))
    order = max(s["DefaultOrder"] for s in st.values()) + 1
    res = []
    for r in new:
        star = int(r["レア"].lstrip("★"))
        alt = "（" in r["名前"]
        base = 26000 if star == 1 else (20000 if alt else 10000)
        sid = max([i for i in used if base <= i < base + 1000] or [base]) + 1
        used.add(sid)
        rj = romaji.get(r["名前"])
        if not rj:
            sys.exit(f"PathName 未指定: {r['名前']}  → --map '{r['名前']}=romaji' を付けてください")
        res.append((r, sid, order, rj))
        order += 1
    return res


def cmd_build(a, f):
    rows, new = cmd_diff(a, f)
    if a.names:
        new = [r for r in rows if r["名前"] in a.names]
    if not new:
        print("追加対象なし")
        return
    st = students_of("jp")
    items = item_index()
    clubs = load_clubs(a.club)
    entries = []
    for r, sid, order, rj in plan(a, rows, new):
        info = parse_page(f.page(r["_page"]))
        e = build_entry(r, info, sid, order, st, items, rj, clubs)
        got = fetch_images(f, r, info, e, a.dry_run)
        entries.append(e)
        print(f"[{sid}] {e['Name']} ({rj}) dev={e['DevName']} 画像: {', '.join(got)}")
    if a.dry_run:
        print(json.dumps(entries, ensure_ascii=False, indent=1)[:6000])
        return
    for lang in LANGS:
        data = students_of(lang)
        for e in entries:
            data[str(e["Id"])] = e
        write_students(lang, data)
    if clubs["_new"]:
        for lang in LANGS:
            add_clubs(lang, clubs["_new"])
        print("localization の Club に追加:", clubs["_new"])
    out = os.path.join(a.cache, "added.json")
    json.dump(entries, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(entries)} 名を {len(LANGS)} 言語に追加しました（詳細: {out}）")


def cmd_verify(a, f):
    rows = parse_list(f.page(LIST_PAGE))
    st = students_of("jp")
    items = item_index()
    bad = 0
    for name in a.names or ["コトネ"]:
        r = next(x for x in rows if x["名前"] == name)
        ref = next(s for s in st.values() if s["Name"] == name)
        info = parse_page(f.page(r["_page"]))
        e = build_entry(r, info, ref["Id"], ref["DefaultOrder"], st, items, ref["PathName"], load_clubs(a.club))
        keys = ["School", "StarGrade", "SquadType", "TacticRole", "Position", "BulletType", "ArmorType",
                "StreetBattleAdaptation", "OutdoorBattleAdaptation", "IndoorBattleAdaptation", "WeaponType",
                "WeaponImg", "Cover", "Equipment", "FamilyName", "PersonalName", "SchoolYear", "CharacterAge",
                "Birthday", "FamilyNameRuby", "CharacterVoice", "BirthDay", "Illustrator", "Designer",
                "CharHeightMetric", "StabilityPoint", "AttackPower1", "AttackPower100", "MaxHP1", "MaxHP100",
                "DefensePower1", "DefensePower100", "HealPower1", "HealPower100", "DodgePoint",
                "AccuracyPoint", "CriticalPoint", "CriticalDamageRate", "Range", "RegenCost",
                "FavorStatType", "FavorStatValue", "SkillExMaterial", "SkillExMaterialAmount",
                "SkillMaterial", "SkillMaterialAmount", "PotentialMaterial", "IsLimited"]
        for k in keys:
            if e[k] != ref[k]:
                bad += 1
                print(f"  [差異] {name}.{k}: wikiru={e[k]!r} / 正式={ref[k]!r}")
        for k in ("Ex", "Public", "Passive", "WeaponPassive", "ExtraPassive"):
            a_, b_ = e["Skills"].get(k, {}), ref["Skills"].get(k, {})
            for kk in ("Name", "Icon", "Parameters", "Cost"):
                if a_.get(kk) != b_.get(kk):
                    bad += 1
                    print(f"  [差異] {name}.Skills.{k}.{kk}: wikiru={a_.get(kk)!r} / 正式={b_.get(kk)!r}")
        w = ref["Weapon"]
        for kk in ("Name", "AdaptationType", "AttackPower1", "AttackPower100", "MaxHP1", "MaxHP100",
                   "HealPower1", "HealPower100"):
            if e["Weapon"][kk] != w[kk]:
                bad += 1
                print(f"  [差異] {name}.Weapon.{kk}: wikiru={e['Weapon'][kk]!r} / 正式={w[kk]!r}")
    print(f"差異 {bad} 件")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["diff", "build", "verify"])
    ap.add_argument("--names", nargs="+", help="対象の生徒名（wikiru 表記）")
    ap.add_argument("--map", nargs="+", help="PathName 指定: 'アンナ=anna' 'カスミ（水着）=kasumi_swimsuit'")
    ap.add_argument("--club", nargs="+", help="新しい部活のキー指定: '183号特別クラス=Class183'")
    ap.add_argument("--cache", default=DEFAULT_CACHE, help="取得物のキャッシュ先")
    ap.add_argument("--delay", type=float, default=3.0, help="リクエスト間隔（秒）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    f = Fetcher(a.cache, a.delay)
    {"diff": cmd_diff, "build": cmd_build, "verify": cmd_verify}[a.command](a, f)


if __name__ == "__main__":
    main()
