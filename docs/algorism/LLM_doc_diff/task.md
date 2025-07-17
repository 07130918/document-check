# LLMベース文書差分検出システム 実装タスク詳細

## Phase 0: ベースライン互換性確保（1週間）

### Task 0.1: ベースライン出力形式の再現
- [ ] 出力ディレクトリ構造の実装
  - [ ] `output/llm_diff_test/` ディレクトリ作成
  - [ ] `PDFs/` サブディレクトリ（ハイライト付きPDF出力）
  - [ ] `debug/` サブディレクトリ（CSV形式のデバッグ情報）
  - [ ] `reports/` サブディレクトリ（実行レポート）
- [ ] ベースライン互換出力ファイル
  - [ ] `{year}_compared.pdf` - 差分ハイライト付きPDF
  - [ ] `{year}_original_order.pdf` - 元の読み順序表示
  - [ ] `{year}_reading_order.pdf` - 推定読み順序表示
  - [ ] `{year}_diff.csv` - 差分詳細CSV
  - [ ] `{year}_reading_order_estimated.csv` - 推定読み順序CSV
  - [ ] `execution_report.json/md` - 実行レポート

### Task 0.2: LLM統合基盤構築
- [ ] OpenAI API統合
  - [ ] `LLMService` クラス作成
  - [ ] APIキー管理（環境変数）
  - [ ] モデル選択機能（gpt-4o-mini推奨）
  - [ ] レート制限・エラーハンドリング
- [ ] プロンプトテンプレート管理
  - [ ] `PromptTemplateManager` クラス作成
  - [ ] 読み順序推定用プロンプト
  - [ ] 差分重要度評価用プロンプト
  - [ ] 文書要約用プロンプト

### Task 0.3: Word/PowerPoint対応強化
- [ ] PDF変換サービス実装
  - [ ] `PDFConverter` 抽象クラス
  - [ ] `LibreOfficePDFConverter` 実装
  - [ ] `SpirePDFConverter` 実装（オプション）
- [ ] Word専用処理
  - [ ] PDF変換によるBBox取得
  - [ ] フォールバック: テキストのみ抽出
- [ ] PowerPoint専用処理
  - [ ] python-pptxによる直接位置情報取得
  - [ ] EMU→ポイント変換実装

## Phase 1: LLM活用機能実装（1週間）

### Task 1.1: LLMベース読み順序推定
- [ ] 読み順序推定エンジン
  - [ ] `LLMReadingOrderEstimator` クラス作成
  - [ ] BBox情報をLLMに渡すフォーマット設計
  - [ ] ページレイアウト理解プロンプト
  - [ ] 複雑なレイアウト（表、カラム）対応
- [ ] ハイブリッド推定
  - [ ] 座標ベース推定とLLM推定の組み合わせ
  - [ ] 信頼度スコアによる選択
  - [ ] フォールバック機構

### Task 1.2: LLMベース差分検出強化
- [ ] 意味的差分検出
  - [ ] `SemanticDiffDetector` クラス作成
  - [ ] 文脈を考慮した差分判定
  - [ ] 同義語・言い換えの認識
- [ ] 差分重要度評価
  - [ ] `DiffImportanceEvaluator` クラス作成
  - [ ] 数値・日付変更の重要度判定
  - [ ] 契約条件変更の検出
  - [ ] 1-10スケールでの重要度スコアリング

### Task 1.3: 文書理解機能
- [ ] 文書構造解析
  - [ ] `DocumentStructureAnalyzer` クラス作成
  - [ ] セクション・章立ての認識
  - [ ] 表・リストの構造理解
- [ ] 要約生成
  - [ ] `DocumentSummarizer` クラス作成
  - [ ] 変更箇所の要約
  - [ ] 重要変更のハイライト

## Phase 2: Azure Document Intelligence統合（1週間）

### Task 2.1: Azure統合実装
- [ ] Azure Document Intelligenceサービス
  - [ ] `AzureDocumentIntelligenceService` クラス作成
  - [ ] レイアウト解析API統合
  - [ ] OCR機能活用
