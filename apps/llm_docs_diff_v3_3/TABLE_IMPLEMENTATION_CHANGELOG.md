# 表検出機能実装の変更ログ

## 1. v3-2からv3-3へのコピーと基本設定

### 1.1 ディレクトリ構造のコピー
```bash
cp -r apps/llm_docs_diff_v3_2 apps/llm_docs_diff_v3_3
```

### 1.2 設定ファイルの更新
**ファイル**: `apps/llm_docs_diff_v3_3/config/settings.py`
```python
# 変更前
OUTPUT_DIR = PROJECT_ROOT.parent.parent / "output" / "llm_diff_test_v3-2"

# 変更後（Line 39）
OUTPUT_DIR = PROJECT_ROOT.parent.parent / "output" / "llm_diff_test_v3-3"
```

## 2. コマンドライン引数の追加

**ファイル**: `apps/llm_docs_diff_v3_3/test_llm_diff_v3.py`

### 2.1 引数定義の追加（Line 48-51）
```python
parser.add_argument('--use-table-detection', action='store_true',
                    help='表構造を考慮した差分検出を有効化')
parser.add_argument('--no-table-detection', action='store_true',
                    help='表構造を無視して従来の方法で処理')
```

### 2.2 表検出フラグの処理（Line 126）
```python
print(f"    - 表検出機能: {'有効' if args.use_table_detection else '無効'}")
```

### 2.3 出力ディレクトリ名への反映（Line 146-153）
```python
# 表検出機能の有無でディレクトリ名を変更
if args.use_table_detection:
    output_base_dir = settings.OUTPUT_DIR.parent / "llm_diff_test_v3-3_standard_table"
else:
    output_base_dir = settings.OUTPUT_DIR.parent / "llm_diff_test_v3-3_standard"
```

## 3. 表マッチング機能の実装

### 3.1 TableMatcherクラスの作成
**新規ファイル**: `apps/llm_docs_diff_v3_3/core/table_matcher.py`

主要メソッド：
- `__init__` (Line 20-24): 閾値設定（cell_similarity_threshold=0.8）
- `match_tables` (Line 26-64): 表のマッチング処理
- `_group_by_structural_similarity` (Line 66-112): 構造的類似度でグループ化
- `_calculate_header_similarity` (Line 114-152): ヘッダー行の総当たりマッチング
- `_text_similarity` (Line 161-193): レーベンシュタイン距離によるテキスト類似度計算
- `_calculate_row_header_similarity` (Line 301-343): 1列目（行見出し）の類似度計算【後で追加】

### 3.2 構造類似度の計算方法
```python
# 初期実装（Line 91）
structure_similarity = header_similarity * 0.7 + size_similarity * 0.3

# 改善後（Line 94）
structure_similarity = header_similarity * 0.5 + row_header_similarity * 0.3 + size_similarity * 0.2
```

### 3.3 マッチング条件
```python
# 初期実装（Line 93）
if structure_similarity > 0.6:

# 改善後（Line 97-98）
header_match_count = len(header_matches) if isinstance(header_matches, list) else 0
if structure_similarity > 0.7 and header_match_count >= 2:
```

## 4. 表差分検出器の実装

### 4.1 TableAwareDiffDetectorクラスの作成
**新規ファイル**: `apps/llm_docs_diff_v3_3/core/table_aware_diff_detector.py`

主要メソッド：
- `__init__` (Line 22-48): 初期化処理
- `detect_differences` (Line 61-94): メインの差分検出メソッド
- `_extract_non_table_text` (Line 122-160): 表以外のテキストを抽出
- `_detect_table_differences` (Line 162-224): 表の差分を検出
- `_compare_matched_tables` (Line 226-376): マッチした表の比較
- `_match_rows_by_headers` (Line 385-444): 行見出しによる行マッチング【後で追加】

### 4.2 行マッチングアルゴリズムの実装（Line 271-349）
```python
# 変更前：単純な位置ベースの比較
for (row, col), cell1 in cells1_map.items():
    if (row, col) in cells2_map:
        cell2 = cells2_map[(row, col)]
        if cell1['text'] != cell2['text']:
            # 差分を記録

# 変更後：行見出しベースのマッチング
row_mapping = self._match_rows_by_headers(table1, table2, cells1_map, cells2_map)
for row1, row2 in row_mapping.items():
    # row1とrow2でマッチした行を比較
```

### 4.3 セル変更情報の拡張（Line 300-313）
```python
cell_changes.append({
    'row': row1,    # 表1の行番号
    'row2': row2,   # 表2の行番号を追加
    'column': col,
    'old_text': cell1['text'],
    'new_text': cell2['text'],
    'change_type': 'modified',
    'detailed_diff': detailed_diff  # MeCab解析結果（オプション）
})
```

## 5. 表差分結果モデルの作成

**新規ファイル**: `apps/llm_docs_diff_v3_3/models/table_models.py`

```python
@dataclass
class TableDiffResult:
    table_index1: Optional[int]
    table_index2: Optional[int]
    change_type: ChangeType
    structure_changes: List[str]
    cell_changes: List[Dict[str, Any]]
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON シリアライズ用のメソッド"""
        return {
            'table_index1': self.table_index1,
            'table_index2': self.table_index2,
            'change_type': self.change_type.value,
            'structure_changes': self.structure_changes,
            'cell_changes': self.cell_changes,
            'summary': self.summary
        }
```

