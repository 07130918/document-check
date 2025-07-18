# LLM Diff Test v1, v2, v3 完全比較

## 概要

本文書では、LLM Diff Testの3つのバージョン（v1, v2, v3）の違いを包括的に比較し、各バージョンの特徴と適用場面を明確にします。

## バージョン概要

### v1: 基本実装
- Azure Document Intelligence中心
- 基本的な差分検出
- 変更検出が機能しない

### v2: 高速化と精度向上
- PyMuPDF中心（ローカル処理）
- 位置ベースの高度な差分検出
- 前処理による効率化

### v3: 内容ベース検出
- Azure Document Intelligence（階層構造）
- 位置に依存しない差分検出
- テキスト移動の認識

## 主要指標の比較

### 検出結果比較（4ページ処理時）

| 指標 | v1 | v2 | v3 |
|------|----|----|-----|
| **削除** | 122件 | 130件 | 57件 |
| **追加** | 113件 | 81件 | 10件 |
| **変更** | 0件 | 16件 | 53件 |
| **移動** | - | - | 26件 |
| **合計** | 235件 | 227件 | 146件 |
| **偽陽性率** | 高 | 中 | 低 |

### パフォーマンス比較

| 指標 | v1 | v2 | v3 |
|------|----|----|-----|
| **処理時間** | 40-50秒 | 10-15秒 | 40-50秒 |
| **メモリ使用** | 高 | 低 | 中 |
| **APIコスト** | 高 | なし | 中（バッチ） |
| **処理要素数** | 10,711 | 8,248 | 374 |

## アーキテクチャ比較

### v1: シンプルな構造
```
Azure Document Intelligence
    ↓
DocumentAnalyzer
    ↓
DiffDetector（基本）
    ↓
OutputHandler
```

### v2: 効率的な処理
```
PyMuPDF
    ↓
TextPreprocessor（前処理）
    ↓
ReadingOrderEstimator
    ↓
EnhancedDiffDetector（位置ベース）
    ↓
OutputHandler（拡張）
```

### v3: 階層的な処理
```
Azure Document Intelligence
    ↓
階層構造抽出（段落・行・単語）
    ↓
TextPreprocessor
    ↓
ContentBasedDiffDetector（内容ベース）
    ↓
OutputHandler（side-by-side対応）
```

## 技術的特徴の比較

### テキスト抽出方法

| バージョン | 抽出方法 | 特徴 | 制限 |
|-----------|---------|------|------|
| v1 | Azure OCR（文字単位） | 高精度 | ノイズ多、コスト高 |
| v2 | PyMuPDF（単語単位） | 高速、無料 | スキャンPDF非対応 |
| v3 | Azure OCR（階層構造） | 構造保持 | 2ページ制限対応必要 |

### 差分検出アルゴリズム

| バージョン | アルゴリズム | 重み配分 | 特徴 |
|-----------|------------|---------|------|
| v1 | テキストマッチング | 位置無視 | 変更検出不可 |
| v2 | 位置ベース | 位置100%、テキスト併用 | 位置変更に弱い |
| v3 | 内容ベース | 位置5%、テキスト95% | 移動を正しく認識 |

### 前処理機能

| 機能 | v1 | v2 | v3 |
|------|----|----|-----|
| Unicode正規化 | ✗ | ✓ | ✓ |
| 全角半角変換 | ✗ | ✓ | ✓ |
| ノイズ除去 | ✗ | ✓ | ✓ |
| 日本語グループ化 | △ | ✗ | ✓ |
| 要素数削減率 | 0% | 23% | 76.7% |

## 新機能の比較

### v1の機能
- 基本的な差分検出
- ハイライトPDF生成
- LLM解析（基本）

### v2の新機能
- ✨ 前処理システム
- ✨ 変更検出の実現
- ✨ 詳細な変更分析
- ✨ 座標ベース読み取り順序

### v3の新機能
- ✨ 移動検出
- ✨ 内容ベース差分検出
- ✨ side-by-side比較PDF
- ✨ Azure Free Tier対応（バッチ処理）
- ✨ ページ制限機能

## 出力形式の比較

### PDF出力

