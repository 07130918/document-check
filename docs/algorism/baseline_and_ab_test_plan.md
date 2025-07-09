# ベースライン構築と評価計画

## 1. ベースライン構築戦略

### 1.1 現状ベースラインの活用

#### 現在実装済みの機能
1. **読み順序ベースライン** (`baseline_evaluation.py`)
   - 複数ページPDFでの順序推定
   - アノテーションCSVを使用した評価
   - 17種類のテストケース

2. **BBoxベース処理** (`test_sequential_baseline.py`)
   - PyMuPDFを使用したbbox抽出
   - 座標ベースのテキスト結合
   - ページ単位での処理

3. **評価メトリクス**
   - TP (True Positive)
   - FP (False Positive)
   - FN (False Negative)
   - Precision/Recall計算

#### 新システムでの活用方法
```python
# BBoxベース差分検出ベースライン
class BBoxBaselineDiffDetector:
    """bbox_text_dataを使用したベースライン差分検出器"""
    
    def __init__(self):
        self.reading_order_estimator = ReadingOrderEstimator()
    
    def detect_differences(self, 
                         doc1_bbox_list: List[BBoxTextData], 
                         doc2_bbox_list: List[BBoxTextData]) -> List[DiffResult]:
        # 1. 読み順序推定
        doc1_ordered = self.reading_order_estimator.estimate_reading_order(doc1_bbox_list)
        doc2_ordered = self.reading_order_estimator.estimate_reading_order(doc2_bbox_list)
        
        # 2. テキスト結合
        text1 = " ".join([bbox['text'] for bbox in doc1_ordered])
        text2 = " ".join([bbox['text'] for bbox in doc2_ordered])
        
        # 3. 差分検出（単語単位）
        return self._detect_word_differences(doc1_ordered, doc2_ordered)
```

### 1.2 人力評価による性能測定

#### 評価方法
- **出力ファイル**: ハイライト付きPDF/DOCX/PPTX
- **評価項目**:
  1. 読み順序の正確性（番号付き青ハイライト）
  2. 差分検出の正確性（色分けハイライト）
  3. 誤検出・見逃しの確認

#### 評価用テストケース
1. **簡単レベル**: 明確な文字変更（5ケース）
2. **中程度レベル**: 数値・日付変更（5ケース）  
3. **困難レベル**: 複雑レイアウト・表内変更（5ケース）

## 2. 評価計画

### 2.1 評価対象システム

#### ベースラインシステム
- 座標ベース読み順序推定
- 単語単位差分検出
- ハイライト付きファイル出力

#### 改善後システム（将来的な拡張）
- AIを活用した読み順序推定
- コンテキスト考慮差分検出
- マルチフォーマット対応強化

### 2.2 人力評価フレームワーク

#### ManualEvaluationFramework設計
```python
class ManualEvaluationFramework:
    """人力評価用フレームワーク"""
    
    def __init__(self):
        self.evaluation_sheet_generator = EvaluationSheetGenerator()
        self.result_aggregator = ResultAggregator()
    
    def prepare_evaluation(self, test_cases: List[TestCase]) -> EvaluationPackage:
        """評価用パッケージの準備"""
        evaluation_package = []
        
        for test_case in test_cases:
            # ハイライト付きファイル生成
            highlighted_files = self.system.process(test_case.file1, test_case.file2)
            
            # 評価シート生成
            evaluation_sheet = self.evaluation_sheet_generator.create(
                test_case, highlighted_files
            )
            
            evaluation_package.append(evaluation_sheet)
        
        return evaluation_package
```

### 2.3 評価基準

#### 評価項目
1. **読み順序の正確性**
   - 正しい順序: 5点
   - 部分的に正しい: 3点
   - 不正確: 1点

2. **差分検出の正確性**
   - 完全検出: 5点
   - 部分検出: 3点
   - 見逃しあり: 1点

3. **誤検出率**
   - 誤検出なし: 5点
   - 少数誤検出: 3点
   - 多数誤検出: 1点

## 3. 実装タスク詳細

### Phase 0: ベースライン構築（1週間）

#### Task 0.1: BBoxベースベースライン実装
- [ ] `DocumentAnalysisEngine`の実装
- [ ] PDF/Word/Pptx対応のbbox抽出機能
- [ ] `ReadingOrderEstimator`の実装
- [ ] `BBoxBasedDiffDetector`の実装
- [ ] `OutputGenerator`の実装
- [ ] ハイライト付きファイル出力機能

#### Task 0.2: 評価準備
- [ ] 評価用テストケースの作成
- [ ] 評価シートテンプレートの作成
- [ ] 評価プロセスの文書化

#### Task 0.3: 人力評価基盤構築
- [ ] `ManualEvaluationFramework`の実装
- [ ] `EvaluationSheetGenerator`の実装
- [ ] `ResultAggregator`の実装
- [ ] テストデータセット準備
- [ ] 簡単・中程度・困難なテストケース作成
- [ ] PDF/Word/Pptx各形式のテストデータ
- [ ] 評価マニュアルの作成

#### Task 0.4: 性能モニタリング
- [ ] リアルタイム性能計測
- [ ] メトリクス収集システム
- [ ] 結果比較ダッシュボード

### Phase 1-4: システム開発（3週間）

各フェーズで人力評価を実行

#### 評価実行ポイント
- **Phase 1終了時**: 基本機能実装後の評価
- **Phase 2終了時**: 高度化機能実装後の評価
- **Phase 3終了時**: 最適化後の評価
- **Phase 4終了時**: 最終統合システムの評価

## 4. 成功基準とKPI

### 4.1 必須達成指標
- **検出率**: 99-100%（見逃しゼロ）
- **処理時間**: 5分以内（ファイルサイズに関わらず）
- **誤検出率**: 10%以下

### 4.2 評価基準
- **読み順序正確性**: 平均評点 4.0以上/5.0
- **差分検出正確性**: 平均評点 4.5以上/5.0
- **誤検出率**: 平均評点 4.0以上/5.0

### 4.3 評価完了基準
- [ ] 15ケース以上での評価完了
- [ ] 3つの困難度レベルすべてでの評価
- [ ] 全ファイル形式（PDF/Word/Pptx）での検証
- [ ] 評価結果の集計・分析

## 5. リスク管理

### 5.1 技術的リスク
- **ファイル形式差異**: Word/Pptxでのbbox情報取得の困難さ
- **複雑レイアウト**: 表やカラム構造での読み順序推定難度
- **評価者依存**: 人力評価のバラツキ

### 5.2 対応策
- **フォールバック処理**: ファイル形式別の代替処理
- **評価ガイドライン**: 明確な評価基準の提供
- **複数評価者**: 重要なケースでのクロスチェック

## 6. 期待される成果

### 6.1 定量的成果
- **検出率**: 99-100%の達成
- **処理時間**: 5分以内の実現
- **誤検出率**: 10%以下の維持

### 6.2 定性的成果
- **可視化出力**: ハイライトによる直感的な差分確認
- **マルチフォーマット**: PDF/Word/Pptxの統一的処理
- **人力評価基盤**: 継続的改善のための評価体制

このベースライン構築と評価計画により、bbox_text_dataを中心とした文書差分検出システムの有効性を人力評価で検証し、実用的なシステムを実現します。