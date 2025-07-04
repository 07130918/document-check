# 読み順序一致度評価指標ドキュメント

## 1. 概要

PDF文書から抽出されたテキストの読み順序が、人間が認識する自然な読み順序とどの程度一致しているかを定量的に評価するための指標を定義します。

## 2. 評価指標の定義

### 2.1 順序相関係数（Spearman's Rank Correlation）
**定義**: 抽出されたテキストブロックの順序と正解順序の相関を測定
- **範囲**: -1 ≤ ρ ≤ 1
- **解釈**: 
  - ρ = 1: 完全に一致
  - ρ = 0: 無相関
  - ρ = -1: 完全に逆順

**計算式**:
```
ρ = 1 - (6 × Σd²) / (n × (n² - 1))
```
ここで、d = 順位の差、n = 要素数

### 2.2 ケンドールの順位相関係数（Kendall's Tau）
**定義**: ペアワイズ順序の一致・不一致を測定
- **範囲**: -1 ≤ τ ≤ 1
- **特徴**: 順序の逆転数に基づく頑健な指標

**計算式**:
```
τ = (C - D) / (n × (n - 1) / 2)
```
ここで、C = 一致ペア数、D = 不一致ペア数

### 2.3 編集距離ベース指標（Edit Distance Based Metrics）

#### 2.3.1 正規化編集距離（Normalized Edit Distance）
**定義**: 順序を修正するために必要な最小操作数
- **操作**: 挿入、削除、置換、転置
- **正規化**: 0 ≤ NED ≤ 1（0が完全一致）

**計算式**:
```
NED = ED(extracted, correct) / max(len(extracted), len(correct))
```

#### 2.3.2 順序保持率（Order Preservation Rate）
**定義**: 正しい相対順序が保持されているペアの割合
```
OPR = Σ(preserved_pairs) / Σ(total_pairs)
```

### 2.4 セグメントベース指標

#### 2.4.1 セグメント順序精度（Segment Order Accuracy）
**定義**: 文章・段落レベルでの順序正確性
- 粒度: 文、段落、セクション
- スコア: 各レベルでの正解率

#### 2.4.2 局所順序一致率（Local Order Consistency）
**定義**: 隣接要素間の順序関係の正確性
```
LOC = Σ(correct_adjacent_pairs) / Σ(total_adjacent_pairs)
```

### 2.5 重み付き指標

#### 2.5.1 重要度重み付き順序スコア（Importance-Weighted Order Score）
**定義**: テキストブロックの重要度を考慮した順序評価
- タイトル、見出し: 高重要度（w = 2.0）
- 本文: 標準重要度（w = 1.0）
- 注釈、脚注: 低重要度（w = 0.5）

**計算式**:
```
IWOS = Σ(wi × positioni) / Σ(wi)
```

## 3. 複合評価スコア

### 3.1 総合読み順序スコア（Composite Reading Order Score）
複数の指標を組み合わせた総合評価:
```
CROS = α × ρ + β × OPR + γ × LOC + δ × IWOS
```
ここで、α + β + γ + δ = 1（重み係数）

推奨重み配分:
- α = 0.3（全体的な順序相関）
- β = 0.3（順序保持率）
- γ = 0.2（局所的な一致）
- δ = 0.2（重要度考慮）

## 4. 評価基準

### 4.1 スコア解釈ガイドライン
| CROS範囲 | 評価 | 説明 |
|----------|------|------|
| 0.95-1.00 | 優秀 | 人間の読み順序とほぼ完全に一致 |
| 0.85-0.94 | 良好 | 実用上問題ないレベル |
| 0.70-0.84 | 可 | 基本的な順序は保持、一部改善必要 |
| 0.50-0.69 | 要改善 | 明確な順序の乱れあり |
| 0.00-0.49 | 不可 | 大幅な改善が必要 |

### 4.2 用途別閾値
- **契約書・法的文書**: CROS ≥ 0.95（厳格）
- **技術文書・マニュアル**: CROS ≥ 0.85（標準）
- **一般文書**: CROS ≥ 0.70（許容）

## 5. 実装例

