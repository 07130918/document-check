# PDF差分検出アルゴリズム詳細仕様書

## 1. 概要

本システムでは、2つのPDF文書間の差分を検出するために、主に2つのアルゴリズムを実装しています：
1. **PhraseBasedDiffDetector** (現在のベースライン)
2. **SequentialDiffDetector** (実験的実装)

## 2. PhraseBasedDiffDetector（フレーズベース差分検出器）

### 2.1 基本設計思想

- テキストをフレーズ（意味のある単位）に分割
- 集合ベースの比較（順序を考慮しない）
- 類似度に基づく差分判定

### 2.2 処理フロー

```
入力: doc1_text, doc2_text
↓
1. テキスト正規化（TextNormalizer）
   - 全角・半角の統一
   - 不要な空白の除去
   - 改行の正規化
↓
2. フレーズ分割（_segment_into_phrases）
   - MeCabによる形態素解析
   - 意味単位でのグループ化
   - フレーズタイプの分類
↓
3. フレーズ比較（_compare_phrase_sets）
   - 削除されたフレーズの検出
   - 追加されたフレーズの検出
   - 類似フレーズのペアリング
↓
4. 差分生成（_generate_differences）
   - 3種類の差分タイプを生成
     * DELETION（削除）
     * ADDITION（追加）
     * MODIFICATION（修正）
↓
出力: List[DiffResult]
```

### 2.3 フレーズ分割の詳細

#### フレーズタイプの分類
```python
phrase_types = {
    "年度": r"令和\d+年度|平成\d+年度",
    "日付": r"\d{1,2}月\d{1,2}日|令和\d+年\d{1,2}月\d{1,2}日",
    "URL": r"https?://[^\s]+",
    "数値": r"\d+(?:\.\d+)?",
    "括弧": r"[（(][^）)]+[）)]",
    # ... その他のパターン
}
```

#### 分割アルゴリズム
1. **基本分割**: 句読点、空白、改行での分割
2. **形態素解析**: MeCabによる品詞情報を利用
3. **パターンマッチング**: 特定パターンの抽出
4. **グループ化**: 意味的にまとまった単位への結合

### 2.4 差分検出ロジック

#### 削除・追加の検出
```python
def _compare_phrase_sets(self, phrases1, phrases2):
    set1 = set(p.text for p in phrases1)
    set2 = set(p.text for p in phrases2)

    # 削除: doc1にあってdoc2にない
    deleted = set1 - set2

    # 追加: doc2にあってdoc1にない
    added = set2 - set1

    # 共通: 両方にある（変更なし）
    common = set1 & set2
```

#### 類似度計算
```python
def _calculate_similarity(self, text1, text2):
    # 正規化
    norm1 = self.normalizer.normalize(text1)
    norm2 = self.normalizer.normalize(text2)

    # SequenceMatcherによる類似度
    return SequenceMatcher(None, norm1, norm2).ratio()
```

#### 修正の検出
- 削除されたフレーズと追加されたフレーズのペアリング
- 類似度閾値（デフォルト: 0.5）以上のペアを修正として検出

### 2.5 問題点と制限事項

1. **順序を考慮しない**
   - 文書内での位置変更を検出できない
   - 文脈依存の変更を見逃す可能性

2. **過剰な差分報告**
   - 1つの変更に対して削除・追加・修正の3つを報告
   - 適合率が低下（現在33.3%）

3. **フレーズ境界の曖昧さ**
   - 「iOS 11/12/13」が「iOS」と「11/12/13」に分割される問題
   - アノテーションとの不一致

## 3. SequentialDiffDetector（順序考慮型差分検出器）

### 3.1 基本設計思想

- 文書の順序を保持した差分検出
- 動的計画法による最適アラインメント
- 順序のズレを許容（window_size）

### 3.2 主要パラメータ

```python
def __init__(self, window_size: int = 3, similarity_threshold: float = 0.85):
    """
    Args:
        window_size: 順序のズレを許容する範囲（前後のフレーズ数）
        similarity_threshold: 類似と判定する閾値
    """
```

### 3.3 アラインメントアルゴリズム

