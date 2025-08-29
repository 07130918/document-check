# 差分検知アルゴリズム概要

プロジェクトには6つの主要な差分検知アルゴリズムが実装されています：

## ベースライン実装
1. **SimpleDiffDetector** - SequenceMatcherベースの基本実装
2. **LayoutAwareDiffDetector** - レイアウト変更も検出
3. **SentenceAwareDiffDetector** - 文章単位→単語単位の2段階検出

## LLM統合版（v1-v5）
4. **v1-v2: EnhancedDiffDetector** - Azure OCR統合、読み順序改善
5. **v3: ContentBasedDiffDetector** - テキスト内容重視、移動検出対応
6. **v4: WordLevelDiffDetector** - 単語単位の精密検出
7. **v5: BlockDiffDetector** - 構造ブロック単位（パラグラフ、表、画像）

## 主要な特徴
- 差分タイプ: ADDITION, DELETION, MODIFICATION, MOVEMENT, LAYOUT_CHANGE
- LLM活用: 読み順序推定、視覚的フロー検出
- Azure統合: OCR、複雑レイアウト解析

詳細は `/home/dev/prj-ms-document-check/docs/diff_detection_algorithms.md` を参照