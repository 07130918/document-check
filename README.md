# PDF差分検出API - FastAPI統合版

Azure Document IntelligenceとLLMを活用した高精度PDF差分検出システムのAPI実装です。

## 🚀 クイックスタート

### 必要な環境
- Docker & Docker Compose
- Python 3.13+ (ローカル開発時)
- uv (Python パッケージマネージャー)

### 環境変数の設定
.envをslackでもらう

### Docker環境での起動

```bash
# コンテナのビルドと起動
make up

# または直接docker-composeを使用
docker compose up -d
```

APIは `http://localhost:8000` で利用可能になります。

## 📡 API仕様

### APIドキュメント
サーバー起動後、以下のURLでアクセス可能:
- 対話型APIドキュメント: `http://localhost:8000/docs`
- ReDoc形式: `http://localhost:8000/redoc`

## 🧪 テスト

### APIテストスクリプト

```bash
# PDF差分検出APIの動作確認
./test_pdf_diff_api.sh
```

## 🧪 A/Bテストデータセット

### テストケース構成
- **簡単レベル（10ケース）**: 明確な文字・数値変更
- **中程度レベル（10ケース）**: 複数箇所変更・微細数値変更
- **困難レベル（10ケース）**: 表現言い換え・語順変更・同義語置換

### 評価指標
- **真陽性率（Recall）**: 見逃し防止の指標
- **適合率（Precision）**: 誤検出抑制の指標
- **処理時間**: 性能指標
- **統計的有意性**: p値・効果量による改善確認

## 🛠 開発コマンド

```bash
# Dockerコンテナ起動
make up

# コンテナ停止
make down

# コンテナログ確認
make logs

# クリーンアップ
make clean
```

## 🔬 技術仕様

### アーキテクチャ
- **APIフレームワーク**: FastAPI
- **PDF処理**: Azure Document Intelligence + PyMuPDF
- **差分検出**: LLMベース文書比較アルゴリズム
- **認証**: APIキーベースミドルウェア
- **実行方式**: インプロセス実行（高速化）

### 主要コンポーネント
- **PDF差分プロセッサ**: `pdf_diff_processor.py`
  - バッチ処理対応
  - 拡張出力ハンドラー統合
  - ZIPレスポンス生成
- **拡張出力ハンドラー**: `enhanced_output_handler_v3_4.py`
  - 注釈付きPDF生成
  - 差分ハイライト表示
  - JSON結果出力

### 依存関係
- **Python**: 3.13+
- **FastAPI**: REST APIフレームワーク
- **PyMuPDF**: PDF解析・注釈
- **Azure Document Intelligence**: 文書解析AI
- **OpenAI GPT**: 差分判定・要約生成
- **MeCab**: 日本語形態素解析
- **uv**: Pythonパッケージ管理

### Docker環境
- **ベースイメージ**: python:3.13-slim
- **MeCab**: UTF-8対応IPA辞書
- **ホットリロード**: 開発環境対応
- **ボリューム**: 仮想環境キャッシュ

## 🗺 ロードマップ

### ✅ Phase 0: ベースライン構築（完了）
- [x] prj-meiji-document-checkアルゴリズム移植
- [x] A/Bテスト基盤構築
- [x] 30ケーステストデータセット作成

### 🔜 Phase 1: 基盤構築
- [ ] PyMuPDF統合
- [ ] Azure AI Document Intelligence統合
- [ ] 改良アルゴリズム基盤

### 🔜 Phase 2: 高度化
- [ ] LLM中心型読み順序推定
- [ ] MeCab単語ベース差分検出
- [ ] アンサンブル統合

### 🔜 Phase 3: 最適化
- [ ] 並列処理最適化
- [ ] メモリ効率化
- [ ] エラー処理強化

### 🔜 Phase 4: 統合・検証
- [ ] 最終A/Bテスト実行
- [ ] 統計的有意性検定
- [ ] 性能改善確認

## 📈 成功基準

### 必須要件
- ベースライン比 **真陽性率+10%以上**
- ベースライン比 **処理時間-30%以上**
- ベースライン比 **誤検出率-20%以上**

### 統計的検証
- **p値 < 0.05**: 統計的有意性
- **Cohen's d ≥ 0.5**: 実用的効果量

## 🤝 貢献

1. Docker環境でのテスト実行
2. 新しいテストケース追加
3. 改良アルゴリズムの実装
4. 性能最適化

## 📝 ライセンス

AICE Internal Project
