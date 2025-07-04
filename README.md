# PDF差分検出システム - ベースライン実装

A/Bテスト用のベースライン実装とテスト基盤を提供するPDF差分検出システムです。

## 🚀 クイックスタート

### Docker環境での実行（推奨）

```bash
# 1. Docker imageビルド
make build

# 2. ベースラインテスト実行
make run

# 3. 結果確認
cat results/baseline_report.md
```

### ローカル環境での実行

```bash
# 1. 依存関係インストール
make install

# 2. MeCab動作確認
make test-mecab

# 3. ベースラインテスト実行
python run_baseline_test.py
```

## 📁 プロジェクト構成

```
├── baseline/                    # prj-meiji-document-checkベースライン
│   ├── text_normalizer.py      # テキスト正規化（128種類変換ルール）
│   ├── sequence_matcher_detector.py  # SequenceMatcherベース差分検出
│   └── __init__.py
├── evaluation/                  # A/Bテスト評価基盤
│   ├── comparison_evaluator.py # 統計的有意性検定フレームワーク
│   ├── test_data_generator.py  # 30ケーステストデータ生成
│   └── __init__.py
├── data/
│   └── test_dataset.json      # テストデータセット（30ケース）
├── results/
│   ├── baseline_performance.json  # ベースライン性能結果
│   └── baseline_report.md         # 性能レポート
├── pyproject.toml              # Poetry依存関係管理
├── Dockerfile                  # Docker環境定義
├── docker-compose.yml          # サービス定義
└── Makefile                    # 実行コマンド集約
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