#### DPテーブルの構築
```python
# dp[i][j] = (score, action, prev_i, prev_j)
# score: 最適スコア
# action: 'match', 'substitute', 'delete', 'insert'
# prev_i, prev_j: バックトラック用の前の位置

for i in range(1, n + 1):
    for j in range(1, m + 1):
        # window内の範囲で最適なマッチングを探す
        for k in range(max(0, j - window_size), j):
            similarity = calculate_similarity(phrases1[i-1], phrases2[j-1])
            if similarity >= similarity_threshold:
                # マッチ or 置換として記録
```

### 3.4 評価結果

実験結果（accuracy_evaluation_20250705_030157.md）より：

| アルゴリズム | 適合率 | 再現率 | F1スコア |
|------------|--------|--------|----------|
| phrase_based | 0.400 | 0.909 | 0.556 |
| sequential_w3 | 0.385 | 0.455 | 0.417 |

順序を考慮することで、逆に性能が低下した。

## 4. 共通コンポーネント

### 4.1 TextNormalizer（テキスト正規化）

```python
class TextNormalizer:
    def normalize(self, text: str) -> str:
        # 1. 全角英数字を半角に変換
        # 2. 半角カナを全角に変換
        # 3. 連続する空白を単一に
        # 4. 改行の正規化
        # 5. 前後の空白を除去
```

### 4.2 MeCabTokenizer（形態素解析）

```python
class MeCabTokenizer:
    def tokenize(self, text: str) -> List[Token]:
        # MeCabによる形態素解析
        # 品詞情報の抽出
        # トークンオブジェクトの生成
```

### 4.3 DiffResult（差分結果）

```python
@dataclass
class DiffResult:
    change_type: ChangeType  # ADDITION, DELETION, MODIFICATION
    confidence_score: float  # 信頼度スコア
    original_text: Optional[str]  # 元のテキスト
    modified_text: Optional[str]  # 変更後のテキスト
    similarity_score: float = 0.0  # 類似度
    detection_method: str = ""  # 検出手法
```

## 5. 評価方法

### 5.1 部分一致評価（_is_partial_match）

```python
def _is_partial_match(self, detected: Tuple[str, str], truth: Tuple[str, str]) -> bool:
    # 完全一致
    if det_orig == truth_orig and det_mod == truth_mod:
        return True

    # 部分一致（どちらかがどちらかに含まれる）
    orig_match = (det_orig in truth_orig or truth_orig in det_orig)
    mod_match = (det_mod in truth_mod or truth_mod in det_mod)

    return orig_match and mod_match
```

### 5.2 評価指標

- **True Positive (TP)**: 正しく検出された差分
- **False Positive (FP)**: 誤検出
- **False Negative (FN)**: 検出漏れ
- **適合率 (Precision)**: TP / (TP + FP)
- **再現率 (Recall)**: TP / (TP + FN)
- **F1スコア**: 2 * (Precision * Recall) / (Precision + Recall)

## 6. 現在の課題と改善方向

### 6.1 アルゴリズムの課題

1. **重複した差分報告**
   - 解決案: 差分タイプの優先順位付け
   - MODIFICATIONが検出されたら、DELETION/ADDITIONを抑制

2. **フレーズ分割の精度**
   - 解決案: コンテキストを考慮した分割
   - 機械学習ベースの境界検出

3. **順序変更の扱い**
   - 解決案: REORDERタイプの導入
   - 内容は同じで位置のみ変更を別扱い

### 6.2 評価の課題

1. **アノテーション仕様**
   - 文脈情報の不足
   - 評価基準の曖昧さ

2. **部分一致の定義**
   - どこまでを正解とするか不明確
   - マッチング方式の明示が必要

### 6.3 改善ロードマップ

1. **短期（1-2週間）**
   - アノテーション仕様の改善
   - 重複差分の抑制ロジック実装

2. **中期（1-2ヶ月）**
   - フレーズ分割の精度向上
   - 文脈を考慮した差分検出

3. **長期（3ヶ月以上）**
   - 機械学習ベースの差分検出
   - 意味的な変更の理解
