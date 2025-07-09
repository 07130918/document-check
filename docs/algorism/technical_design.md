# 文書差分検出システム 技術設計書

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

### 2.1 文書解析エンジン (`DocumentAnalysisEngine`)

#### 2.1.1 責務
- PDF・Word・Pptxファイルの統合解析
- bbox_text_data形式でのデータ抽出
- 文書構造・座標情報の抽出
- レイアウト解析・単語単位のテキスト識別

#### 2.1.2 技術仕様
```python
class DocumentAnalysisEngine:
    def __init__(self, pdf_service: PyMuPDFService, 
                 docx_service: DocxService,
                 pptx_service: PptxService):
        self.pdf_service = pdf_service
        self.docx_service = docx_service
        self.pptx_service = pptx_service
    
    def extract_bbox_text_data(self, file_bytes: bytes, file_type: str) -> List[BBoxTextData]:
        """Extract bbox_text_data list from document"""
        if file_type == 'pdf':
            return self.pdf_service.extract_bbox_data(file_bytes)
        elif file_type == 'docx':
            return self.docx_service.extract_bbox_data(file_bytes)
        elif file_type == 'pptx':
            return self.pptx_service.extract_bbox_data(file_bytes)
    
    def process_pages(self, bbox_data_list: List[BBoxTextData]) -> Dict[int, List[BBoxTextData]]:
        """Process bbox_text_data by pages"""
        pages = {}
        for bbox_data in bbox_data_list:
            page = bbox_data['page']
            if page not in pages:
                pages[page] = []
            pages[page].append(bbox_data)
        return pages
```

#### 2.1.3 パフォーマンス最適化
- **メモリ効率**: ページ単位での遅延読み込み
- **並列処理**: ThreadPoolExecutorによるページ並列解析
- **キャッシュ**: 解析結果の一時保存

### 2.2 読み順序推定システム (`ReadingOrderEstimator`)

#### 2.2.1 座標ベース推定戦略
```python
class ReadingOrderEstimator:
    def __init__(self):
        pass
    
    def estimate_reading_order(self, bbox_data_list: List[BBoxTextData]) -> List[BBoxTextData]:
        """Estimate reading order based on bbox coordinates"""
        # ページごとに処理
        pages = {}
        for bbox_data in bbox_data_list:
            page = bbox_data['page']
            if page not in pages:
                pages[page] = []
            pages[page].append(bbox_data)
        
        # 各ページで座標ベースソート
        ordered_data = []
        for page in sorted(pages.keys()):
            page_data = pages[page]
            # 左上から右下への自然な読み順序でソート
            # y座標（上から下）を優先、同じ行はx座標（左から右）でソート
            sorted_page = sorted(page_data, 
                               key=lambda d: (d['bbox'][1], d['bbox'][0]))
            ordered_data.extend(sorted_page)
        
        return ordered_data
```

#### 2.2.2 読み順序推定の詳細
- **座標ベースソート**: y座標を主軸、x座標を副軸とした並び替え
- **行検出**: 近接するy座標を同一行として扱う
- **カラム対応**: 複数カラムレイアウトの検出と処理

### 2.3 BBoxベース差分検出器 (`BBoxBasedDiffDetector`)

#### 2.3.1 アルゴリズム設計
```python
class BBoxBasedDiffDetector:
    def __init__(self):
        pass
    
    def detect_differences(self, doc1_bbox_list: List[BBoxTextData], 
                         doc2_bbox_list: List[BBoxTextData]) -> List[DiffResult]:
        """Detect differences between documents using bbox_text_data
        
        bbox_text_dataは既に単語単位で分割されている前提
        """
        differences = []
        
        # ページごとに処理
        doc1_pages = self._group_by_page(doc1_bbox_list)
        doc2_pages = self._group_by_page(doc2_bbox_list)
        
        all_pages = set(doc1_pages.keys()) | set(doc2_pages.keys())
        
        for page in sorted(all_pages):
            page1_data = doc1_pages.get(page, [])
            page2_data = doc2_pages.get(page, [])
            
            # 単語レベルでの差分検出
            page_diffs = self._detect_page_differences(page1_data, page2_data)
            differences.extend(page_diffs)
        
        return differences
    
    def _group_by_page(self, bbox_list: List[BBoxTextData]) -> Dict[int, List[BBoxTextData]]:
        """Group bbox_text_data by page number"""
        pages = {}
        for bbox_data in bbox_list:
            page = bbox_data['page']
            if page not in pages:
                pages[page] = []
            pages[page].append(bbox_data)
        return pages
    
    def _detect_page_differences(self, page1_data: List[BBoxTextData], 
                               page2_data: List[BBoxTextData]) -> List[DiffResult]:
        """Detect differences within a page"""
        # 位置と内容を考慮した差分検出
        pass
```


