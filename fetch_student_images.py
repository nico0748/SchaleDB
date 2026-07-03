#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_student_images.py — SchaleDB 生徒画像（立ち絵・アイコン等）ダウンローダ

schaledb.com から生徒画像を取得し、ローカル SchaleDB リポジトリの
images/student/<type>/<Id>.webp に保存する。data/jp/students.json を読み、
「ローカルに画像が無い生徒」を自動検出して差分だけ取得できる。

画像タイプ（SchaleDB の images/student/ 配下）:
  icon       … アイコン（小さい顔アイコン）
  portrait   … 立ち絵（編成などで使われるポートレート）
  collection … コレクション（カード風の一枚絵）
  lobby      … メモリアルロビー（ホーム画面の全身イラスト）

使い方の例:
  # 今回の新キャラ3体の「立ち絵＋アイコン」を取得
  python3 fetch_student_images.py --ids 10143 10144 10145

  # 立ち絵・アイコン・コレクション・ロビーを全部取得
  python3 fetch_student_images.py --ids 10143 10144 10145 --types icon portrait collection lobby

  # ローカルに未取得の全生徒の icon+portrait をまとめて取得（差分同期）
  python3 fetch_student_images.py --missing

  # 何を落とすかだけ確認（ダウンロードしない）
  python3 fetch_student_images.py --missing --dry-run

  # 見やすいファイル名（Id_名前.webp）のコピーも別フォルダに出力
  python3 fetch_student_images.py --ids 10143 10144 10145 --named-copy ./_out
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_JSON = os.path.join(REPO_ROOT, "data", "jp", "students.json")
IMG_ROOT = os.path.join(REPO_ROOT, "images", "student")
BASE_URL = "https://schaledb.com/images/student"          # <type>/<Id>.webp
ALL_TYPES = ["icon", "portrait", "collection", "lobby"]
DEFAULT_TYPES = ["portrait", "icon"]                       # 立ち絵＋アイコン
UA = "Mozilla/5.0 (compatible; SchaleDB-image-fetch/1.0)"


def load_students():
    with open(DATA_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return {s["Id"]: s.get("Name", str(s["Id"])) for s in data}


def local_path(img_type, sid):
    return os.path.join(IMG_ROOT, img_type, f"{sid}.webp")


def safe_name(name):
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name


def download(url, dest, retries=3, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if not data:
                raise IOError("empty response")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            return True, len(data)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 404:      # 画像が存在しない（そのタイプが無い等）
                return False, last
        except Exception as e:     # noqa
            last = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(1.2 * attempt)
    return False, last


def main():
    ap = argparse.ArgumentParser(description="SchaleDB 生徒画像ダウンローダ")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ids", type=int, nargs="+", help="対象の生徒Id（複数可）")
    g.add_argument("--missing", action="store_true",
                   help="ローカルに画像が無い生徒を自動検出して取得")
    ap.add_argument("--types", nargs="+", default=DEFAULT_TYPES, choices=ALL_TYPES,
                    help=f"取得する画像タイプ（既定: {' '.join(DEFAULT_TYPES)}）")
    ap.add_argument("--out", default=IMG_ROOT,
                    help="保存先ルート（既定: リポジトリの images/student）")
    ap.add_argument("--named-copy", metavar="DIR",
                    help="Id_名前.webp 形式の見やすいコピーを別途出力するフォルダ")
    ap.add_argument("--overwrite", action="store_true", help="既存ファイルも上書き取得")
    ap.add_argument("--delay", type=float, default=0.4, help="各DL間の待機秒（既定0.4）")
    ap.add_argument("--dry-run", action="store_true", help="取得せず対象一覧だけ表示")
    args = ap.parse_args()

    names = load_students()

    # 対象Idの決定
    if args.ids:
        targets = args.ids
        unknown = [i for i in targets if i not in names]
        if unknown:
            print(f"[警告] data に無いId: {unknown}（画像は試行しますが名前は不明）")
    elif args.missing:
        targets = []
        for sid in names:
            if any(not os.path.exists(os.path.join(args.out, t, f"{sid}.webp"))
                   for t in args.types):
                targets.append(sid)
        targets.sort()
    else:
        ap.error("--ids か --missing のどちらかを指定してください")

    print(f"対象生徒: {len(targets)}体 / タイプ: {', '.join(args.types)}"
          + ("  (dry-run)" if args.dry_run else ""))

    ok = skip = fail = 0
    for sid in targets:
        nm = names.get(sid, "?")
        for t in args.types:
            dest = os.path.join(args.out, t, f"{sid}.webp")
            if os.path.exists(dest) and not args.overwrite:
                skip += 1
                continue
            url = f"{BASE_URL}/{t}/{sid}.webp"
            if args.dry_run:
                print(f"  [DL予定] {t:10} {sid} {nm}  <- {url}")
                ok += 1
                continue
            success, info = download(url, dest)
            if success:
                ok += 1
                print(f"  [OK] {t:10} {sid} {nm}  ({info:,} bytes)")
                if args.named_copy:
                    import shutil
                    nd = os.path.join(args.named_copy, t,
                                      f"{sid}_{safe_name(nm)}.webp")
                    os.makedirs(os.path.dirname(nd), exist_ok=True)
                    shutil.copyfile(dest, nd)
            else:
                fail += 1
                print(f"  [NG] {t:10} {sid} {nm}  ({info})")
            time.sleep(args.delay)

    print(f"\n完了: 取得/予定 {ok} ・ スキップ(既存) {skip} ・ 失敗 {fail}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
