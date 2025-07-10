# PDF差分検出システム PoC - プロジェクト計画（案）

## プロジェクト概要

### 目的
2つのPDFファイルの差分を検出し、視覚的に表示するシステムのPoC開発

### 体制
- **横山さん**：PDF解析ロジック、API実装（仮FastAPI）、LLM調整（7月末まで）
- **杉山**：Streamlitフロントエンド、Azureインフラ、CI/CD（8月20日まで）

### 完成予定日
**2025年8月20日（水）**

## アーキテクチャ（案）

### システム構成（モノリシック）
```
[ユーザー] 
    ↓
[Azure App Service - 単一コンテナ]
  ├─ Streamlit Web App (Port 8501)
  └─ PDF差分検出API (Port 8000/内部通信)
    ↓
[Azure OpenAI Service]
```

**注意**: モジュラーモノリシック構成を採用。横山さんのDockerイメージをベースに8月統合。

### 技術スタック
- **フロントエンド**: Streamlit (Python)
- **バックエンド**: Web API（FastAPI/内部通信）
- **PDF処理**: PyMuPDF
- **日本語処理**: MeCab
- **LLM**: Azure OpenAI Service
- **インフラ**: Azure App Service（単一コンテナ）
- **CI/CD**: GitHub Actions

### セキュリティ
- IP制限によるアクセス制御
- ユーザー認証なし（PoC版）
- HTTPS通信

## スケジュール（案）

### 7月（30時間）
| 期間 | 作業内容 | 時間 |
|------|----------|------|
| 7/9-10 | 環境準備、Streamlit学習 | 6h |
| 7/15,17,22-25 | UIモックアップ、インフラ設計 | 18h |
| 7/28,31 | モックAPI作成、仕様受領 | 6h |

**除外日**: 7/11、7/14、7/16、7/18、7/21（祝）、7/29-30

### 8月（100時間）
| 期間 | 作業内容 | 時間 |
|------|----------|------|
| 8/1-7 | Streamlit開発、API統合 | 40h |
| 8/12-15 | Azureデプロイ、CI/CD構築 | 32h |
| 8/18-19 | セキュリティ設定、最終調整 | 16h |
| 8/20 | 本番デプロイ | 4h |

## API仕様（7月末確定）

### エンドポイント（仮）
```
POST /api/detect
```

### リクエスト
- `file1`: PDFファイル（最大50MB）
- `file2`: PDFファイル（最大50MB）

### レスポンス
```json
{
  "status": "success",
  "processing_time": 5.2,
  "summary": {
    "additions": 10,
    "deletions": 5,
    "modifications": 3
  },
  "result_pdf": "base64_encoded_pdf"
}
```

## インフラ構成（モノリシック）

### リソース
- **App Service**: B1プラン（モノリシックアプリ用）
- ~~**Container Instances**: 2 vCPU, 4GB RAM（削除）~~
- **Storage Account**: 結果PDF一時保存用

### 推定コスト
約5,000円/月（PoC環境）
※Container Instances削除により¥2,000/月削減

## デプロイメント

### GitHub Actions
```yaml
name: Deploy to Azure
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      - name: Deploy to App Service
        uses: azure/webapps-deploy@v3
```

## 成功基準

### 機能要件
- [ ] 2つのPDFの差分検出が可能
- [ ] 結果をPDFで出力
- [ ] 30ページのPDFを60秒以内で処理

### 非機能要件
- [ ] Azure上で稼働
- [ ] IP制限によるアクセス制御
- [ ] 自動デプロイ可能

## リスクと対策

| リスク | 対策 |
|--------|------|
| API実装方法の変更 | 抽象化層で柔軟に対応 |
| API仕様の遅延 | モックAPIで事前開発 |
| 統合の問題 | モノリシック構成で単純化、8月初週で統合 |
| 性能問題 | 同期処理で妥協（60秒タイムアウト） |
| CORS設定 | モノリシックで回避（同一オリジン） |

## プロジェクト完了条件

1. **8月20日時点で本番環境にデプロイ済み**
2. **基本的な差分検出機能が動作**
3. **簡易運用マニュアル（README）を作成して引き継ぎ**

---

*更新日: 2025年7月10日*
*モジュラーモノリシック構成に変更（Container Instances削除）*