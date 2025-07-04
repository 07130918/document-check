# PDF差分検出システム - システムアーキテクチャ

## システム全体構成図

### アーキテクチャ設計の考慮点
- **Next.js フルスタック構成**: Next.jsのAPI Routesを活用し、フロントエンドとユーザー認証API機能を1つのコンテナに統合
- **責任分離**: PDF処理は専用のFastAPIサービスで処理し、認証・ユーザー管理はNext.js API Routesで処理
- **セキュリティ**: フロントエンドUIは直接データベースにアクセスせず、Next.js API Routesを経由

```mermaid
graph TB
    subgraph "Users"
        U[利用者<br/>30-60人]
    end

    subgraph "Azure Front Door"
        FD[Front Door<br/>CDN/WAF/SSL終端]
    end

    subgraph "Azure Container Instances"
        subgraph "Web Container"
            subgraph "Next.js App (Port: 3000)"
                WEBUI[Frontend UI<br/>React Components]
                WEBAPI[API Routes<br/>認証・ユーザー管理]
            end
        end
        subgraph "API Container"
            API[FastAPI Service<br/>Port: 8000<br/>PDF処理]
        end
    end

    subgraph "Azure Storage"
        BLOB[Blob Storage<br/>一時ファイル保存]
    end

    subgraph "Azure Database"
        DB[(PostgreSQL<br/>ユーザー管理)]
    end

    subgraph "Azure Security"
        KV[Key Vault<br/>シークレット管理]
    end

    subgraph "External APIs"
        OPENAI[OpenAI API<br/>読み順序推定]
    end

    subgraph "Azure Monitoring"
        AI[Application Insights]
        LA[Log Analytics]
    end

    U -->|HTTPS| FD
    FD -->|Port 3000| WEBUI
    WEBUI -->|Internal| WEBAPI
    WEBUI -->|REST API| API
    API -->|Upload/Download| BLOB
    WEBAPI -->|User Auth| DB
    API -->|Reading Order| OPENAI
    API -->|Secrets| KV
    WEBUI -->|Telemetry| AI
    API -->|Logs| LA
```

## データフロー図

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant WUI as Frontend UI
    participant WAPI as Next.js API Routes
    participant A as FastAPI Service
    participant S as Storage
    participant P as PDF処理エンジン
    participant LLM as OpenAI API
    participant DB as Database

    U->>WUI: ログイン
    WUI->>WAPI: 認証リクエスト
    WAPI->>DB: ユーザー認証
    DB-->>WAPI: 認証結果
    WAPI->>WAPI: JWT生成
    WAPI-->>WUI: 認証トークン
    WUI-->>U: 認証完了

    U->>WUI: PDFアップロード画面
    U->>WUI: 2つのPDFファイル選択
    WUI->>A: POST /api/diff/upload
    A->>S: PDFファイル保存
    A-->>WUI: タスクID返却
    WUI-->>U: アップロード完了

    A->>P: 差分検出処理開始
    P->>P: テキスト抽出
    P->>LLM: 読み順序推定リクエスト
    LLM-->>P: 読み順序結果
    P->>P: 差分検出（MeCab）
    P->>S: 結果保存

    WUI->>A: GET /api/diff/status/{id}
    A-->>WUI: 処理状況
    WUI-->>U: 進捗表示

    WUI->>A: GET /api/diff/result/{id}
    A->>S: 結果取得
    A-->>WUI: 差分データ
    WUI-->>U: 差分表示

    U->>WUI: ダウンロード要求
    WUI->>A: GET /api/diff/download/{id}
    A->>S: 注釈付きPDF取得
    A-->>WUI: PDFファイル
    WUI-->>U: ダウンロード

    A->>S: ファイル削除（処理完了後）