### 2.4 出力生成システム (`OutputGenerator`)

#### 2.4.1 ハイライト生成戦略

**ハイライト対象**:
1. **読み順序**: 番号付き青色ハイライト
2. **差分箇所**: 色分けハイライト
   - 追加: 緑色
   - 削除: 赤色
   - 修正: 黄色

**出力形式**:
- PDF: 元ファイルにハイライトを追加
- Word(DOCX): 元ファイルにハイライトを追加
- PowerPoint(PPTX): 元ファイルにハイライトを追加

```python
class OutputGenerator:
    def __init__(self, 
                 pdf_handler: PDFHighlightHandler,
                 docx_handler: DocxHighlightHandler,
                 pptx_handler: PptxHighlightHandler):
        self.pdf_handler = pdf_handler
        self.docx_handler = docx_handler
        self.pptx_handler = pptx_handler
    
    def generate_highlighted_document(self, 
                                    original_file: bytes,
                                    file_type: str,
                                    reading_order: List[BBoxTextData],
                                    differences: List[DiffResult]) -> bytes:
        """Generate document with highlights"""
        if file_type == 'pdf':
            return self.pdf_handler.add_highlights(original_file, reading_order, differences)
        elif file_type == 'docx':
            return self.docx_handler.add_highlights(original_file, reading_order, differences)
        elif file_type == 'pptx':
            return self.pptx_handler.add_highlights(original_file, reading_order, differences)

class DocumentComparisonPipeline:
    def __init__(self,
                 doc_engine: DocumentAnalysisEngine,
                 reading_order: ReadingOrderEstimator,
                 diff_detector: BBoxBasedDiffDetector,
                 output_generator: OutputGenerator):
        self.doc_engine = doc_engine
        self.reading_order = reading_order
        self.diff_detector = diff_detector
        self.output_generator = output_generator
    
    def process_document_comparison(self, file1: bytes, file2: bytes, 
                                  file_type: str) -> Tuple[bytes, bytes]:
        """Execute full document comparison pipeline"""
        # 1. bbox_text_data抽出
        doc1_bbox_list = self.doc_engine.extract_bbox_text_data(file1, file_type)
        doc2_bbox_list = self.doc_engine.extract_bbox_text_data(file2, file_type)
        
        # 2. 読み順序推定
        doc1_ordered = self.reading_order.estimate_reading_order(doc1_bbox_list)
        doc2_ordered = self.reading_order.estimate_reading_order(doc2_bbox_list)
        
        # 3. 差分検出
        differences = self.diff_detector.detect_differences(doc1_ordered, doc2_ordered)
        
        # 4. ハイライト付きファイル生成
        highlighted_file1 = self.output_generator.generate_highlighted_document(
            file1, file_type, doc1_ordered, differences)
        highlighted_file2 = self.output_generator.generate_highlighted_document(
            file2, file_type, doc2_ordered, differences)
        
        return highlighted_file1, highlighted_file2
```

## 3. データモデル設計

### 3.1 文書関連モデル
```python
from typing import TypedDict, List

class BBoxTextData(TypedDict):
    bbox: List[float]  # [x, y, width, height]
    text: str          # 単語単位のテキスト
    page: int          # ページ番号

@dataclass
class DiffResult:
    change_type: ChangeType  # ADDITION, DELETION, MODIFICATION
    original_bbox: Optional[BBoxTextData]
    modified_bbox: Optional[BBoxTextData]
    page: int
    confidence: float

class ChangeType(Enum):
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
```

