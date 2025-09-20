# PDF差分検出システム - ベースライン実装

A/Bテスト用のベースライン実装とテスト基盤を提供するPDF差分検出システムです。

## 🚀 クイックスタート

### 必要な環境
- Python 3.13+
- uv (Python パッケージマネージャー)

### インストール

```bash
# appsディレクトリに移動
cd apps

# 依存関係のインストール（uv使用）
uv sync
```

### APIサーバーの起動

```bash
# 開発用サーバーの起動
cd apps
uv run uvicorn api.main:app --reload --port 8000
```

APIは `http://localhost:8000` で利用可能になります。

### 差分検出スクリプトの実行

```bash
# デフォルトのサンプルPDFで実行（apps/sample配下のPDFを使用）
cd apps
uv run llm_docs_diff_v3.4/test_llm_diff_v3_4.py

# カスタムPDFファイルを指定して実行
uv run llm_docs_diff_v3.4/test_llm_diff_v3_4.py file1.pdf file2.pdf
```

### APIエンドポイント
- `GET /` - ウェルカムメッセージ
- `GET /api/hello` - "Hello API"を返却

### APIドキュメント
サーバー起動後、以下のURLでアクセス可能:
- 対話型APIドキュメント: `http://localhost:8000/docs`

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
# 開発用コンテナ起動
make dev

# コードフォーマット
make format

# テスト実行
make test

# 全30ケーステスト
make full-test

# クリーンアップ
make clean
```

## 📊 ベースライン性能

現在のprj-meiji-document-checkベースライン：
- **処理時間**: ~0.002秒/ケース
- **メモリ使用量**: 最小限
- **技術基盤**: SequenceMatcher + レーベンシュタイン距離

## 🔬 技術仕様

### 依存関係
- **Python**: 3.11+
- **PyMuPDF**: PDF解析
- **python-Levenshtein**: 高速文字列類似度
- **MeCab**: 日本語形態素解析（Phase 2以降）
- **scipy**: 統計的有意性検定

### Docker環境
- **ベースイメージ**: python:3.11-slim
- **MeCab**: UTF-8対応IPA辞書
- **Poetry**: 依存関係管理

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
