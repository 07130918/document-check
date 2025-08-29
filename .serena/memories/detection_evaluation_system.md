# 検出ステップ評価システム

## 概要
PDFから抽出された要素の検出精度を評価するシステム。4つの主要課題に対する自動評価を実装。

## 評価課題
1. **完全性評価**: 全文言が検出されているか（IoUベース）
2. **分割単位評価**: 適切な単位で分割されているか
3. **ページまたぎ評価**: ページ間の継続文章を1単位として検出
4. **粒度評価**: 文・節・単語レベルの一貫性

## 使用プロパティ
### Azure Document Intelligence
- pages[].lines[].content/polygon
- pages[].words[].content/polygon/confidence
- pages[].paragraphs[].content/boundingRegions

### 検出システム出力（v5）
- block_id, text, page, polygon/bbox
- reading_order, confidence, block_type

## アノテーション形式
- completeness.json: 必須検出要素と位置
- segmentation.json: 有効/無効な分割パターン
- cross_page.json: ページまたぎ文章
- granularity.json: 粒度レベルの例

## 評価メトリクス
- IoU（Intersection over Union）
- Precision/Recall/F1スコア
- 粒度一貫性スコア

## 実装優先順位
1. 基本評価（完全性）
2. 構造評価（分割・粒度）
3. 高度評価（ページまたぎ・統合）

詳細: /docs/detection_evaluation_system_design.md