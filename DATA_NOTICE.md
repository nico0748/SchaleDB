# データ・画像の出典に関する注意（免責）

このリポジトリは [SchaleDB](https://schaledb.com/) の個人フォークです。
本ファイルは、フォーク側で行ったデータ・画像の更新について記録するものです。

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