### 5.1 Python実装サンプル
```python
import numpy as np
from scipy.stats import spearmanr, kendalltau
from typing import List, Tuple

class ReadingOrderEvaluator:
    """読み順序評価クラス"""
    
    def calculate_spearman_correlation(self, 
                                     extracted_order: List[int], 
                                     correct_order: List[int]) -> float:
        """スピアマンの順位相関係数を計算"""
        if len(extracted_order) != len(correct_order):
            raise ValueError("順序リストの長さが一致しません")
        
        correlation, _ = spearmanr(extracted_order, correct_order)
        return correlation
    
    def calculate_order_preservation_rate(self,
                                        extracted_order: List[int],
                                        correct_order: List[int]) -> float:
        """順序保持率を計算"""
        preserved_pairs = 0
        total_pairs = 0
        
        for i in range(len(extracted_order)):
            for j in range(i + 1, len(extracted_order)):
                total_pairs += 1
                # 相対順序が保持されているかチェック
                extracted_rel = extracted_order[i] < extracted_order[j]
                correct_rel = correct_order[i] < correct_order[j]
                if extracted_rel == correct_rel:
                    preserved_pairs += 1
        
        return preserved_pairs / total_pairs if total_pairs > 0 else 0
    
    def calculate_local_order_consistency(self,
                                        extracted_order: List[int],
                                        correct_order: List[int]) -> float:
        """局所順序一致率を計算"""
        correct_adjacent = 0
        total_adjacent = len(extracted_order) - 1
        
        for i in range(total_adjacent):
            # 隣接要素の順序が正しいかチェック
            if abs(extracted_order[i+1] - extracted_order[i]) == 1:
                if abs(correct_order[i+1] - correct_order[i]) == 1:
                    correct_adjacent += 1
        
        return correct_adjacent / total_adjacent if total_adjacent > 0 else 0
    
    def calculate_composite_score(self,
                                extracted_order: List[int],
                                correct_order: List[int],
                                weights: Tuple[float, float, float, float] = (0.3, 0.3, 0.2, 0.2)) -> dict:
        """総合読み順序スコアを計算"""
        spearman = self.calculate_spearman_correlation(extracted_order, correct_order)
        opr = self.calculate_order_preservation_rate(extracted_order, correct_order)
        loc = self.calculate_local_order_consistency(extracted_order, correct_order)
        
        # 重要度重み付きスコア（簡略版）
        iwos = 0.9  # 実際の実装では重要度を考慮
        
        # 総合スコア計算
        cros = (weights[0] * spearman + 
                weights[1] * opr + 
                weights[2] * loc + 
                weights[3] * iwos)
        
        return {
            'spearman_correlation': spearman,
            'order_preservation_rate': opr,
            'local_order_consistency': loc,
            'importance_weighted_score': iwos,
            'composite_score': cros,
            'evaluation': self._get_evaluation(cros)
        }
    
    def _get_evaluation(self, score: float) -> str:
        """スコアに基づく評価を返す"""
        if score >= 0.95:
            return "優秀"
        elif score >= 0.85:
            return "良好"
        elif score >= 0.70:
            return "可"
        elif score >= 0.50:
            return "要改善"
        else:
            return "不可"
```

## 6. 評価実施ガイドライン

### 6.1 評価データ準備
1. **正解データ作成**: 人間が判断した正しい読み順序
2. **アノテーション**: 各テキストブロックに順序番号付与
3. **重要度ラベリング**: タイトル、本文、注釈等の分類

### 6.2 評価プロセス
1. PDF文書からテキストブロック抽出
2. 抽出されたブロックの順序記録
3. 正解順序との比較
4. 各指標の計算
5. 総合スコアの算出
6. 結果の解釈と改善点の特定

### 6.3 改善指針
- **スピアマン相関が低い場合**: 全体的な順序アルゴリズムの見直し
- **OPRが低い場合**: ペアワイズ順序判定ロジックの改善
- **LOCが低い場合**: 隣接要素の位置関係判定の精緻化
- **IWOSが低い場合**: 重要要素の識別・優先順位付けの改善

## 7. ベンチマーク目標

### 7.1 短期目標（1ヶ月）
- CROS ≥ 0.70（基本的な順序保持）
- 局所順序一致率 ≥ 0.80

### 7.2 中期目標（3ヶ月）
- CROS ≥ 0.85（実用レベル）
- スピアマン相関 ≥ 0.90

### 7.3 長期目標（6ヶ月）
- CROS ≥ 0.95（高精度）
- 全指標で0.90以上

## 8. 参考文献

1. Spearman, C. (1904). "The proof and measurement of association between two things"
2. Kendall, M. (1938). "A new measure of rank correlation"
3. PDF文書解析に関する最新研究論文
4. 文書レイアウト解析のベストプラクティス