## 6. デバッグハンドラーの実装

**新規ファイル**: `apps/llm_docs_diff_v3_3/core/table_debug_handler.py`

主要メソッド：
- `save_table_info` (Line 20-58): 表検出情報をJSONで保存
- `save_matching_info` (Line 60-102): マッチング情報を保存
- `save_diff_info` (Line 104-134): 差分情報を保存
- `save_tables_as_csv` (Line 136-172): 各表をCSVファイルとして保存

出力先：
- `debug/table_detection.json`
- `debug/table_matching.json`
- `debug/table_diffs.json`
- `debug/tables/table1_*.csv`
- `debug/tables/table2_*.csv`

## 7. Azureサービスの修正

**ファイル**: `apps/llm_docs_diff_v3_3/services/azure_service.py`

### 7.1 表抽出メソッドの修正（Line 129-223）
```python
def extract_tables(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
    # バウンディングボックス情報を追加
    if bounding_region and hasattr(bounding_region, 'polygon'):
        points = bounding_region.polygon
        # polygonから最小・最大座標を計算（Line 168-176）
        bbox = [
            min(x_coords),  # x
            min(y_coords),  # y
            max(x_coords) - min(x_coords),  # width
            max(y_coords) - min(y_coords)   # height
        ]
```

### 7.2 セルのバウンディングボックス追加（Line 190-211）
```python
cell_info = {
    'row': cell.row_index,
    'column': cell.column_index,
    'text': cell.content,
    'row_span': cell.row_span or 1,
    'column_span': cell.column_span or 1,
    'bbox': cell_bbox  # セルのバウンディングボックスを追加
}
```

## 8. 出力ハンドラーの修正

**ファイル**: `apps/llm_docs_diff_v3_3/handlers/output_handler.py`

### 8.1 表差分セクションの追加（Line 429-460）
```python
# 表の差分情報
if result.metadata and result.metadata.get("table_detection_used"):
    table_diffs = result.metadata["table_diffs"]
    if table_diffs:
        report_lines.extend([
            f"## 表の差分",
            f"検出された表の差分: {len(table_diffs)}件",
        ])
```

### 8.2 ハイライト処理の実装（Line 553-639）
```python
# 座標変換の修正（インチ→ポイント）
bbox_points = [coord * 72 for coord in cell['bbox']]

# row2を使用した正しい行番号での検索
target_row = cell_change.get('row2', cell_change.get('row'))
```

## 9. MeCab解析機能の追加

**新規ファイル**: `apps/llm_docs_diff_v3_3/core/cell_text_analyzer.py`

主要メソッド：
- `__init__` (Line 14-32): MeCab初期化（/etc/mecabrcを指定）
- `analyze_cell_diff` (Line 34-66): セル内テキストの詳細差分解析
- `_split_sentences` (Line 68-93): 文単位への分割
- `_compare_sentences` (Line 95-153): 文単位での比較
- `_analyze_morpheme_diff` (Line 155-223): 形態素単位での差分解析
- `_parse_morphemes` (Line 224-264): MeCabによる形態素解析

## 10. test_llm_diff_v3.pyの表検出対応

### 10.1 表検出処理の分岐（Line 235-276）
```python
if args.use_table_detection:
    # 表構造を考慮した差分検出
    table_aware_detector = TableAwareDiffDetector(debug_dir=debug_dir)
    diff_results, table_diffs = table_aware_detector.detect_differences(
        line_bbox_list1_filtered,
        line_bbox_list2_filtered,
        tables1, tables2
    )
else:
    # 従来の差分検出
    diff_detector = DiffDetector(debug_dir=debug_dir)
    diff_results = diff_detector.detect_differences(...)
```

### 10.2 メタデータへの表情報追加（Line 290-295）
```python
metadata = {
    "table_detection_used": args.use_table_detection,
    "tables1": tables1,
    "tables2": tables2,
    "table_diffs": [td.to_dict() for td in table_diffs] if args.use_table_detection else []
}
```

## 11. 主要な修正履歴

### 11.1 JSON シリアライズエラーの修正
- **問題**: `TypeError: Object of type TableDiffResult is not JSON serializable`
- **解決**: TableDiffResultに`to_dict()`メソッドを追加

### 11.2 バウンディングボックス座標変換
- **問題**: ハイライトが表示されない
- **原因**: Azure（インチ単位）→PDF（ポイント単位）の変換漏れ
- **解決**: `bbox_points = [coord * 72 for coord in cell['bbox']]`

### 11.3 行マッチングの改善
- **問題**: 行挿入時に後続行がすべて差分として検出される
- **解決**: 行見出し（1列目）による総当たりマッチング実装

### 11.4 表マッチング精度の改善
- **問題**: 異なる表が誤ってマッチされる
- **解決**: 
  - 閾値を0.6→0.7に引き上げ
  - 最小ヘッダーマッチ数2個の条件追加
  - 1列目の類似度も考慮

### 11.5 MeCabエラーの修正
- **問題**: `RuntimeError: no such file or directory: /usr/local/etc/mecabrc`
- **解決**: `-r /etc/mecabrc`オプションを指定