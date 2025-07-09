# Document Diff System - BBox Based Baseline

## 概要

このシステムは、PDF/Word/PowerPoint文書の差分を検出し、視覚的にハイライト表示するベースラインシステムです。

### 主な特徴

- **BBoxベースの処理**: 単語単位のbounding box情報を使用
- **文章単位の読み順序推定**: 自然な読み順序で文章を並び替え
- **単語単位の差分検出**: 細かい変更も見逃さない
- **視覚的な出力**: 読み順序と差分をハイライトで表示

## システム構成

```
document_diff_system/
├── models/          # データモデル定義
│   └── bbox_models.py
├── services/        # 主要サービス
│   ├── document_analysis_engine.py  # 文書解析
│   ├── reading_order_estimator.py   # 読み順序推定
│   ├── bbox_diff_detector.py        # 差分検出
│   └── output_generator.py          # 出力生成
├── handlers/        # ファイル形式別ハンドラ
│   ├── pdf_handler.py
│   ├── docx_handler.py
│   └── pptx_handler.py
└── core/           # 統合パイプライン
    └── document_comparison_pipeline.py
```

## インストール

```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt
```

## 使用方法

### 基本的な使用例

```python
from apps.document_diff_system.core import DocumentComparisonPipeline

# パイプラインの初期化
pipeline = DocumentComparisonPipeline()

# ファイルの比較
summary = pipeline.compare_files(
    'document1.pdf',
    'document2.pdf',
    output_dir='output'
)

print(summary)
```

### 詳細な使用例

```python
from apps.document_diff_system.services import (
    DocumentAnalysisEngine,
    ReadingOrderEstimator,
    BBoxBasedDiffDetector,
    OutputGenerator
)

# 1. 文書解析
engine = DocumentAnalysisEngine()
doc1_bbox = engine.extract_from_file('doc1.pdf')
doc2_bbox = engine.extract_from_file('doc2.pdf')

# 2. 読み順序推定
estimator = ReadingOrderEstimator()
doc1_ordered = estimator.estimate_reading_order(doc1_bbox)
doc2_ordered = estimator.estimate_reading_order(doc2_bbox)

# 3. 差分検出
detector = BBoxBasedDiffDetector()
differences = detector.detect_differences(doc1_ordered, doc2_ordered)

# 4. 出力生成
generator = OutputGenerator()
with open('doc1.pdf', 'rb') as f:
    file1_bytes = f.read()
with open('doc2.pdf', 'rb') as f:
    file2_bytes = f.read()

highlighted1, highlighted2 = generator.generate_comparison_report(
    file1_bytes, file2_bytes, 'pdf', differences
)

# ファイルとして保存
with open('doc1_highlighted.pdf', 'wb') as f:
    f.write(highlighted1)
with open('doc2_highlighted.pdf', 'wb') as f:
    f.write(highlighted2)
```

## テストの実行

```bash
# ベースラインテストの実行
python apps/document_diff_system/test_baseline.py
```

## ハイライトの意味

### 読み順序（文書1のみ）
- **青色の番号**: 文章の読み順序を示す

### 差分（両文書）
- **緑色**: 追加された内容
- **赤色**: 削除された内容
- **黄色**: 修正された内容

## 制限事項

1. **Word/PowerPoint**: 正確なbbox情報が取得できないため、擬似的な座標を生成
2. **文章抽出**: 単語から文章へのグルーピングが不完全な場合がある
3. **複雑なレイアウト**: 表やカラムレイアウトでは精度が低下する可能性

## 今後の改善点

1. より高度な文章境界検出アルゴリズム
2. 機械学習を使用した読み順序推定
3. レイアウト解析の高度化
4. パフォーマンスの最適化