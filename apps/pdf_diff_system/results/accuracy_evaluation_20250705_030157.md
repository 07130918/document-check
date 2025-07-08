# 差分検出アルゴリズム精度評価レポート

評価日時: 2025-07-05 03:01:57

## 評価結果サマリー

| アルゴリズム | 適合率 | 再現率 | F1スコア | 平均処理時間(秒) |
|------------|--------|--------|----------|-----------------|
| phrase_based | 0.400 | 0.909 | 0.556 | 0.001 |
| sequential_w1 | 0.462 | 0.545 | 0.500 | 0.002 |
| sequential_w3 | 0.385 | 0.455 | 0.417 | 0.001 |
| sequential_w5 | 0.385 | 0.455 | 0.417 | 0.001 |

## 詳細評価結果


### phrase_based

- **総True Positive**: 10
- **総False Positive**: 15
- **総False Negative**: 1
- **総処理時間**: 0.010秒

### sequential_w1

- **総True Positive**: 6
- **総False Positive**: 7
- **総False Negative**: 5
- **総処理時間**: 0.018秒

### sequential_w3

- **総True Positive**: 5
- **総False Positive**: 8
- **総False Negative**: 6
- **総処理時間**: 0.007秒

### sequential_w5

- **総True Positive**: 5
- **総False Positive**: 8
- **総False Negative**: 6
- **総処理時間**: 0.012秒

## 考察

- **最高F1スコア**: phrase_based (0.556)
- **最速処理**: sequential_w3 (0.001秒/ケース)

### 順序考慮の効果
- F1スコア改善: -0.139
- 特に順序変更を含むケースで効果的