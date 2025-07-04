# PDF差分検出システム - システムアーキテクチャ

## システム全体構成図

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
            WEB[Next.js App<br/>Port: 3000]
        end
        subgraph "API Container"
            API[FastAPI Service<br/>Port: 8000]
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

    subgraph "Azure Monitoring"
        AI[Application Insights]
        LA[Log Analytics]
    end

    U -->|HTTPS| FD
    FD -->|Port 3000| WEB
    WEB -->|REST API| API
    API -->|Upload/Download| BLOB
    WEB -->|User Auth| DB
    API -->|Secrets| KV
    WEB -->|Telemetry| AI
    API -->|Logs| LA
```

## データフロー図

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant W as Webアプリ
    participant A as API Service
    participant S as Storage
    participant P as PDF処理エンジン

    U->>W: ログイン
    W->>W: JWT生成
    W-->>U: 認証トークン

    U->>W: PDFアップロード画面
    U->>W: 2つのPDFファイル選択
    W->>A: POST /api/diff/upload
    A->>S: PDFファイル保存
    A-->>W: タスクID返却
    W-->>U: アップロード完了

    A->>P: 差分検出処理開始
    P->>P: テキスト抽出
    P->>P: 読み順序推定（LLM）
    P->>P: 差分検出（MeCab）
    P->>S: 結果保存

    W->>A: GET /api/diff/status/{id}
    A-->>W: 処理状況
    W-->>U: 進捗表示

    W->>A: GET /api/diff/result/{id}
    A->>S: 結果取得
    A-->>W: 差分データ
    W-->>U: 差分表示

    U->>W: ダウンロード要求
    W->>A: GET /api/diff/download/{id}
    A->>S: 注釈付きPDF取得
    A-->>W: PDFファイル
    W-->>U: ダウンロード

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
    end

    subgraph "最適化施策"
        AUTO[自動スケーリング<br/>・最小インスタンス設定<br/>・スケジュール制御]
        LIFE[ライフサイクル<br/>・古いデータ削除<br/>・アーカイブ]
        CACHE[キャッシング<br/>・CDN活用<br/>・Redis]
        RET[保存期間<br/>・ログ30日<br/>・メトリクス90日]
    end

    COMP --> AUTO
    STOR --> LIFE
    NET --> CACHE
    MON2 --> RET
```

## 技術スタック一覧

| レイヤー | 技術/サービス | 用途 | 備考 |
|---------|--------------|------|------|
| フロントエンド | Next.js 14, React 18, TypeScript | UIフレームワーク | 確定 |
| スタイリング | Tailwind CSS | CSSフレームワーク | 確定 |
| 状態管理 | Zustand | クライアント状態管理 | 確定 |
| バックエンド | FastAPI, Python 3.11 | APIサーバー | 確定 |
| PDF処理 | PyMuPDF, PDF.js | PDF解析・表示 | テキストPDFのみ対応※1 |
| 日本語処理 | MeCab | 形態素解析 | 確定 |
| コンテナ | Docker, Azure Container Instances | アプリケーション実行環境 | 確定 |
| CDN/WAF | Azure Front Door | コンテンツ配信・セキュリティ | 確定 |
| ストレージ | Azure Blob Storage | ファイル保存 | 一時保存のみ※2 |
| データベース | Azure Database for PostgreSQL | ユーザー管理 | スペック要調整※3 |
| 認証 | JWT | ユーザー認証 | 確定 |
| 監視 | Application Insights, Log Analytics | パフォーマンス監視 | ログ保持期間未定※4 |
| CI/CD | GitHub Actions | 自動デプロイ | 確定 |
| IaC | Terraform | インフラ管理 | 確定 |

### 未確定要素による影響
※1: 画像・表・グラフの差分検出は未定（質問No.2）
※2: ファイル保存要件は不要と確定（質問No.6）
※3: 予算（質問No.9）とシステム稼働率（質問No.12）による
※4: ログ管理要件（質問No.13）による