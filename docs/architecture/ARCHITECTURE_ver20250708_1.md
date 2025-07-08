# PDF差分検出システム - アーキテクチャ（案）

## システム概要

### アーキテクチャ構成
```mermaid
graph TB
    subgraph "利用者"
        U[ユーザー<br/>IP制限付きアクセス]
    end

    subgraph "Azure App Service"
        WEB[Streamlit Web App<br/>Python 3.11]
    end

    subgraph "Azure Container Instances"
        API[Web API Backend<br/>PDF差分検出ロジック<br/>（仮：FastAPI）]
    end

    subgraph "Azure OpenAI Service"
        LLM[GPT-4<br/>読み順序推定]
    end

    subgraph "GitHub"
        REPO[ソースコード]
        GA[GitHub Actions]
    end

    U -->|HTTPS| WEB
    WEB -->|HTTP POST /api/detect| API
    API -->|API Call| LLM
    REPO -->|Push| GA
    GA -->|Deploy| WEB
```

**注意**: API実装方法（FastAPI等）は仮決定。7月末に横山さんが最終決定。

## 技術スタック

| レイヤー | 技術 | 担当 | 備考 |
|---------|------|------|------|
| **フロントエンド** | Streamlit 1.35+ | 杉山 | Python製Webフレームワーク |
| **バックエンド** | Web API（仮：FastAPI） | 横山さん | 7月末完成・実装方法確定 |
| **PDF処理** | PyMuPDF | 横山さん | 実装済み |
| **日本語処理** | MeCab | 横山さん | 実装済み |
| **LLM** | Azure OpenAI Service | 横山さん | GPT-4使用 |
| **ホスティング** | Azure App Service | 杉山 | B1インスタンス |
| **API実行環境** | Azure Container Instances | 杉山 | 2vCPU/4GB |
| **CI/CD** | GitHub Actions | 杉山 | 自動デプロイ |

## データフロー

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant S as Streamlit
    participant A as Web API
    participant O as Azure OpenAI
    
    U->>S: アクセス（IP確認）
    U->>S: PDF2ファイルアップロード
    S->>A: POST /api/detect
    A->>A: PDF解析・テキスト抽出
    A->>O: 読み順序推定リクエスト
    O-->>A: 読み順序結果
    A->>A: 差分検出処理
    A->>A: 結果PDF生成
    A-->>S: JSON + Base64 PDF
    S-->>U: 結果表示
    U->>S: PDFダウンロード
```

## API仕様（7月末確定予定）

### エンドポイント（仮）
```
POST /api/detect
Content-Type: multipart/form-data
```

### リクエスト
- `file1`: PDFファイル（必須、最大50MB）
- `file2`: PDFファイル（必須、最大50MB）

### レスポンス（仮）
```json
{
  "status": "success",
  "processing_time": 5.2,
  "summary": {
    "additions": 10,
    "deletions": 5,
    "modifications": 3
  },
  "result_pdf": "base64_encoded_pdf_string",
  "error_code": null,
  "message": "処理が正常に完了しました"
}
```

### エラーレスポンス（仮）
```json
{
  "status": "error",
  "processing_time": 0.5,
  "summary": null,
  "result_pdf": null,
  "error_code": "FILE_TOO_LARGE",
  "message": "ファイルサイズが50MBを超えています"
}
```

## セキュリティ設計

### アクセス制御
- **IP制限**: App Serviceのアクセス制限機能で実装
- **許可IPリスト**: 顧客環境のIPアドレスのみ許可
- **認証**: なし（PoC版のため）

### 通信セキュリティ
- **HTTPS**: App Service標準SSL証明書使用
- **API間通信**: Container InstancesのプライベートIP使用

### 機密情報管理
- **APIキー**: App Service環境変数に格納
- **接続文字列**: Key Vaultは使用せず、環境変数で管理

## インフラ構成

### リソース一覧
| リソース | SKU/サイズ | 用途 | 月額コスト |
|---------|-----------|------|------------|
| App Service Plan | B1 | Streamlitホスティング | ¥5,000 |
| App Service | - | Webアプリケーション | - |
| Container Instances | 2vCPU/4GB | API実行 | ¥2,000 |
| Storage Account | Standard LRS | 一時ファイル保存 | ¥500 |

### ネットワーク構成
- パブリックアクセス（IP制限付き）
- VNet統合なし（PoC簡略化のため）

## デプロイメント設計

### CI/CDパイプライン
```yaml
name: Deploy Streamlit to Azure

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: azure/webapps-deploy@v2
        with:
          app-name: pdf-diff-poc-web
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

### 環境変数
```bash
# App Service設定
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com/
AZURE_OPENAI_API_KEY=***
API_ENDPOINT=http://container-internal-ip:8000  # 仮
```

## 制約事項

### 機能制約
- 同時処理数: 10リクエストまで
- ファイルサイズ: 最大50MB/ファイル
- 処理時間: 最大60秒でタイムアウト
- ファイル保持: 処理完了後即削除

### 非機能要件
- 可用性: 99%（PoC版）
- 応答時間: 30ページPDFで60秒以内
- 同時ユーザー数: 最大10名

## コスト試算

| 項目 | 月額費用 |
|------|----------|
| App Service (B1) | ¥5,000 |
| Container Instances | ¥2,000 |
| Storage | ¥500 |
| Azure OpenAI | 従量課金 |
| **合計** | **¥7,500〜** |

## 今後の拡張性

### 本番化時の考慮事項
1. **認証追加**: Azure AD B2C統合
2. **スケーラビリティ**: App Service自動スケール
3. **監視**: Application Insights導入
4. **データ保持**: Blob Storageでの結果保存
5. **非同期処理**: Azure Functionsでのバックグラウンド処理

## API実装に関する柔軟性

7月末にAPI実装方法が確定するまで、以下の点で柔軟に対応：

1. **API抽象化層**: フロントエンドはAPIクライアントを抽象化
2. **モックAPI**: 7月はモックAPIで開発を進行
3. **最小限の結合**: API仕様のみに依存し、実装詳細に依存しない設計

このアーキテクチャにより、8月20日までにPoC版の本番稼働を実現します。

---

*更新日: 2025年7月8日*
*API実装方法は7月末に横山さんが決定予定*