- [ ] ハイブリッド処理
  - [ ] スキャンPDFの自動検出
  - [ ] OCR必要時の自動切り替え
  - [ ] ネイティブ抽出との結果統合

### Task 2.2: 高精度BBox抽出
- [ ] Azure活用による精度向上
  - [ ] より正確な単語境界検出
  - [ ] 表構造の詳細解析
  - [ ] 画像内テキストの抽出
- [ ] 処理最適化
  - [ ] キャッシュ機構実装
  - [ ] バッチ処理対応

## Phase 3: 性能最適化とAPI実装（1週間）

### Task 3.1: 処理性能最適化
- [ ] LLM呼び出し最適化
  - [ ] バッチ処理実装
  - [ ] 非同期処理対応
  - [ ] キャッシュ戦略
- [ ] コスト最適化
  - [ ] 必要最小限のLLM呼び出し
  - [ ] モデル選択の最適化
  - [ ] トークン使用量監視

### Task 3.2: FastAPI実装
- [ ] エンドポイント実装
  - [ ] `/api/v1/llm/compare` - LLM版比較API
  - [ ] `/api/v1/llm/analyze` - 文書解析API
  - [ ] `/api/v1/llm/summary` - 要約生成API
- [ ] 非同期処理
  - [ ] バックグラウンドタスク実装
  - [ ] 進捗通知WebSocket
  - [ ] ジョブキュー管理

### Task 3.3: 監視・ログ強化
- [ ] LLM使用状況監視
  - [ ] APIコール数追跡
  - [ ] トークン使用量記録
  - [ ] コスト計算・レポート
- [ ] 品質監視
  - [ ] LLM応答品質チェック
  - [ ] エラー率監視
  - [ ] レスポンスタイム追跡

## Phase 4: 統合テストと評価（1週間）

### Task 4.1: ベースラインとの比較評価
- [ ] 精度比較
  - [ ] 読み順序推定精度
  - [ ] 差分検出精度
  - [ ] 誤検出率
- [ ] 性能比較
  - [ ] 処理時間
  - [ ] メモリ使用量
  - [ ] API応答時間

### Task 4.2: LLM特有機能の評価
- [ ] 意味的差分検出の評価
  - [ ] 同義語認識テスト
  - [ ] 文脈理解テスト
- [ ] 重要度評価の妥当性
  - [ ] 人手評価との比較
  - [ ] ビジネスルールとの整合性

### Task 4.3: ドキュメント作成
- [ ] API仕様書
  - [ ] LLM版エンドポイント
  - [ ] パラメータ説明
  - [ ] 使用例
- [ ] 運用ガイド
  - [ ] コスト管理方法
  - [ ] モデル選択指針
  - [ ] トラブルシューティング

## 成功基準

### 機能要件
- [ ] ベースラインと同等の出力形式
- [ ] Word/PowerPoint完全対応
- [ ] LLMによる高度な差分検出
- [ ] Azure Document Intelligence統合

### 性能要件
- [ ] 検出精度: ベースライン以上
- [ ] 処理時間: 10分以内（LLM呼び出し含む）
- [ ] 同時処理: 3ユーザー対応

### 品質要件
- [ ] 意味的差分検出の実現
- [ ] 重要度評価の実装
- [ ] 完全なエラーハンドリング

## GitHub Issue作成用サマリー

### Issue Title
「LLMベース文書差分検出システムの実装」

### Issue Description
ベースラインシステムをLLMで強化し、以下を実現：
1. Word/PowerPoint完全対応
2. 意味的差分検出
3. 差分重要度の自動評価
4. Azure Document Intelligence統合

### Milestones
- Week 1: ベースライン互換性とLLM基盤
- Week 2: LLM機能実装
- Week 3: Azure統合と最適化
- Week 4: 統合テストと評価

### Labels
- enhancement
- AI/ML
- document-processing
- high-priority