### 3.1.1 文書タイプ別BBox抽出実装
```python
class PyMuPDFService:
    def extract_bbox_data(self, pdf_bytes: bytes) -> List[BBoxTextData]:
        """Extract bbox_text_data from PDF using PyMuPDF"""
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        bbox_data_list = []
        
        for page_num, page in enumerate(doc):
            words = page.get_text("words")  # [(x0, y0, x1, y1, "word", block_no, line_no, word_no)]
            for word in words:
                bbox_data = BBoxTextData(
                    bbox=[word[0], word[1], word[2]-word[0], word[3]-word[1]],
                    text=word[4],
                    page=page_num
                )
                bbox_data_list.append(bbox_data)
        
        return bbox_data_list

class DocxService:
    def extract_bbox_data(self, docx_bytes: bytes) -> List[BBoxTextData]:
        """Extract bbox_text_data from Word document"""
        # python-docxを使用した実装
        # 注: Wordファイルからは直接bbox情報を取得できないため、
        # レイアウト情報を推定する必要がある
        pass

class PptxService:
    def extract_bbox_data(self, pptx_bytes: bytes) -> List[BBoxTextData]:
        """Extract bbox_text_data from PowerPoint presentation"""
        # python-pptxを使用した実装
        # スライド内のシェイプから位置情報を取得
        pass
```

### 3.2 ハイライト情報モデル
```python
@dataclass
class Highlight:
    bbox: List[float]  # [x, y, width, height]
    page: int
    color: str  # "red", "green", "yellow", "blue"
    label: Optional[str]  # 読み順序の番号など
    
@dataclass
class HighlightedDocument:
    original_file: bytes
    highlights: List[Highlight]
    file_type: str
    metadata: Dict[str, Any]
```

## 4. API設計

### 4.1 RESTful API
```python
# メイン差分検出API
@router.post("/api/v1/document/compare")
async def compare_documents(
    file1: UploadFile,
    file2: UploadFile,
    file_type: str = Form(...),  # "pdf", "docx", "pptx"
    options: ComparisonOptions = Body(default_factory=ComparisonOptions)
) -> Dict[str, str]:
    """Compare two documents and return highlighted files"""
    # ハイライト付きファイルのダウンロードURLを返す
    return {
        "file1_url": "/download/{file1_id}",
        "file2_url": "/download/{file2_id}"
    }

# ハイライト付きファイルダウンロードAPI
@router.get("/api/v1/download/{file_id}")
async def download_highlighted_file(file_id: str) -> FileResponse:
    """Download highlighted file"""
    pass

# プレビューAPI
@router.post("/api/v1/document/preview")
async def preview_highlights(
    file: UploadFile,
    highlights: List[Highlight]
) -> Dict[str, Any]:
    """Preview highlights on document"""
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
    
    def process_large_document(self, file_bytes: bytes, file_type: str) -> ProcessingResult:
        """Process large document with memory constraints"""
        if self.memory_monitor.get_usage() > self.max_memory_mb * 0.8:
            self._trigger_garbage_collection()
        
        # ページ単位での分割処理
        return self._process_in_chunks(file_bytes, file_type)
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
class DocumentComparisonError(Exception):
    """Base exception for document comparison errors"""
    pass

class DocumentFormatError(DocumentComparisonError):
    """Invalid document format error"""
    pass

class BBoxExtractionError(DocumentComparisonError):
    """BBox extraction failed error"""
    pass

class MemoryLimitError(DocumentComparisonError):
    """Memory limit exceeded error"""
    pass
```

### 6.2 障害復旧戦略
- **フォールバック**: ファイルタイプ別の代替処理
- **グレースフルデグラデーション**: 部分的機能での継続動作
- **エラー通知**: 管理者へのエラー通知

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
    def track_comparison_metrics(self, 
                               file_type: str,
                               processing_time: float,
                               file_size: int,
                               differences: List[DiffResult]):
        """Track performance metrics"""
        metrics = {
            'file_type': file_type,
            'processing_time': processing_time,
            'file_size': file_size,
            'differences_found': len(differences),
            'memory_usage': self.get_memory_usage(),
            'pages_processed': self.get_pages_processed()
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

### 9.2 人力評価プロセス
- **評価対象**: ハイライト付き出力ファイル
- **評価項目**:
  - 読み順序の正確性
  - 差分検出の正確性
  - 誤検出・見逃しの確認
- **評価シート**: 結果記録用テンプレート提供

この技術設計は、bbox_text_dataを中心としたPDF・Word・Pptx文書の差分検出システムの実現を目指しています。出力はハイライト付きファイルとし、人力での評価を前提としています。