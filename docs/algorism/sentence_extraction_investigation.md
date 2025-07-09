# 文章抽出問題に関する調査ドキュメント

## 1. 問題の概要

### 1.1 現状の課題
- **入力データ**: 単語単位のbbox_text_data（PyMuPDF等から取得）
- **要求仕様**: 読み順序推定は文章単位で行う必要がある
- **問題点**: 単語から文章へのグルーピングが不完全で、文章境界の判定が困難

### 1.2 影響範囲
- 読み順序推定の精度低下
- 複雑なレイアウトでの文章認識エラー
- 評価時の判定基準の曖昧さ

## 2. 技術的課題の詳細

### 2.1 文章境界判定の困難さ

#### 2.1.1 日本語特有の課題
- **句読点の不規則性**: 
  - 箇条書きでは句点がない場合が多い
  - 見出しやタイトルに句読点がない
  - 表内テキストでの句読点省略
- **改行の扱い**:
  - PDFでは表示幅に応じて任意の位置で改行
  - 論理的な文章の区切りと物理的な改行が一致しない
  - 段落内改行と段落間改行の区別が困難

#### 2.1.2 レイアウトによる課題
- **カラムレイアウト**:
  - 複数カラムでの文章の続き判定
  - カラム間の読み順序推定
- **表構造**:
  - セル内の文章とセル間の関係
  - ヘッダーとデータの区別
- **箇条書き・リスト**:
  - インデントレベルの認識
  - 番号付き/番号なしリストの判定

### 2.2 bbox情報からの文章グルーピング課題

#### 2.2.1 座標ベースの判定限界
```python
# 現状の単純な近接判定の例
def is_same_sentence(bbox1, bbox2, threshold=10):
    # y座標の差が閾値以内なら同一行と判定
    return abs(bbox1[1] - bbox2[1]) < threshold
```

この方法では以下の問題が発生：
- フォントサイズの違いを考慮できない
- 上付き・下付き文字の誤判定
- 行間の変動への対応困難

#### 2.2.2 文脈情報の欠如
- 単語の品詞情報がない
- 文法的なつながりを判定できない
- 意味的な区切りを認識できない

## 3. 現状の対処方法と限界

### 3.1 ヒューリスティックなアプローチ

#### 3.1.1 実装例
```python
def group_words_to_sentences(bbox_list):
    sentences = []
    current_sentence = []
    
    for i, bbox in enumerate(bbox_list):
        current_sentence.append(bbox)
        
        # 文末判定の条件
        if any(ending in bbox['text'] for ending in ['。', '！', '？', '\n']):
            sentences.append(current_sentence)
            current_sentence = []
        # 次の単語との距離が大きい場合も文章区切りと判定
        elif i < len(bbox_list) - 1:
            next_bbox = bbox_list[i + 1]
            if calculate_distance(bbox, next_bbox) > SENTENCE_BREAK_THRESHOLD:
                sentences.append(current_sentence)
                current_sentence = []
    
    return sentences
```

#### 3.1.2 限界
- 固定的なルールでは多様なレイアウトに対応困難
- 文書タイプごとの調整が必要
- エッジケースが多数存在

### 3.2 機械学習アプローチの可能性

#### 3.2.1 教師あり学習
- **必要なデータ**: 文章境界がアノテーションされた学習データ
- **特徴量**:
  - bbox座標の相対位置
  - 単語間距離
  - フォントサイズ
  - 前後の単語内容
- **課題**: 大量のアノテーションデータが必要

#### 3.2.2 ルールベースと機械学習のハイブリッド
- 基本的なルールで初期分割
- 機械学習モデルで境界の調整
- 信頼度スコアによる判定

## 4. 評価時の考慮事項

### 4.1 文章抽出の不完全さを前提とした評価

#### 4.1.1 評価基準の調整
- **完全一致評価から部分一致評価へ**:
  - 文章の70%以上が正しくグループ化されていれば「部分的に正しい」
  - 重要な意味単位が保持されているかを重視
- **エラータイプの分類**:
  - 過分割: 1文を複数に分割
  - 過結合: 複数文を1つに結合
  - 順序エラー: 文章の順序が入れ替わる

#### 4.1.2 レイアウト別評価
```markdown
| レイアウトタイプ | 期待精度 | 許容エラー率 |
|-----------------|----------|-------------|
| 単一カラム本文   | 90-95%  | 5-10%      |
| 2カラムレイアウト | 80-90%  | 10-20%     |
| 表構造          | 70-80%  | 20-30%     |
| 複雑な混在      | 60-70%  | 30-40%     |
```