```

## インフラストラクチャ構成

```mermaid
graph LR
    subgraph "開発環境"
        GH[GitHub<br/>ソースコード]
        GA[GitHub Actions<br/>CI/CD]
    end

    subgraph "Azure Container Registry"
        ACR[コンテナイメージ<br/>web-app:latest<br/>pdf-service:latest]
    end

    subgraph "本番環境"
        subgraph "ネットワーク層"
            FD2[Azure Front Door]
            WAF[WAF Rules]
        end

        subgraph "コンピュート層"
            ACI[Azure Container Instances<br/>自動スケーリング]
        end

        subgraph "データ層"
            ST[Storage Account<br/>暗号化]
            PG[PostgreSQL<br/>自動バックアップ]
        end

        subgraph "管理層"
            KV2[Key Vault]
            MON[Azure Monitor]
        end
    end

    GH -->|Push| GA
    GA -->|Build & Push| ACR
    GA -->|Deploy| ACI
    ACR -->|Pull| ACI
    FD2 --> WAF
    WAF --> ACI
    ACI --> ST
    ACI --> PG
    ACI --> KV2
    ACI --> MON
```

## セキュリティアーキテクチャ

```mermaid
graph TB
    subgraph "外部アクセス"
        USER[ユーザー]
        ATK[攻撃者]
    end

    subgraph "境界防御"
        SSL[SSL/TLS 1.3]
        WAF2[WAF<br/>・SQLインジェクション防止<br/>・XSS防止<br/>・DDoS防御]
    end

    subgraph "アプリケーション層"
        AUTH[認証<br/>・JWT<br/>・セッション管理]
        RBAC[認可<br/>・ロールベース<br/>・リソース制御]
    end

    subgraph "データ保護"
        ENC[暗号化<br/>・保存時暗号化<br/>・転送時暗号化]
        DEL[データ削除<br/>・処理後即削除<br/>・監査ログ]
    end

    USER -->|HTTPS| SSL
    ATK -->|攻撃| WAF2
    SSL --> AUTH
    WAF2 -.阻止.-> ATK
    AUTH --> RBAC
    RBAC --> ENC
    ENC --> DEL
```

## スケーラビリティ設計

```mermaid
graph LR
    subgraph "負荷分散"
        LB[Front Door<br/>地理的分散]
    end

    subgraph "水平スケーリング"
        WEB1[Web App<br/>Instance 1]
        WEB2[Web App<br/>Instance 2]
        WEB3[Web App<br/>Instance N]
        
        API1[API Service<br/>Instance 1]
        API2[API Service<br/>Instance 2]
        API3[API Service<br/>Instance N]
    end

    subgraph "自動スケーリング"
        AS[Auto Scaling<br/>・CPU使用率<br/>・メモリ使用率<br/>・リクエスト数]
    end

    LB --> WEB1
    LB --> WEB2
    LB --> WEB3
    
    WEB1 --> API1
    WEB2 --> API2
    WEB3 --> API3
    
    AS -->|スケールアウト| WEB3
    AS -->|スケールアウト| API3
```

## 災害復旧（DR）計画

```mermaid
graph TB
    subgraph "プライマリリージョン（東日本）"
        P_ACI[Container Instances]
        P_ST[Storage Account]
        P_DB[PostgreSQL]
    end

    subgraph "セカンダリリージョン（西日本）"
        S_ACI[Container Instances<br/>スタンバイ]
        S_ST[Storage Account<br/>レプリケーション]
        S_DB[PostgreSQL<br/>読み取りレプリカ]
    end

    subgraph "グローバルサービス"
        FD3[Front Door<br/>自動フェイルオーバー]
        TM[Traffic Manager]
    end

    FD3 --> TM
    TM -->|通常時| P_ACI
    TM -.災害時.-> S_ACI
    
    P_ST -.レプリケーション.-> S_ST
    P_DB -.レプリケーション.-> S_DB
```

## 監視・運用アーキテクチャ

```mermaid
graph TB
    subgraph "アプリケーション"
        APP[Web/API<br/>Applications]
    end

    subgraph "監視収集"
        AI2[Application Insights<br/>・パフォーマンス<br/>・例外<br/>・依存関係]
        LA2[Log Analytics<br/>・ログ集約<br/>・クエリ分析]
        MET[Metrics<br/>・CPU/メモリ<br/>・レスポンス時間]
    end

    subgraph "アラート"
        ALT[Alert Rules<br/>・閾値監視<br/>・異常検知]
        ACT[Action Groups<br/>・メール通知<br/>・Teams通知]
    end

    subgraph "可視化"
        DASH[Dashboard<br/>・リアルタイム<br/>・KPI表示]
        WB[Workbooks<br/>・詳細分析<br/>・レポート]
    end

    APP --> AI2
    APP --> LA2
    APP --> MET
    
    AI2 --> ALT
    LA2 --> ALT
    MET --> ALT
    
    ALT --> ACT
    
    AI2 --> DASH
    LA2 --> DASH
    MET --> WB
