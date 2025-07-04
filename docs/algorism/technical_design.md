# PDF差分検出システム 技術設計書

## 1. システムアーキテクチャ

### 1.1 全体構成
```
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│   Frontend      │    │    Backend      │    │  External APIs   │
│   (Next.js)     │◄──►│   (FastAPI)     │◄──►│  (LLM, Azure)    │
└─────────────────┘    └─────────────────┘    └──────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │    Database     │
                       │  (SQL Server)   │
                       └─────────────────┘
```

### 1.2 Clean Architecture適用
- **Domain Layer**: PDF差分検出ビジネスロジック
- **Application Layer**: ユースケース実행・DTO変換
- **Infrastructure Layer**: 外部システム統合・永続化

## 2. 核心コンポーネント設計

### 2.1 PDF解析エンジン (`PDFAnalysisEngine`)

#### 2.1.1 責務
- テキストベースPDF専用の高速解析
- 文書構造・座標情報の抽出
- レイアウト解析・テキストブロック識別

#### 2.1.2 技術仕様
```python
class PDFAnalysisEngine:
    def __init__(self, pymupdf_service: PyMuPDFService):
        self.pymupdf_service = pymupdf_service
    
    def extract_text_blocks(self, pdf_bytes: bytes) -> List[TextBlock]:
        """Extract text blocks with coordinate information"""
        pass
    
    def extract_document_structure(self, pdf_bytes: bytes) -> DocumentStructure:
        """Extract hierarchical document structure"""
        pass
```

#### 2.1.3 パフォーマンス最適化
- **メモリ効率**: ページ単位での遅延読み込み
- **並列処理**: ThreadPoolExecutorによるページ並列解析
- **キャッシュ**: 解析結果の一時保存

### 2.2 読み順序推定システム (`ReadingOrderEstimator`)

#### 2.2.1 LLMベース推定戦略
```python
class ReadingOrderEstimator:
    def __init__(self, llm_client: LLMClient, fallback_strategy: PositionBasedStrategy):
        self.llm_client = llm_client
        self.fallback_strategy = fallback_strategy
    
    def estimate_reading_order(self, text_blocks: List[TextBlock]) -> List[TextBlock]:
        """Estimate natural reading order using LLM with fallback"""
        try:
            return self._llm_based_estimation(text_blocks)
        except LLMAPIException:
            return self.fallback_strategy.sort_by_position(text_blocks)
```

#### 2.2.2 フォールバック戦略
- **位置ベースソート**: LLM API障害時の代替手法
- **ハイブリッド**: LLM + 位置情報の組み合わせ
- **信頼度評価**: 推定結果の品質評価

### 2.3 単語ベース差分検出器 (`WordBasedDiffDetector`)

#### 2.3.1 アルゴリズム設計
```python
class WordBasedDiffDetector:
    def __init__(self, mecab_tokenizer: MeCabTokenizer):
        self.mecab_tokenizer = mecab_tokenizer
    
    def detect_differences(self, doc1: ProcessedDocument, doc2: ProcessedDocument) -> List[DiffResult]:
        """Detect word-level differences using MeCab tokenization
        
        前提: 差分アノテーションは文章単位で入力される想定
        """
        # 文章単位での分割（アノテーション単位に対応）
        sentences1 = self.mecab_tokenizer.split_sentences(doc1.text)
        sentences2 = self.mecab_tokenizer.split_sentences(doc2.text)
        
        # MeCabによる単語分割
        tokens1 = [self.mecab_tokenizer.tokenize(sent) for sent in sentences1]
        tokens2 = [self.mecab_tokenizer.tokenize(sent) for sent in sentences2]
        
        alignment = self._align_documents(tokens1, tokens2)
        differences = self._calculate_differences(alignment)
        
        return self._classify_changes(differences)
```


### 2.4 アンサンブル統合システム (`EnsembleIntegrator`)

#### 2.4.1 アンサンブル戦略の明確化

**アンサンブル対象**:
1. **文字ベース差分検出** (SequenceMatcher) - 従来手法
2. **単語ベース差分検出** (形態素解析ベース) - 新手法

**統合方式**:
- 両手法の結果を統合し、より高精度な差分検出を実現
- 文字レベル: 細かい変更を検出
- 単語レベル: 意味的な変更を検出