### 4.2 評価シートへの反映

#### 4.2.1 文章抽出品質の記録項目
- 文章境界の正確性（5段階評価）
- 主要なエラータイプ
- レイアウトの複雑度
- 改善提案

#### 4.2.2 総合評価への重み付け
- 読み順序評価: 40%（文章抽出の影響を考慮）
- 差分検出評価: 60%（単語単位なので影響少）

## 5. 改善提案

### 5.1 短期的改善（現実的な対応）

#### 5.1.1 パラメータチューニング
- 文書タイプ別の閾値設定
- フォントサイズを考慮した動的閾値
- 行間隔の統計的分析

#### 5.1.2 後処理の追加
- 明らかな過分割の結合
- 短すぎる文章の前後結合
- 句読点ベースの補正

### 5.2 中長期的改善

#### 5.2.1 追加情報の活用
- フォント情報（サイズ、スタイル）
- 段落インデント情報
- ページ内の相対位置

#### 5.2.2 外部ツールの検討
- 自然言語処理ライブラリとの連携
- 文書構造解析専用ツール
- OCRエンジンの文章認識機能

## 6. 実装推奨事項

### 6.1 現状での最適化案

```python
class SentenceExtractor:
    def __init__(self, 
                 line_threshold: float = 5.0,
                 paragraph_threshold: float = 15.0,
                 min_sentence_length: int = 3):
        self.line_threshold = line_threshold
        self.paragraph_threshold = paragraph_threshold
        self.min_sentence_length = min_sentence_length
    
    def extract_sentences(self, bbox_list: List[BBoxTextData]) -> List[List[BBoxTextData]]:
        """単語単位のbboxデータから文章単位にグルーピング"""
        sentences = []
        current_sentence = []
        
        for i, bbox in enumerate(bbox_list):
            current_sentence.append(bbox)
            
            # 文末判定
            if self._is_sentence_end(bbox, i, bbox_list):
                if len(current_sentence) >= self.min_sentence_length:
                    sentences.append(current_sentence)
                current_sentence = []
        
        # 残りの処理
        if current_sentence:
            sentences.append(current_sentence)
        
        return sentences
    
    def _is_sentence_end(self, bbox: BBoxTextData, index: int, bbox_list: List[BBoxTextData]) -> bool:
        """文章の終わりかどうかを判定"""
        # 句読点チェック
        if bbox['text'].endswith(('。', '！', '？')):
            return True
        
        # 最後の要素
        if index == len(bbox_list) - 1:
            return True
        
        # 次の要素との距離チェック
        next_bbox = bbox_list[index + 1]
        y_distance = abs(next_bbox['bbox'][1] - bbox['bbox'][1])
        
        # 改行判定
        if y_distance > self.line_threshold:
            # 段落変更の可能性
            if y_distance > self.paragraph_threshold:
                return True
            # 行末での区切り判定（日本語の特性を考慮）
            if self._is_likely_line_break(bbox['text']):
                return True
        
        return False
    
    def _is_likely_line_break(self, text: str) -> bool:
        """行末での自然な区切りかどうかを判定"""
        # 助詞で終わっている場合は続く可能性が高い
        if text.endswith(('の', 'を', 'に', 'が', 'と', 'で', 'から', 'まで')):
            return False
        # 名詞・動詞で終わっている場合は区切りの可能性
        return True
```

### 6.2 評価への反映

```python
class ReadingOrderEvaluator:
    def evaluate_with_sentence_extraction_consideration(self, 
                                                      system_output: List[int],
                                                      ground_truth: List[int],
                                                      extraction_quality: float) -> float:
        """文章抽出の品質を考慮した読み順序評価"""
        base_score = self.calculate_base_score(system_output, ground_truth)
        
        # 文章抽出品質による調整
        # extraction_quality: 0.0-1.0 (1.0が完全)
        adjusted_score = base_score * (0.7 + 0.3 * extraction_quality)
        
        return adjusted_score
```

## 7. まとめ

### 7.1 重要な認識
- 完全な文章抽出は現状の技術では困難
- 評価時には文章抽出の不完全さを考慮する必要がある
- 単語単位の差分検出は影響を受けにくい

### 7.2 推奨アプローチ
1. **短期**: 現状のヒューリスティックを改善し、評価基準を調整
2. **中期**: 追加情報の活用とパラメータの最適化
3. **長期**: 機械学習や外部ツールの導入検討

### 7.3 評価での留意点
- 文章抽出エラーと読み順序エラーを区別
- レイアウトの複雑さに応じた評価基準の適用
- 改善可能性の記録と分析