| ファイル | v1 | v2 | v3 | 説明 |
|---------|----|----|-----|------|
| compared.pdf | ✓ | ✓ | ✓ | 差分ハイライト |
| reading_order.pdf | ✓ | ✓ | ✓ | 読み取り順序 |
| original_order.pdf | ✓ | ✓ | ✗ | 元の順序 |
| side_by_side.pdf | ✗ | ✗ | ✓ | 並列比較 |

### レポート出力

| レポート | v1 | v2 | v3 |
|----------|----|----|-----|
| execution_report.json | ✓ | ✓ | ✓ |
| statistics.json | △ | ✓ | ✓ |
| modification_analysis.json | ✗ | ✓ | ✗ |
| movement_analysis.json | ✗ | ✗ | ✓ |

## 類似度計算の進化

### v1: 類似度計算なし
- 完全一致のみ
- 変更検出不可

### v2: 基本的な類似度
```python
# Levenshtein距離ベース
similarity = 1 - (edit_distance / max_length)
```

### v3: 高度な日本語対応
```python
# 1. 包含関係チェック
# 2. 数字パターン認識
# 3. 共通キーワードボーナス
# 4. 文字n-gram類似度
```

## 使用推奨場面

### v1を選ぶべき場合
- ✓ シンプルな差分確認のみ必要
- ✓ 変更検出が不要
- ✓ Azure OCRの最高精度が必要
- ✗ コストが問題でない

### v2を選ぶべき場合
- ✓ 高速処理が最優先
- ✓ コスト削減が重要
- ✓ 大量のPDF処理
- ✗ テキストの位置が安定している

### v3を選ぶべき場合
- ✓ レイアウト変更が多い文書
- ✓ テキストの移動を正確に把握したい
- ✓ 偽陽性を最小化したい
- ✓ Azure Free Tierを使用
- ✗ 処理速度は問わない

## 実装の違い

### v1の実装
```python
# シンプルなAPI呼び出し
analyzer = DocumentAnalyzer()
result = analyzer.analyze_documents(file1, file2)
```

### v2の実装
```python
# ローカル処理 + 前処理
pdf_processor = PDFProcessor()
bbox_list = pdf_processor.extract_bbox_data(pdf_bytes, preprocess=True)
diff_detector = EnhancedDiffDetector()
```

### v3の実装
```python
# 階層構造 + 内容ベース
azure_service = AzureDocumentServiceEnhanced()
hierarchy = azure_service.extract_layout_with_hierarchy_batch(pdf_bytes)
diff_detector = ContentBasedDiffDetector(position_weight=0.05)
```

## コスト比較

| 項目 | v1 | v2 | v3 |
|------|----|----|-----|
| Azure API | 高（全ページ） | なし | 中（バッチ処理） |
| 処理時間 | 長い | 短い | 長い |
| 必要リソース | API依存 | ローカルのみ | 混合 |

## 移行パス

### v1 → v2
1. Azure API依存を解消
2. PyMuPDFのインストール
3. 前処理システムの活用

### v2 → v3
1. Azure API設定の再有効化
2. 差分検出器の変更
3. 移動検出結果の活用

### v1 → v3
1. 階層構造対応のAzureサービス使用
2. 内容ベース検出への移行
3. side-by-side PDFの活用

## 総合評価

### 精度
**v3 > v2 > v1**
- v3: 偽陽性最小、移動認識
- v2: 変更検出可能
- v1: 基本機能のみ

### 速度
**v2 > v1 ≈ v3**
- v2: 10-15秒（最速）
- v1, v3: 40-50秒

### コスト効率
**v2 > v3 > v1**
- v2: 無料（ローカル処理）
- v3: 中（バッチ処理）
- v1: 高（全ページAPI）

### 機能性
**v3 > v2 > v1**
- v3: 移動検出、side-by-side
- v2: 詳細分析
- v1: 基本機能

## まとめ

各バージョンには明確な強みと適用場面があります：

- **v1**: シンプルで確実な基本実装
- **v2**: 高速・低コストな実用版
- **v3**: 高精度・高機能な先進版

プロジェクトの要件に応じて、適切なバージョンを選択することが重要です。将来的には、v3の精度とv2の速度を組み合わせたハイブリッド版の開発も検討されています。