```python
class EnsembleIntegrator:
    def __init__(self, 
                 pdf_engine: PDFAnalysisEngine,
                 reading_order: ReadingOrderEstimator,
                 char_diff_detector: CharacterBasedDiffDetector,
                 word_diff_detector: WordBasedDiffDetector,
                 confidence_evaluator: ConfidenceEvaluator):
        self.pdf_engine = pdf_engine
        self.reading_order = reading_order
        self.char_diff_detector = char_diff_detector
        self.word_diff_detector = word_diff_detector
        self.confidence_evaluator = confidence_evaluator
    
    def process_pdf_comparison(self, pdf1: bytes, pdf2: bytes) -> ComparisonResult:
        """Execute full PDF comparison pipeline"""
        # 1. PDF解析
        doc1_blocks = self.pdf_engine.extract_text_blocks(pdf1)
        doc2_blocks = self.pdf_engine.extract_text_blocks(pdf2)
        
        # 2. 読み順序推定
        doc1_ordered = self.reading_order.estimate_reading_order(doc1_blocks)
        doc2_ordered = self.reading_order.estimate_reading_order(doc2_blocks)
        
        # 3. 文字ベース差分検出
        char_differences = self.char_diff_detector.detect_differences(doc1_ordered, doc2_ordered)
        
        # 4. 単語ベース差分検出
        word_differences = self.word_diff_detector.detect_differences(doc1_ordered, doc2_ordered)
        
        # 5. 結果統合
        differences = self._merge_detection_results(char_differences, word_differences)
        
        # 6. 信頼度評価
        confidence_scores = self.confidence_evaluator.evaluate(differences)
        
        return ComparisonResult(differences, confidence_scores)
```

## 3. データモデル設計

### 3.1 文書関連モデル
```python
@dataclass
class TextBlock:
    text: str
    bbox: BoundingBox
    page_number: int
    confidence: float
    block_type: BlockType  # PARAGRAPH, HEADER, FOOTER, TABLE

@dataclass
class ProcessedDocument:
    text_blocks: List[TextBlock]
    reading_order: List[int]  # インデックス順序
    metadata: DocumentMetadata

@dataclass 
class Token:
    surface: str          # 表層形
    part_of_speech: str   # 品詞
    base_form: str        # 基本形
    position: int         # 文章内位置
```

### 3.1.1 MeCabトークナイザー実装
```python
class MeCabTokenizer:
    def __init__(self, mecab_dicdir: Optional[str] = None):
        import MeCab
        self.tagger = MeCab.Tagger(f"-d {mecab_dicdir}" if mecab_dicdir else "")
    
    def tokenize(self, text: str) -> List[Token]:
        """MeCab形態素解析による日本語テキストのトークン化"""
        result = []
        node = self.tagger.parseToNode(text)
        position = 0
        
        while node:
            if node.surface:
                features = node.feature.split(',')
                token = Token(
                    surface=node.surface,
                    part_of_speech=features[0],
                    base_form=features[6] if len(features) > 6 else node.surface,
                    position=position
                )
                result.append(token)
                position += len(node.surface)
            node = node.next
        
        return result
    
    def split_sentences(self, text: str) -> List[str]:
        """文章単位分割（アノテーション単位に対応）"""
        import re
        # 句点・感嘆符・疑問符・改行等で文章を分割
        sentences = re.split(r'[。！？\n]+', text)
        return [s.strip() for s in sentences if s.strip()]
```

### 3.2 差分検出結果モデル
```python
@dataclass
class DiffResult:
    change_type: ChangeType  # ADDITION, DELETION, MODIFICATION
    confidence_score: float
    original_text: Optional[str]
    modified_text: Optional[str]
    location: DocumentLocation
    detection_method: str  # "character_based" or "word_based"
    
@dataclass
class ComparisonResult:
    differences: List[DiffResult]
    summary: ComparisonSummary
    processing_time: float
    performance_metrics: PerformanceMetrics
```

## 4. API設計

