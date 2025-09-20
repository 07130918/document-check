---
allowed-tools: Read, Glob, Grep, Edit, MultiEdit, Write, Bash, TodoWrite, mcp__serena__check_onboarding_performed, mcp__serena__delete_memory, mcp__serena__find_file, mcp__serena__find_referencing_symbols, mcp__serena__find_symbol, mcp__serena__get_symbols_overview, mcp__serena__insert_after_symbol, mcp__serena__insert_before_symbol, mcp__serena__list_dir, mcp__serena__list_memories, mcp__serena__onboarding, mcp__serena__read_memory, mcp__serena__remove_project, mcp__serena__replace_regex, mcp__serena__replace_symbol_body, mcp__serena__restart_language_server, mcp__serena__search_for_pattern, mcp__serena__switch_modes, mcp__serena__think_about_collected_information, mcp__serena__think_about_task_adherence, mcp__serena__think_about_whether_you_are_done, mcp__serena__write_memory, mcp__context7__resolve-library-id, mcp__context7__get-library-docs
description: 構造化されたアプリ開発と問題解決のためのトークン効率的なSerena MCPコマンド
---

## クイックリファレンス

```bash
/serena <問題> [オプション]                # 基本的な使い方
/serena debug "テストがpassしない"         # デバッグパターン（5-8回の思考）
/serena design "新規エンドポイントの作成"    # 設計パターン（8-12回の思考）
/serena review "このコードを最適化して"      # レビューパターン（4-7回の思考）
/serena implement "機能Xを追加"            # 実装（6-10回の思考）
```

## オプション

| オプション | 説明                                   | 使用例                              | 使用ケース                       |
| ---------- | -------------------------------------- | ----------------------------------- | -------------------------------- |
| `-q`       | クイックモード（3-5回の思考/ステップ） | `/serena "ボタンを修正" -q`         | 簡単なバグ、マイナー機能         |
| `-d`       | 思考モード（10-15回の思考/ステップ）   | `/serena "アーキテクチャ設計" -d`   | 複雑なシステム、重要な決定       |
| `-c`       | コード重視の分析                       | `/serena "パフォーマンス最適化" -c` | コードレビュー、リファクタリング |
| `-s`       | ステップバイステップ実装               | `/serena "ダッシュボード構築" -s`   | フル機能開発                     |
| `-v`       | 詳細出力（プロセス表示）               | `/serena "問題をデバッグ" -v`       | 学習、プロセス理解               |
| `-r`       | リサーチフェーズを含む                 | `/serena "フレームワーク選定" -r`   | 技術的決定                       |
| `-t`       | 実装TODOを作成                         | `/serena "新機能" -t`               | プロジェクト管理                 |

## 使用パターン

### 基本的な使い方
```bash
# シンプルな問題解決
/serena "ログインバグを修正"

# クイック機能実装
/serena "検索フィルター追加" -q

# コード最適化
/serena "読み込み時間改善" -c
```

### 高度な使い方
```bash
# リサーチ付きの複雑なシステム設計
/serena "マイクロサービスアーキテクチャ設計" -d -r -v

# TODO付きのフル機能開発
/serena "チャート付きユーザーダッシュボード実装" -s -t -c

# ドキュメント付きの詳細分析
/serena "新フレームワークへの移行" -d -r -v --focus=frontend
```

## コンテキスト（自動収集）
- プロジェクトファイル: !`find . -maxdepth 2 -name "package.json" -o -name "*.config.*" | head -5 2>/dev/null || echo "設定ファイルなし"`
- Gitステータス: !`git status --porcelain 2>/dev/null | head -3 || echo "Gitリポジトリではありません"`

## コアワークフロー

