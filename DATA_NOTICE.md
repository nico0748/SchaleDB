# データ・画像の出典に関する注意（免責）

このリポジトリは [SchaleDB](https://schaledb.com/) の個人フォークです。
本ファイルは、フォーク側で行ったデータ・画像の更新について記録するものです。

## 2026-11-22 更新（wikiru から新生徒を追加）

ブルアカ攻略 wikiru（`https://bluearchive.wikiru.jp/`）のキャラクター一覧（281行）と突き合わせ、
本フォーク未登録の **7名** を wikiru の各生徒ページから取り込みました（`tools/wikiru_sync.py`）。

- 生徒数: 274件 → **281件**（全言語。他言語ファイルにも日本語のまま追加）

| Id（仮） | 名前 | ★ | 学校 | 部活 | 攻撃 | 防御 | 武器 | 役割 |
|---|---|---|---|---|---|---|---|---|
| 10151 | アンナ | 3 | RedWinter | Class183（183号特別クラス） | Pierce | LightArmor | HG | DamageDealer / Middle |
| 10152 | エリナ | 3 | RedWinter | Class183 | Sonic | LightArmor | HG | Supporter / Back |
| 10153 | ツムギ | 3 | WildHunt | OccultClub | Pierce | Unarmed | SMG | Tanker / Front |
| 20061 | アズサ（レーシング） | 3 | Trinity | RemedialClass | Explosion | Unarmed | AR | Supporter / Back |
| 20062 | カスミ（水着） | 3 | Gehenna | HotSpringsDepartment | Pierce | Unarmed | HG | Supporter / Back |
| 20063 | ヒフミ（レーシング） | 3 | Trinity | RemedialClass | Explosion | Unarmed | AR | DamageDealer / Middle |
| 26017 | ラナ | 1 | RedWinter | Class183 | Explosion | Unarmed | SG | Vehicle / Back |

いずれも `"Source": "wikiru"` / `"DataPartial": true` を持つ**部分データ**です。
`IsReleased` は `[true, false, false]`（日本のみ）。localization の `Club` に `Class183` を追加しました。

### wikiru から取れたもの / 取れなかったもの

- **取得**: プロフィール（フルネーム・ルビ・学年・年齢・誕生日・身長・趣味・CV・イラスト/デザイン・紹介文）、
  ステータス（★3 Lv90 の値から Lv1/Lv100 を逆算。既存のコトネで照合し ±1 以内）、地形適性、装備、
  スキル5種（名前・説明・レベル別数値・EXコスト・アイコン）、固有武器（名前・説明・Lv1/Lv100・★3地形強化）、
  絆ランクボーナス、スキル育成素材、能力解放素材、メモリアルロビー解放ランク（記載がある生徒のみ）
- **取得できず空/仮**: `Id`（下記）、スキルの `Effects`（ダメージ計算用の内部値）、通常攻撃（同じ武器種の既存生徒から流用）、
  `CharacterSSRNew`（加入時セリフ）、贈り物の好み・家具インタラクション、`MemoryLobbyBGM`、
  エリナとカスミ（水着）のメモロビ解放ランク、弾数・弾コスト（同武器種の中央値）、`Size`（Medium 固定）

### Id について

wikiru には内部 Id が無いため、既存の採番規則に沿って**仮の Id** を振っています
（新規★3 = 10xxx、衣装違い★3 = 20xxx、★1 = 26xxx）。
schaledb.com 側に正式データが出たら、**同名の wikiru エントリを削除してから**正式データに置き換えてください（Id が変わる可能性があります）。

### 画像（36ファイル追加、すべて wikiru の添付画像を WebP 変換）

- `images/student/icon` … 一覧のアイコン（120×120 に縮小）= 7件
- `images/student/portrait` … 生徒ページのメイン立ち絵（高さ 1280px）= 7件
- `images/student/lobby` … メモリアルロビー画像を 182×144 に中央切り抜き = 7件
- `images/student/collection` … **立ち絵の頭部付近を切り抜いた仮画像**（wikiru に同等の画像が無いため）= 7件
- `images/weapon` … `weapon_icon_ch0252` / `ch0320` / `ch0321` / `ch0322` = 4件
  （衣装違い3名は元生徒の武器アイコンを参照）
- `images/skill` … 固有スキルアイコン 4件

### 既知の問題（今回の更新以前から）

2026-08-22 のフルデータ同期以降、`data/*/students.min.json` などは schaledb.com の新しい
**オブジェクト形式（`{"10000": {...}}`）**ですが、本フォークの `js/common.min.js`（v302）は
**配列形式**を前提にしているため、ローカルで `index.html` を開くと読み込み中のまま止まります
（`data.students.sort is not a function`）。今回の追加データ自体は既存エントリと同じキー・型であることを確認済みです。

## 2026-08-31 更新（差分同期）

前回（2026-08-22）以降の schaledb.com ライブデータとの差分を取り込みました。
158ファイル中 **116ファイルに更新**があり、それらのみを入れ替えています
（currency / equipment / summons / config / groups は無変更のため据え置き）。

- 生徒数: 272件 → **274件**（全言語）

### 今回追加された生徒（日本サーバー実装分）

| Id | 名前 | ★ | 学校 | 部活 | 攻撃属性 | 武器 | 役割 | CV |
|---|---|---|---|---|---|---|---|---|
| 10149 | ココロ | 3 | Odyssey | DivingClub | Mystic | AR | Supporter / Middle | 百瀬紗菜 |
| 10150 | コトネ | 3 | Odyssey | DivingClub | Explosion | AR | Tanker / Front | 天音ゆかり |

いずれも `IsReleased` は `[true, false, false]`（日本のみ実装）です。
**Odyssey（オデュッセイア）は本フォークで初登場の学校**です。

### 画像（16ファイル追加）

- `images/student/{icon,portrait,collection,lobby}` … 10149 / 10150 の各4種 = 8件
- `images/weapon` … `weapon_icon_ch0368` / `ch0369` = 2件
- `images/skill` … `SKILLICON_CH0368_EXTRAPASSIVESKILL` / `CH0369_...` = 2件
- `images/background` … `BG_OdysseyWharf` = 1件
- `images/schoolicon` … ODYSSEY / WILDHUNT / HIGHLANDER = 3件

### 学校アイコンの命名について（注意）

schaledb.com は学校アイコンを `images/schoolicon/Odyssey.png` のような
**新しい命名**に移行しています。一方、本フォークの `js/` は v302 時点のコードで、
`School_Icon_<大文字>_W.png` を組み立てて参照します。
そのため取得した新命名のPNGを**旧命名にリネームして格納**しました。

- `Sakugawa`（佐天涙子の所属・柵川中学）のアイコンは、
  新旧どちらの命名でも schaledb.com に存在しないため**未取得**です。
  これは今回の更新による欠落ではなく、以前からの状態です。

### 検証結果

全274生徒の icon / portrait / collection / lobby、および参照される
武器アイコン・スキルアイコン・背景に欠落なし。全言語で生徒IDが一致。
`localization.json` の参照キー欠落なし。

なお wikiru のキャラクター一覧（274件）とも突き合わせ、新規実装が
ココロ・コトネの2名であることを確認しています。
ただし防御タイプについては wikiru が「特殊装甲」、schaledb.com が
`Unarmed`（未武装）と食い違っています。本データは schaledb.com 側を採用しています。

## 2026-08-22 更新（フルデータ同期）

`data/` 配下および `images/` 配下を **schaledb.com のライブデータで総入れ替え**しました。

### データ

- 対象: 7言語（cn / en / jp / kr / th / tw / zh）× 11種
  （currency, enemies, equipment, furniture, items, localization,
  　raids, stages, students, summons, voice）の `.json` / `.min.json`、
  および `config` / `groups` — 計 **158ファイル**
- 生徒数: 267件 → **272件**（全言語）
- `crafting_cn` / `crafting_global` / `crafting_jp` は、現在 schaledb.com が
  当該パスを配信していない（SPAのHTMLが返る）ため **更新対象から除外**し、
  従来のファイルをそのまま残しています。

### 今回追加された生徒（日本サーバー実装分）

| Id | 名前 | ★ | 学校 | 攻撃属性 | 武器 |
|---|---|---|---|---|---|
| 10146 | マコト（水着） | 3 | Gehenna | Mystic | SR |
| 10147 | サツキ（水着） | 3 | Gehenna | Sonic | HG |
| 10148 | イロハ（水着） | 3 | Gehenna | Explosion | HG |
| 20060 | イブキ（水着） | 3 | Gehenna | Explosion | AR |
| 26016 | チアキ（水着） | 1 | Gehenna | Pierce | AR |

いずれも `IsReleased` は `[true, false, false]`（日本のみ実装）です。

### 画像

不足していた **180ファイル**を追加しました。

| 種別 | 追加数 | 更新後 |
|---|---|---|
| `images/student/collection` | 75 | 272 |
| `images/student/icon` | 5 | 272 |
| `images/student/portrait` | 5 | 284 |
| `images/student/lobby` | 5 | 272 |
| `images/weapon` | 33 | 155 |
| `images/skill` | 41 | 143 |
| `images/background` | 16 | 61 |

全生徒の icon / portrait / collection / lobby、および
データが参照する武器アイコン・スキルアイコン・背景に欠落がないことを確認済みです。

## 以前の「wikiru由来」追記について（解消済み）

2026-07 以前、本フォークには元データに無かった生徒 **73件** を
ブルアカ攻略 wikiru（`https://bluearchive.wikiru.jp/`）を参考に追記していました。
これらは `"Source": "wikiru"` / `"DataPartial": true` を持つ部分データで、
戦闘ステータス等が空であり、ID・名前にズレを含むものがありました
（例: `シュエリン（水着）` は実際には `シュン（水着）` id:10144）。

今回のライブデータ同期により **これらは全て正式データに置き換わり、
`Source` / `DataPartial` を持つエントリは 0 件になりました。**

なお wikiru は、今回の更新でも「どの生徒が新規実装されたか」を突き合わせる
参照先として利用しています。データ本体・画像は schaledb.com から取得しています。

## 権利に関する注意

本フォークは、ブルーアーカイブのファンによる**二次創作・非営利**の用途を目的としたものです。

- 株式会社Yostar、NEXON Games、および「ブルーアーカイブ」運営とは**一切関係がなく、
  公式に許諾・承認されたものではありません（非公式・非公認）**。
- 「ブルーアーカイブ」および生徒名・キャラクター・画像等の著作権・商標等の権利は、
  すべて権利者に帰属します。
- **本リポジトリには生徒画像（icon / portrait / collection / lobby 等）が含まれます。**
  これらは SchaleDB が公開しているものを取得したもので、権利は権利者に帰属します。
- 本フォークは**ブルーアーカイブの二次創作ガイドラインの範囲内での利用を意図**しており、
  **公式ガイドラインに抵触する意図はありません。**
- 権利者・運営からの削除・修正等のご要請があった場合は、**速やかに対応します**。
- 最新の公式二次創作ガイドラインは、必ずご自身で公式サイトにてご確認ください。