```

## コスト最適化アーキテクチャ

```mermaid
graph LR
    subgraph "コスト要因"
        COMP[コンピュート<br/>Container Instances]
        STOR[ストレージ<br/>Blob/Database]
        NET[ネットワーク<br/>帯域/CDN]
        MON2[監視<br/>ログ保存]
        LLM_COST[LLM API<br/>読み順序推定]
    end

    subgraph "最適化施策"
        AUTO[自動スケーリング<br/>・最小インスタンス設定<br/>・スケジュール制御]
        LIFE[ライフサイクル<br/>・古いデータ削除<br/>・アーカイブ]
        CACHE[キャッシング<br/>・CDN活用<br/>・Redis]
        RET[保存期間<br/>・ログ30日<br/>・メトリクス90日]
        LLM_OPT[LLM最適化<br/>・結果キャッシュ<br/>・使用量制限]
    end

    COMP --> AUTO
    STOR --> LIFE
    NET --> CACHE
    MON2 --> RET
    LLM_COST --> LLM_OPT
```

## 技術スタック一覧

| レイヤー | 技術/サービス | 用途 | バージョン | 備考 |
|---------|--------------|------|------------|------|
| **フロントエンド（杉山さん担当）** |
| フロントエンド | Next.js 15, React 19, TypeScript 5.5+ | フルスタックフレームワーク | 2025年7月最新安定版 | 新規選定（API Routes含む） |
| スタイリング | Tailwind CSS 3.4+ | CSSフレームワーク | 最新安定版 | 新規選定 |
| 状態管理 | Zustand 4.5+ | クライアント状態管理 | 最新安定版 | 新規選定 |
| JavaScript実行環境 | Node.js 22 LTS | 実行環境 | LTS | 新規選定 |
| PDF表示 | PDF.js 4.0+ | ブラウザPDF表示 | 最新安定版 | 新規選定 |
| **バックエンド（横山さん担当）** |
| バックエンド | FastAPI, Python 3.11 | APIサーバー | pyproject.toml準拠 | 既存選定済み |
| PDF処理 | PyMuPDF ^1.23.8 | PDF解析 | pyproject.toml準拠 | 既存選定済み |
| 日本語処理 | mecab-python3 ^1.0.6 | 形態素解析 | pyproject.toml準拠 | 既存選定済み |
| 数値計算 | numpy ^1.24.0 | 数値処理 | pyproject.toml準拠 | 既存選定済み |
| LLM API | OpenAI API | 読み順序推定 | GPT-4 Turbo | 暫定選定※5 |
| **インフラ（杉山さん担当）** |
| コンテナ | Docker 26.0+, Azure Container Instances | アプリケーション実行環境 | 最新安定版 | 新規選定 |
| CDN/WAF | Azure Front Door | コンテンツ配信・セキュリティ | - | 新規選定 |
| ストレージ | Azure Blob Storage | ファイル保存 | - | 一時保存のみ※2 |
| データベース | Azure Database for PostgreSQL 16+ | ユーザー管理 | PostgreSQL 16推奨 | 新規選定 |
| 認証 | JWT (RFC 7519) | ユーザー認証 | 標準仕様 | 新規選定 |
| 監視 | Application Insights, Log Analytics | パフォーマンス監視 | - | ログ保持期間未定※4 |
| CI/CD | GitHub Actions | 自動デプロイ | - | 新規選定 |
| IaC | Terraform 1.8+ | インフラ管理 | 最新安定版 | 新規選定 |

### 未確定要素による影響
※1: 画像・表・グラフの差分検出は未定（質問No.2）
※2: ファイル保存要件は不要と確定（質問No.6）
※3: 予算（質問No.9）とシステム稼働率（質問No.12）による
※4: ログ管理要件（質問No.13）による
※5: LLM APIは暫定でOpenAI GPT-4 Turboを想定、Azure OpenAI Serviceの検討も必要