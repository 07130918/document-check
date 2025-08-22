# llm_docs_diff_v3/v5 問題分析と改善施策

## 1. 検出された問題の詳細分析

### 1.1 改行による誤検出問題

**問題**:
Document Intelligenceが1行単位でBBOXを返すため、文書間で改行が入ると誤検出する（sample1 p4など）

**原因**:
- v3では`extract_layout_from_lines()`を使用し、行単位でテキストを抽出
- 改行位置が変わると、同じ内容でも別の行として扱われる
- 例: 「これは長い文章です」が「これは長い」「文章です」に分割されると別要素として検出
- SimpleDiffDetectorV3のdifflibベースの比較では、順序が重要なため誤検出が増加

**対応策**:
1. **テキスト結合アルゴリズムの実装**
   - 改行で分割された可能性のある行を結合
   - 同一段落と判定される行をマージ
2. **段落単位での処理への切り替え**
   - `extract_layout_from_paragraphs()`メソッドの使用
   - v5で実証済みの効果的なアプローチ

### 1.2 テキスト抽出失敗問題

**問題**:
画像内テキスト（漫画など）など、複数箇所でDocument Intelligenceがテキストを抽出できていない

**原因**:
- v3では`prebuilt-layout`モデルを使用（レイアウト解析特化）
- `prebuilt-layout`は構造化されたテキストは抽出するが、画像内テキストはOCRしない
- v5では`prebuilt-read`モデルを使用（OCR特化）で、より広範囲のテキストを検出

**対応策**:
```python
# azure_service_enhanced.pyの修正
def extract_layout_with_hierarchy(self, pdf_bytes: bytes, use_ocr_model: bool = True):
    model_id = "prebuilt-read" if use_ocr_model else "prebuilt-layout"
    poller = self.client.begin_analyze_document(model_id, ...)
```

### 1.3 テキスト認識誤り問題

**問題**:
「補償内容」の「内」が「內」として誤認識される．誤検出につながるのみなので，重要度：低

**原因**:
- Azure Document Intelligenceの`prebuilt-layout`モデルのテキスト認識精度の限界
- 日本語の異体字や類似文字の誤認識が発生
- v3の前処理では全角・半角変換は実装されているが、漢字の異体字修正は未実装

**対応策**:
```python
# text_preprocessing.pyに追加
OCR_CORRECTION_PATTERNS = {
    '內': '内',
    '巳': '己',
    '已': '己',
    # その他の一般的な誤認識パターン
}

def correct_ocr_errors(text: str) -> str:
    for wrong, correct in OCR_CORRECTION_PATTERNS.items():
        text = text.replace(wrong, correct)
    return text
```

### 1.4 BBOX結合問題

**問題**:
文書1で「有限会社矯正サービス」が下の「東京都～」とBBOXが結合している

**原因**:
- Azure Document Intelligence APIの仕様：`prebuilt-layout`モデルは近接するテキストを1つの行として認識する傾向
- 行の境界判定アルゴリズムが垂直方向の間隔を十分に考慮していない

**対応策**:
- ブロック単位抽出を導入し，様子を見る

### 1.5 粒度の問題

**問題**:
現在の処理は1行全体のBBOX出力だが、要件定義では単語単位が必要

**原因**:
- v3は行単位での差分検出を実装
- 単語レベルの処理は未実装
- 反対に、v5では1文字単位になりすぎて見にくい

**対応策**:
差分検出後に単語レベルに変換する後処理を実装：
```python
def convert_to_word_level(diff_results: List[DiffResult]) -> List[DiffResult]:
    """行レベルの差分を単語レベルに変換"""
    word_level_results = []

    for result in diff_results:
        if result.change_type == ChangeType.MODIFICATION:
            # 変更箇所を単語レベルで特定
            word_diffs = find_word_level_changes(
                result.original_bbox['text'],
                result.modified_bbox['text'],
                result.original_bbox['bbox'],
                result.modified_bbox['bbox']
            )
            word_level_results.extend(word_diffs)
        else:
            # 追加・削除は行全体を単語に分割
            words = split_to_words(result)
            word_level_results.extend(words)

    return word_level_results
```

## 2. 実装優先順位

1. **高優先度**
   - OCRモデルへの切り替え（画像内テキスト対応）
   - 改行問題への対策（テキスト結合または段落単位処理）

2. **中優先度**
   - 単語単位への変換
   - OCR誤認識パターンの拡充

3. **低優先度**
   - BBOX分離アルゴリズム（複雑なケースへの対応）

## 3. テスト項目

各改善施策の実装後、以下のテストケースで検証：

1. **改行テスト**: sample1 p4での誤検出が解消されるか
2. **画像内テキスト**: 2Pの漫画内文章や他の画像内テキストが検出されるか
3. **OCR精度**: 「內」→「内」の修正が機能するか
4. **BBOX分離**: 結合されたテキストが適切に分離されるか
5. **単語粒度**: 差分が単語単位で表示されるか

--------------------
横山TODO
v3とv5でどこまでアルゴリズムが修正できているかよくわからないので，v3基準で修正する
- ブロック単位抽出の追加(v3を基準に追加していく)
- 出力を単語レベルに変換(v3)
- Azure Document Intelligence 技術調査
- baseline アルゴリズムの明確化・テストファイル（暫定サンプル2）の評価を実行