### 4.1 RESTful API
```python
# メイン差分検出API
@router.post("/api/v1/pdf/compare")
async def compare_pdfs(
    file1: UploadFile,
    file2: UploadFile,
    options: ComparisonOptions = Body(default_factory=ComparisonOptions)
) -> ComparisonResult:
    """Compare two PDF files and return differences"""
    pass

# 結果取得API
@router.get("/api/v1/comparison/{comparison_id}")
async def get_comparison_result(comparison_id: str) -> ComparisonResult:
    """Get comparison result by ID"""
    pass

# エクスポートAPI
@router.get("/api/v1/comparison/{comparison_id}/export")
async def export_comparison(
    comparison_id: str,
    format: ExportFormat = Query(ExportFormat.PDF)
) -> FileResponse:
    """Export comparison result in specified format"""
    pass
```

### 4.2 WebSocket (リアルタイム進捗)
```python
@router.websocket("/ws/comparison/{comparison_id}")
async def comparison_progress(websocket: WebSocket, comparison_id: str):
    """Real-time comparison progress updates"""
    await websocket.accept()
    # 進捗更新の送信
```

## 5. 性能最適化戦略

### 5.1 メモリ管理
```python
class MemoryOptimizedProcessor:
    def __init__(self, max_memory_mb: int = 1024):
        self.max_memory_mb = max_memory_mb
        self.memory_monitor = MemoryMonitor()
    
    def process_large_pdf(self, pdf_bytes: bytes) -> ProcessingResult:
        """Process large PDF with memory constraints"""
        if self.memory_monitor.get_usage() > self.max_memory_mb * 0.8:
            self._trigger_garbage_collection()
        
        # ページ単位での分割処理
        return self._process_in_chunks(pdf_bytes)
```

### 5.2 並列処理最適化
```python
class ParallelProcessingOrchestrator:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def parallel_page_analysis(self, pages: List[PDFPage]) -> List[PageAnalysisResult]:
        """Analyze pages in parallel"""
        futures = [self.executor.submit(self._analyze_page, page) for page in pages]
        return [future.result() for future in futures]
```

## 6. エラーハンドリング設計

### 6.1 階層的エラー処理
```python
class PDFComparisonError(Exception):
    """Base exception for PDF comparison errors"""
    pass

class PDFFormatError(PDFComparisonError):
    """Invalid PDF format error"""
    pass

class LLMAPIError(PDFComparisonError):
    """LLM API related error"""
    pass

class MemoryLimitError(PDFComparisonError):
    """Memory limit exceeded error"""
    pass
```

### 6.2 障害復旧戦略
- **自動リトライ**: LLM API障害時の指数バックオフ
- **フォールバック**: LLM不使用の代替処理モード
- **グレースフルデグラデーション**: 部分的機能での継続動作

## 7. セキュリティ考慮事項

### 7.1 データ保護
- **一時ファイル**: 処理後の即座削除
- **メモリクリア**: 機密情報のメモリ上削除
- **暗号化**: 保存時・転送時の暗号化

### 7.2 API制限
- **レート制限**: ユーザー・IP別のリクエスト制限
- **ファイルサイズ制限**: 100MB上限の厳格な実施
- **認証**: JWT トークンベース認証

## 8. 監視・ログ設計

### 8.1 メトリクス収集
```python
class PerformanceMonitor:
    def track_comparison_metrics(self, result: ComparisonResult):
        """Track performance metrics"""
        metrics = {
            'processing_time': result.processing_time,
            'document_size': result.document_size,
            'differences_found': len(result.differences),
            'memory_usage': self.get_memory_usage(),
            'api_calls': result.api_calls_count
        }
        self.metrics_collector.record(metrics)
```

### 8.2 構造化ログ
```python
logger.info("PDF comparison started", extra={
    'comparison_id': comparison_id,
    'file1_size': file1.size,
    'file2_size': file2.size,
    'user_id': user.id
})
```

## 9. 品質保証戦略

### 9.1 テスト設計
- **単体テスト**: 各コンポーネントの独立テスト
- **統合テスト**: エンドツーエンドの差分検出テスト
- **性能テスト**: 負荷・メモリ使用量テスト
- **精度テスト**: 既知データセットでの検出率評価

### 9.2 継続的品質改善
- **A/Bテスト**: アルゴリズム改善効果の定量評価
- **フィードバック収集**: ユーザーからの品質評価
- **定期的再評価**: 月次での性能・精度レビュー

この技術設計は、修正された要件定義に基づき、テキストベースPDF専用の効率的な差分検出システムの実現を目指しています。