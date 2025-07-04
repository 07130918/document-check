# ベースライン構築とA/Bテスト計画

## 1. ベースライン構築戦略

### 1.1 prj-meiji-document-checkベースライン実装

#### 参考にすべき核心アルゴリズム
1. **テキスト正規化エンジン** (`utils.py`)
   - 128種類の文字変換ルール
   - 全角英数字→半角変換
   - 特殊記号統一処理

2. **並列テキストマッチング** (`PdfDiffLogicDomainService`)
   - ThreadPoolExecutorによる高速処理
   - 事前フィルタリング + 動的閾値設定
   - フォールバック機能付きの堅牢設計

3. **SequenceMatcher差分検出**
   - 文字ベース類似度計算
   - レーベンシュタイン距離による部分一致判定
   - 階層的マッチング（完全一致→部分一致）

#### 移植対象コンポーネント
```python
# ベースライン実装クラス
class SequenceMatcherDiffDetector:
    """prj-meiji-document-checkベースの差分検出器"""
    
    def __init__(self, text_normalizer: TextNormalizer):
        self.text_normalizer = text_normalizer
        self.threshold_calculator = DynamicThresholdCalculator()
    
    def detect_differences(self, doc1: str, doc2: str) -> List[DiffResult]:
        # 1. テキスト正規化
        normalized_doc1 = self.text_normalizer.normalize(doc1)
        normalized_doc2 = self.text_normalizer.normalize(doc2)
        
        # 2. SequenceMatcher類似度計算
        similarity = SequenceMatcher(None, normalized_doc1, normalized_doc2).ratio()
        
        # 3. 動的閾値による判定
        threshold = self.threshold_calculator.calculate(len(doc1), len(doc2))
        
        return self._classify_changes(similarity, threshold)
```

### 1.2 ベースライン性能測定

#### 測定項目
- **精度指標**: 真陽性率、偽陽性率、偽陰性率
- **性能指標**: 処理時間、メモリ使用量
- **安定性**: 複数回実行での結果一貫性

#### ベンチマークデータセット
1. **簡単レベル**: 明確な文字変更（10ケース）
2. **中程度レベル**: 数値・日付変更（10ケース）  
3. **困難レベル**: 微細な変更・レイアウト変更（10ケース）

## 2. A/Bテスト設計

### 2.1 比較対象アルゴリズム

#### A群: ベースライン（prj-meiji-document-checkベース）
- SequenceMatcher + レーベンシュタイン距離
- 文字ベース類似度計算
- 動的閾値設定

#### B群: 改良アルゴリズム（新規開発）
- LLM中心型読み順序推定
- 単語ベース差分検出
- アンサンブル統合システム

### 2.2 評価フレームワーク

#### ComparisonEvaluatorクラス設計
```python
class ComparisonEvaluator:
    """A/Bテスト用評価フレームワーク"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.statistical_analyzer = StatisticalAnalyzer()
    
    def run_ab_test(self, test_cases: List[TestCase]) -> ABTestResult:
        """A/Bテストの実行"""
        baseline_results = []
        improved_results = []
        
        for test_case in test_cases:
            # A群（ベースライン）
            baseline_result = self.baseline_detector.detect(test_case.pdf1, test_case.pdf2)
            baseline_results.append(self._evaluate_result(baseline_result, test_case.ground_truth))
            
            # B群（改良版）
            improved_result = self.improved_detector.detect(test_case.pdf1, test_case.pdf2)
            improved_results.append(self._evaluate_result(improved_result, test_case.ground_truth))
        
        return self._compare_results(baseline_results, improved_results)
```

### 2.3 統計的有意性検定

#### 検定手法
- **t検定**: 精度指標の平均値比較
- **Wilcoxon順位和検定**: ノンパラメトリック比較
- **McNemar検定**: 分類結果の有意差検定

#### 有意水準
- α = 0.05（5%有意水準）
- 効果量（Cohen's d）≥ 0.5で実用的改善と判定

## 3. 実装タスク詳細

### Phase 0: ベースライン構築（1週間）

#### Task 0.1: prj-meiji-document-checkベースライン実装
- [ ] `PdfDiffLogicDomainService`のコアロジック移植
- [ ] テキスト正規化エンジンの移植
- [ ] 並列テキストマッチングの移植
- [ ] `SequenceMatcherDiffDetector`クラス作成
- [ ] 文字ベース類似度計算
- [ ] 動的閾値設定機能

#### Task 0.2: ベースライン性能測定
- [ ] 正解データセットでの精度評価
- [ ] 処理時間・メモリ使用量測定
- [ ] ベースラインスコアの記録

#### Task 0.3: A/Bテスト基盤構築
- [ ] `ComparisonEvaluator`クラス作成
- [ ] 混同行列ベース評価
- [ ] 結果ログ・レポート機能
- [ ] テストデータセット準備
- [ ] 正解データセットの整備
- [ ] 複数困難度レベルのPDF準備
- [ ] アノテーションデータの作成

#### Task 0.4: 性能モニタリング
- [ ] リアルタイム性能計測
- [ ] メトリクス収集システム
- [ ] 結果比較ダッシュボード

### Phase 1-4: 改良アルゴリズム開発（3週間）

各フェーズでベースラインとの比較を実行

#### A/Bテスト実行ポイント
- **Phase 1終了時**: 基盤構築後の初期比較
- **Phase 2終了時**: LLM・単語ベース実装後の比較
- **Phase 3終了時**: 最適化後の比較
- **Phase 4終了時**: 最終統合システムの比較

## 4. 成功基準とKPI

### 4.1 必須改善指標
- **真陽性率**: ベースライン比+10%以上
- **処理時間**: ベースライン比-30%以上短縮
- **偽陽性率**: ベースライン比-20%以上削減

### 4.2 統計的有意性
- **p値**: < 0.05で有意差ありと判定
- **効果量**: Cohen's d ≥ 0.5で実用的改善
- **信頼区間**: 95%信頼区間での改善確認

### 4.3 A/Bテスト完了基準
- [ ] 30ケース以上でのテスト完了
- [ ] 3つの困難度レベルすべてでの改善確認
- [ ] 統計的有意性の確認
- [ ] 実用的効果量の達成

## 5. リスク管理

### 5.1 技術的リスク
- **ベースライン性能**: 既存実装が想定より高性能な場合
- **LLM API制約**: 外部API依存による不安定性
- **統計的検出力**: サンプルサイズ不足による検出力低下

### 5.2 対応策
- **フォールバック戦略**: LLM不使用モードの準備
- **サンプルサイズ計算**: 事前の検出力分析
- **段階的改善**: 小さな改善の積み重ね

## 6. 期待される成果

### 6.1 定量的成果
- **検出率**: 90% → 100%（10%改善）
- **処理時間**: 3.6分 → 2.0分（44%短縮）
- **誤検出率**: 3.2% → 2.0%（38%削減）

### 6.2 定性的成果
- **技術的革新**: LLM活用による読み順序推定の実現
- **実用性向上**: 業務適用可能な精度・速度の達成
- **汎用性確保**: 他文書タイプへの適用可能性

このベースライン構築とA/Bテスト計画により、既存技術を基盤とした確実な改善を実現し、新規アルゴリズムの有効性を科学的に検証できます。