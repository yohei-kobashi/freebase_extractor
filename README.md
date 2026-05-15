# Freebase エンティティ抽出ツール

指定したエンティティ ID リストに対応するトリプルを Freebase RDF ダンプから抽出するためのスクリプト群です。

- `get_freebase_entities.py` : ダンプから対象 ID の三つ組を抽出して JSONL に書き出します。
- `diagnose_freebase_entities.py` : 抽出が失敗・欠落した ID を診断し、原因の内訳を表示します。

> **注意 : 必要なファイルは手動で配置してください。**
> 本リポジトリの `.gitignore` では `*.json` / `*.jsonl` / `*.txt` を除外しているため、以下のファイルは Git では管理されません。クローン直後には存在しないので、各自で取得・作成してください。
>
> - `freebase-rdf-latest.gz` : Freebase RDF ダンプ (後述の手順でダウンロード)
> - `missing_entities2.txt` : 抽出対象の ID リスト (自分で用意)
> - `freebase_triples.jsonl` : `get_freebase_entities.py` が生成する出力ファイル

## 1. 元データのダウンロード

Freebase は 2016 年に提供を終了しており、最終 RDF ダンプは Google が静的ファイルとして公開しています。配布ページの案内は以下にあります。

- 配布案内ページ : <https://developers.google.com/freebase?hl=ja>
- RDF ダンプ本体 : <http://commondatastorage.googleapis.com/freebase-public/rdf/freebase-rdf-latest.gz>

スクリプトは作業ディレクトリ直下に `freebase-rdf-latest.gz` がある前提で動作します。`wget` で取得する場合は次のとおりです (約 30 GB、解凍後は 400 GB を超えるため、解凍はせず gzip のまま使ってください)。

```bash
wget -c -o freebase-download.log \
  http://commondatastorage.googleapis.com/freebase-public/rdf/freebase-rdf-latest.gz
```

`-c` を付けると中断時にレジューム可能、`-o` でログをファイルに残せます。本リポジトリの `freebase-download.log` は実際のダウンロード時のログです。

## 2. 入力 ID リストの準備

抽出したいエンティティの Freebase MID を 1 行 1 件のテキストファイルとして用意します。本リポジトリでは `missing_entities2.txt` を既定の入力としています。

```
m.04y_7zc
m.09l4yfc
m.04p8xnl
...
```

ID は `m.` または `g.` で始まるものを想定しています (`diagnose_freebase_entities.py` がそれ以外を malformed として報告します)。

## 3. エンティティの抽出 (`get_freebase_entities.py`)

`missing_entities2.txt` に列挙された ID を主語とするトリプルを RDF ダンプから走査し、`freebase_triples.jsonl` に追記します。

```bash
python get_freebase_entities.py
```

入力・出力のパスはスクリプト末尾の `extract(...)` 呼び出しでハードコードされています。変更したい場合は以下を編集してください。

```python
extract(
    "freebase-rdf-latest.gz",   # 入力 : Freebase RDF ダンプ (gzip 可)
    "freebase_triples.jsonl"    # 出力 : 抽出結果 (JSONL)
)
```

`missing_entities2.txt` のパスも `extract` 関数内に直接記述されているため、必要に応じて書き換えてください。

### 抽出される値

`<http://rdf.freebase.com/ns/>` 名前空間の三つ組のみを対象とし、各行を以下の JSON として書き出します。

```json
{"id": "m.0jqtzlw", "property": "exhibitions.exhibition_run.admission_fee", "value": "false"}
```

- 目的語が Freebase URI の場合 : `value` には接頭辞を取り除いた MID が入ります。
- 目的語がリテラルの場合 : クォート内の文字列が `value` に入ります。
- `type.object.name` (エンティティ名) は英語 (`@en`) のみを採用します。

### 動作上の注意

- 入力ファイルはマジックナンバーを見て自動的に gzip / 平文を判別します。
- 出力ファイルは追記ではなく上書きされます。
- 1 パスで全ダンプを走査するため、I/O 性能に依存しますが数時間オーダーの処理になります。

## 4. 抽出漏れの診断 (`diagnose_freebase_entities.py`)

指定 ID のうち RDF ダンプ内で「見つからなかった」「主語としては現れたが抽出対象から外れた」ものを分類して表示します。

```bash
python diagnose_freebase_entities.py \
  --input freebase-rdf-latest.gz \
  --ids missing_entities2.txt \
  --max-lines 100000000 \
  --sample-limit 20
```

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--input` | `freebase-rdf-latest.gz` | Freebase RDF ダンプ (gzip) |
| `--ids` | `missing_entities2.txt` | 対象エンティティ ID のリスト |
| `--max-lines` | なし (全件) | 走査する最大行数。動作確認時に短く設定します |
| `--sample-limit` | 20 | レポートで表示するサンプル ID 件数 |

### 出力レポートの読み方

- `subject_hit_ids` / `subject_hit_rows` : 主語として出現した ID 数と行数。
- `object_hit_ids` / `object_hit_rows` : 目的語側で参照された ID 数と行数。
- `extractable_ids` / `extractable_rows` : `get_freebase_entities.py` の条件で抽出可能だった ID 数と行数。
- `drop_reasons` : 抽出から外れた理由の内訳。主な値は次のとおりです。
  - `pred_not_freebase_ns` : 述語が Freebase 名前空間外
  - `literal_parse_fail` : リテラルのパース失敗
  - `name_not_en` : 名前 (`type.object.name`) が英語以外
  - `object_not_uri_or_literal` : 目的語が URI でもリテラルでもない
  - `unicode_decode_error` : UTF-8 への復号失敗
  - `short_line` : 3 カラムに満たない行
- `sample_subject_only` : 主語としてのみ出現した ID のサンプル。
- `sample_object_only` : 目的語としてのみ出現した ID のサンプル (リンク先として参照されているが定義レコードがない)。
- `sample_no_hits` : ダンプ中に一切出現しなかった ID のサンプル。
- `sample_seen_but_not_extractable` : 主語として現れたが抽出条件を満たさなかった ID のサンプル。

`malformed_ids` は `m.` / `g.` 以外で始まる ID の件数で、こちらも先頭から `--sample-limit` 件まで行番号付きで表示されます。

## 5. 推奨ワークフロー

1. `freebase-rdf-latest.gz` を取得する。
2. 対象 ID を `missing_entities2.txt` に書き出す。
3. `python get_freebase_entities.py` で抽出し、`freebase_triples.jsonl` を得る。
4. 期待件数に届かない場合は `python diagnose_freebase_entities.py` で原因を切り分け、ID リストや抽出条件を見直す。

## 6. 動作要件

- Python 3.8 以上 (標準ライブラリのみ使用)
- ディスク : RDF ダンプ用に 30 GB 以上の空き
- メモリ : ID リストをセットで保持するため数十 MB 程度 (ID 数に比例)