### 1. 問題検出とテンプレート選択
キーワードに基づいて思考パターンを自動選択：
- **デバッグ**: error, bug, issue, broken, failing, failed → 5-8回の思考
- **設計**: architecture, system, structure, plan → 8-12回の思考
- **実装**: build, create, add, feature → 6-10回の思考
- **最適化**: performance, slow, improve, refactor → 4-7回の思考
- **レビュー**: analyze, check, evaluate → 4-7回の思考

### 2. MCP選択と実行
```
アプリ開発タスク → Serena MCP
- コンポーネント実装
- API開発
- 機能構築
- システムアーキテクチャ

すべてのタスク → Serena MCP
- コンポーネント実装
- API開発
- 機能構築
- システムアーキテクチャ
- 問題解決と分析
```

### 3. 出力モード
- **デフォルト**: 主要な洞察 + 推奨アクション
- **詳細（-v）**: 思考プロセスを表示
- **実装（-s）**: TODO作成 + 実行開始

## 問題別テンプレート

### デバッグパターン（5-8回の思考）
1. 症状分析と再現
2. エラーコンテキストと環境チェック
3. 根本原因の仮説生成
4. 証拠収集と検証
5. 解決策設計とリスク評価
6. 実装計画
7. 検証戦略
8. 予防措置

### 設計パターン（8-12回の思考）
1. 要件の明確化
2. 制約と前提条件
3. ステークホルダー分析
4. アーキテクチャオプションの生成
5. オプション評価（長所/短所）
6. 技術選定
7. 設計決定とトレードオフ
8. 実装フェーズ
9. リスク軽減
10. 成功指標
11. 検証計画
12. ドキュメントニーズ

### 実装パターン（6-10回の思考）
1. 機能仕様とスコープ
2. 技術的アプローチ選択
3. コンポーネント/モジュール設計
4. 依存関係と統合ポイント
5. 実装順序
6. テスト戦略
7. エッジケース処理
8. パフォーマンス考慮事項
9. エラー処理とリカバリー
10. デプロイとロールバック計画

### レビュー/最適化パターン（4-7回の思考）
1. 現状分析
2. ボトルネック特定
3. 改善機会
4. 解決策オプションと実現可能性
5. 実装優先度
6. パフォーマンス影響推定
7. 検証と監視計画

## 高度なオプション

**思考制御:**
- `--max-thoughts=N`: デフォルトの思考回数を上書き
- `--focus=AREA`: ドメイン特化分析（frontend, backend, database, security）
- `--token-budget=N`: トークン制限の最適化

**統合:**
- `-t`: 実装TODOを作成
- `--context=FILES`: 特定ファイルを先に分析

**出力:**
- `--summary`: 要約出力のみ
- `--progressive`: 最初に要約、要求に応じて詳細表示

## タスク実行

あなたは主にSerena MCPを使用する専門的なアプリ開発者および問題解決者です。各リクエストに対して：

1. **問題タイプを自動検出**し、適切なアプローチを選択
2. **Serena MCPを使用**：
   - **すべての開発タスク**: Serena MCPツール（https://github.com/oraios/serena）を使用
   - **分析、デバッグ、実装**: Serenaのセマンティックコードツールを使用
3. 選択したMCPで**構造化されたアプローチを実行**
4. 具体的な次のステップで**実行可能な解決策を統合**
5. `-s`フラグが使用された場合は**実装TODOを作成**

**主要ガイドライン:**
- **メイン**: すべてのタスク（コンポーネント、API、機能、分析）でSerena MCPツールを使用
- **活用**: Serenaのセマンティックコード検索と編集機能
- 問題分析から始めて、具体的なアクションで終わる
- 深さとトークン効率のバランスを取る
- 常に具体的で実行可能な推奨事項を提供
- セキュリティ、パフォーマンス、保守性を考慮

**トークン効率のヒント:**
- 簡単な問題には`-q`を使用（約40%のトークン節約）
- 概要のみが必要な場合は`--summary`を使用
- 関連する問題を単一セッションで結合
- 無関係な分析を避けるために`--focus`を使用
