# エージェント実行作業設計: 検出評価ワークフロー

## 概要

PDF文書の文言検出と評価を自動化するエージェントのワークフロー設計です。2024年と2025年のサンプルファイルを用いて、検出精度の確認とデバッグを行います。

## 前提知識

### ビジネスロジック
- 保険関連文書の文言変更検出
- ページまたぎ文章の継続性検証
- 文書構造の階層解析（見出し、本文、注釈など）

### 処理フローの各ステップ
1. **PDF解析**: Azure Document Intelligence APIによるOCR処理
2. **ブロック抽出**: LLMベースのセマンティック単位検出
3. **読み順推定**: 視覚的レイアウト解析による順序付け
4. **差分検出**: 対応文章の比較とハイライト生成

## ワークフロー仕様

### Phase 1: 文言チェック対象の決定
**目標**: Geminiの画像検知機能を用いた文言確認
**入力ファイル**: 
- `trimmed_サンプル②2024.pdf`
- `trimmed_サンプル②2025.pdf`

**実行手順**:
1. 対象PDFファイルの画像化
2. Gemini Vision APIによる文言抽出
3. チェック対象文言の選定（評価CSVの「不検出」「誤検出」項目優先）

```bash
# コマンド例
python analyze_detection_logic.py --input_files trimmed_サンプル②2024.pdf,trimmed_サンプル②2025.pdf --mode text_extraction
```

### Phase 2: 現在の検出単位とメタデータ確認
**目標**: 両年度の検出結果をメモリに保存

**実行手順**:
1. 2024年ファイルの処理
   ```bash
   python apps/llm_docs_diff_v5/test_llm_diff_v5.py --input1 trimmed_サンプル②2024.pdf --mode single_analysis
   ```

2. 2025年ファイルの処理
   ```bash
   python apps/llm_docs_diff_v5/test_llm_diff_v5.py --input1 trimmed_サンプル②2025.pdf --mode single_analysis
   ```

3. 検出メタデータの抽出と保存
   - `block_id`, `text`, `page`, `polygon/bbox`
   - `reading_order`, `confidence`, `block_type`

### Phase 3: 該当箇所識別コードの分析
**目標**: デバッグ可能なインスタンス・プロパティの特定

**確認項目**:
- Azure Document Intelligence出力
  - `pages[].lines[].content/polygon`
  - `pages[].words[].content/polygon/confidence`
  - `pages[].paragraphs[].content/boundingRegions`
  
- v5システム出力
  - ブロック抽出ロジック (`apps/llm_docs_diff_v5/services/block_extractor.py`)
  - 読み順推定ロジック (`apps/llm_docs_diff_v5/core/block_reading_order.py`)

### Phase 4: 該当箇所識別の検証
**目標**: 正確に識別できているかの確認とデバッグ

**評価観点**:
1. **完全性評価**: 評価CSV記載文言の検出有無
2. **正確性評価**: 誤検出項目の除外確認
3. **分割評価**: 適切な単位での区切り確認

## デバッグ戦略

### 2025年ファイルの主要課題
| ID | ページ | タイプ | 文言 | 位置 | デバッグポイント |
|----|--------|--------|------|------|------------------|
| 2 | 3 | 不検出 | 右側のたくさんページ番号があるもの | - | ページ番号認識ロジック |
| 3 | 3 | 誤検出 | Q&A | 右下 | 見出し識別精度 |
| 7 | 4 | 不検出 | 上のほうにある細々した対象の数々 | - | 小テキスト検出閾値 |
| 9 | 5 | 不検出 | 表の中身を全て | - | 表構造解析 |
| 13 | 14 | 不検出 | 事故発生の日から180日以内の... | - | 長文継続検出 |

### 2024年ファイルの主要課題
| ページ | タイプ | 文言 | 位置 | デバッグポイント |
|--------|--------|------|------|------------------|
| 4 | 不検出 | CT・MRI検査一時金保障特約の表内容 | 真ん中 | 表内テキスト抽出 |
| 6 | 不検出 | 介護費用・ベットの親介護コース... | 下 | レイアウト境界検出 |

## 実装プランtemplate

### デバッグスクリプトの構造
```python
class DetectionEvaluationAgent:
    def __init__(self, evaluation_csv_path: str):
        self.evaluation_csv = pd.read_csv(evaluation_csv_path)
        self.v5_service = LLMDiffV5Service()
        
    def phase1_text_extraction(self, pdf_paths: List[str]) -> Dict:
        """Gemini画像検知による文言抽出"""
        
    def phase2_detection_analysis(self, pdf_path: str) -> Dict:
        """現在の検出単位とメタデータ確認"""
        
    def phase3_code_analysis(self) -> Dict:
        """識別コードの分析とデバッグ情報収集"""
        
    def phase4_verification(self, detection_results: Dict) -> Dict:
        """該当箇所識別の検証とレポート生成"""
```

### 出力形式
- **デバッグログ**: `/output/agent_debug_{timestamp}/`
  - `phase1_text_extraction.json`
  - `phase2_detection_metadata.json`  
  - `phase3_code_analysis.json`
  - `phase4_verification_report.json`

- **サマリレポート**: `agents_evaluation_summary.md`

## 実行コマンド

```bash
# エージェント実行
python agents/run_check_eval_agent.py \
    --pdf_2024 "output/llm_diff_test_v3/sougou/PDFs/trimmed_サンプル②2024 _reading_order.pdf" \
    --pdf_2025 "output/llm_diff_test_v3/sougou/PDFs/trimmed_サンプル②2025_reading_order.pdf" \
    --evaluation_csv "evaluator/sample_annotations_complete/completeness_annotations.csv" \
    --output_dir "output/check_eval_agent_{timestamp}"
```

## 成功基準

1. **検出率**: 不検出項目の85%以上を検出
2. **精度**: 誤検出項目の70%以上を除外
3. **デバッグ情報**: 各問題の根本原因を特定
4. **改善提案**: 具体的なコード修正案の提示

## 必要なコンテキストファイル

- `docs/detection_evaluation_system_design.md`
- `apps/llm_docs_diff_v5/README.md`
- `evaluator/README.md`
- 該当する評価CSV: `evaluator/sample_annotations_complete/*.csv`

## 確認事項

1. Gemini Vision APIのアクセス権限とAPIキー
2. 評価CSVの最新版が利用可能か
3. デバッグ対象の具体的な文言リストの最終確認
4. 出力ディレクトリの権限設定