---
name: update-schaledb-from-wikiru
description: SchaleDB フォーク（nico0748/SchaleDB）に、ブルアカ攻略 wikiru で実装済みなのに未登録の新生徒・衣装違いを見つけ、生徒データと画像を取り込んで PR にするときに使う。
---

# SchaleDB を wikiru から新生徒で更新する

収集元は **https://bluearchive.wikiru.jp/ のみ**。変換は `tools/wikiru_sync.py` が行う。

## 0. 前提

- リポジトリ: `nico0748/SchaleDB`（`data/<lang>/students(.min).json` は `{"<Id>": {...}}` のオブジェクト形式、indent 4）
- ネットワークで `bluearchive.wikiru.jp` が許可されていること。403 で拒否されたら環境の許可ホストに追加を依頼する
- robots.txt: ページ閲覧と `attach2/` の画像は可、`cmd=` / `plugin=`（ref/attach の openfile 以外）は不可。GPTBot 等は全面禁止なので UA は汎用名
- リクエスト間隔はツール既定の 3 秒を守る。キャッシュ（`--cache`、既定 `.wikiru_cache/`、gitignore 済み）があれば再取得しない
- Pillow が必要（`python3 -c "import PIL"`）

## 1. 差分を確認

```bash
python3 tools/wikiru_sync.py diff --cache <scratch>/wikiru_cache
```

wikiru「キャラクター一覧」とローカル `data/jp/students.json` を **名前の完全一致**で比較し、未登録を表示する。
「ローカルのみ」に出た名前は表記ゆれ（例: 括弧の種類）なので、追加前に確認する。

## 2. パーサの健全性チェック（毎回）

wikiru のページ構造が変わっていないか、正式データがある既存生徒で照合する。

```bash
python3 tools/wikiru_sync.py verify --names コトネ --cache <scratch>/wikiru_cache
```

ステータスの ±1 の丸め差と、wikiru 側がテンプレートのままの素材（`主素材(下級)名` 等）による素材差異は許容。
ステータス・スキル名・パラメータ・武器などで大きくずれたら、`parse_page()` を直してから進む。

## 3. 取り込み

PathName（URL 用ローマ字）を全員分 `--map` で指定する。衣装違いは `<元生徒>_<衣装>`（例 `kasumi_swimsuit`, `azusa_racing`）。
既存の localization に無い部活は `--club '日本語名=キー'` で指定する（未指定だとツールが止まって教えてくれる）。

```bash
python3 tools/wikiru_sync.py build --cache <scratch>/wikiru_cache \
  --map 'アンナ=anna' 'カスミ（水着）=kasumi_swimsuit' \
  --club '183号特別クラス=Class183'
```

まず `--dry-run` で内容を確認するとよい。ツールがやること:

- Id を採番（新規★3 → 10xxx、衣装違い★3 → 20xxx、★1 → 26xxx の各最大値+1）、DefaultOrder は末尾に追加
- 7 言語すべての `students.json` / `students.min.json` に同じエントリ（日本語）を追加
- `"Source": "wikiru"`, `"DataPartial": true` を付与
- 画像を WebP に変換して保存: icon(120×120) / portrait(高さ1280) / lobby(182×144 中央切り抜き) /
  collection(立ち絵の頭部を切り抜いた仮画像 200×226) / 固有武器アイコン(800×205, CHxxxx のもの) / 固有スキルアイコン
- 衣装違いで武器アイコンに CH 番号が無い場合は元生徒の `WeaponImg` を流用、DevName はスキルアイコンの CH 番号から取る

## 4. 確認

```bash
python3 - <<'E'
import json
d = json.load(open('data/jp/students.json')); ref = d['10150']
for k, e in d.items():
    if e.get('Source') == 'wikiru':
        print(k, e['Name'], [x for x in ref if x not in e], e['MemoryLobby'])
E
```

- 全言語で `students.json == students.min.json` かつ件数一致
- 生徒ごとに既存エントリとキー・型が揃っている
- 画像を目視（コンタクトシートを作って Read で見る）。立ち絵が別バリエーション（`_2.png` 等）になっていないか
- 注意: `js/common.min.js`(v302) はオブジェクト形式の data に未対応で、サイト自体がローカルで読み込み中のまま止まる（既知の既存問題）。ブラウザでの表示確認はこれが直るまでできない

## 5. 記録と PR

- `DATA_NOTICE.md` の先頭に日付つきセクションを追加: 追加生徒の表（仮Id・名前・★・学校・部活・攻撃・防御・武器・役割）、
  取れなかった項目、追加画像の内訳
- ブランチ `data/wikiru-<YYYY-MM-DD>` で commit → push → draft PR
- PR 本文に「仮 Id」「collection は仮画像」「wikiru に無い項目」を明記

## schaledb.com 正式データが出た後

正式データで同期するときは、`Source == "wikiru"` のエントリを **名前で照合して削除してから** 取り込む（Id が変わることがある）。
仮 Id の画像（`images/student/*/<仮Id>.webp`）も消す。
