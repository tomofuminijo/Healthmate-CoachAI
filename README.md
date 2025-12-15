# HealthCoachAI エージェント

Amazon Bedrock AgentCore Runtime上で動作する健康支援AIエージェントです。

## 概要

HealthCoachAIは、ユーザーの健康目標達成を支援するAIエージェントです。以下の機能を提供します：

- 健康データの分析とパーソナライズされたアドバイス
- 健康目標の設定と進捗追跡
- 運動や食事に関する実践的な指導
- モチベーション維持のためのサポート

## 主な機能

### 🔐 自動認証
- JWTトークンからユーザーIDを自動抽出
- Cognito認証との統合
- セキュアなユーザー識別

### 🕒 時間認識
- 現在日時の自動取得
- 時間帯に応じた適切なアドバイス
- 日付・時刻を考慮した健康管理

### 🔗 MCP統合
- HealthManagerMCPサーバーとの連携
- 健康管理ツールへのアクセス
- リアルタイムデータ処理

### ☁️ 動的設定
- CloudFormationからの設定自動取得
- 環境変数サポート
- フォールバック機能

## セットアップ

### 前提条件

- Python 3.12+
- AWS CLI設定済み
- Amazon Bedrock AgentCore Runtime環境
- MCP Gatewayスタックのデプロイ

### 🚀 クイックスタート（推奨）

#### 1. カスタムIAMロール作成とデプロイ

```bash
# 1. リポジトリをクローン
git clone https://github.com/tomofuminijo/HealthCoachAI.git
cd HealthCoachAI

# 2. 仮想環境を作成・アクティベート
python3 -m venv venv
source venv/bin/activate

# 3. 依存関係をインストール
pip install -r requirements.txt

# 4. AWS認証を設定
aws configure
# または環境変数を設定
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"

# 5. ワンコマンドデプロイ（IAMロール自動作成）
./deploy_to_aws.sh
```

#### 2. 手動でIAMロール作成（詳細制御が必要な場合）

```bash
# カスタムIAMロールを事前作成
python3 create_custom_iam_role.py

# デプロイ実行
./deploy_to_aws.sh
```

### 🔐 IAMロール権限

カスタムIAMロールには以下の権限が含まれます：

- **AgentCore Runtime基本権限**: Bedrock、ログ、ECR等

### 環境変数設定

デプロイ時に以下の環境変数が自動設定されます：

```bash
# HealthManagerMCP Gateway ID（デプロイ時に自動設定）
HEALTHMANAGER_GATEWAY_ID="gateway-id-from-cloudformation"

# AWSリージョン（デフォルト: us-west-2）
export HEALTH_STACK_NAME="YOUR_CLOUDFORMATION_STACK_NAME"

# AWS設定（オプション）
export AWS_REGION="your-aws-region"

# 手動設定（CloudFormationが利用できない場合）
export HEALTH_GATEWAY_ID="your-gateway-id"
export COGNITO_USER_POOL_ID="your-user-pool-id"
export COGNITO_CLIENT_ID="your-client-id"
export COGNITO_CLIENT_SECRET="your-client-secret"
```

### インストール

```bash
# リポジトリのクローン
git clone <repository-url>
cd health-coach-ai

# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt
```

### エージェントの実行

```bash
# 直接実行
python health_coach_ai/agent.py

# ランナースクリプトを使用
python run_agent.py
```

## 開発・テスト

### 手動テスト

```bash
# インタラクティブテストプログラム
python manual_test_agent.py
```

機能：
- マルチライン入力対応
- セッション維持
- リアルタイムJWT認証
- DynamoDB確認用ユーザーID表示

### 自動テスト

```bash
# 基本機能テスト
python test_health_coach_agent_simple.py

# 包括的統合テスト
python test_health_coach_agent.py

# MCPスキーマ発見テスト
python test_mcp_schema_discovery.py
```

## アーキテクチャ

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   フロントエンド │    │  HealthCoachAI   │    │   MCPサーバー   │
│      UI         │───▶│   エージェント   │───▶│   (バックエンド) │
│                 │    │                  │    │                 │
│ JWT Token       │    │ • JWT Decode     │    │ • User Mgmt     │
│ User Auth       │    │ • Time Aware     │    │ • Health Goals  │
│                 │    │ • Dynamic Config │    │ • Activities    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   CloudFormation │
                       │     Config       │
                       │                  │
                       │ • Gateway ID     │
                       │ • Cognito IDs    │
                       │ • Region Info    │
                       └──────────────────┘
```

## プロジェクト構成

```
health_coach_ai/
├── health_coach_ai/
│   ├── __init__.py
│   └── agent.py                    # メインエージェント実装
├── manual_test_agent.py           # インタラクティブテストプログラム
├── test_config_helper.py          # テスト用設定ヘルパー
├── test_health_coach_agent.py     # 包括的統合テスト
├── test_health_coach_agent_simple.py  # 基本機能テスト
├── test_mcp_schema_discovery.py   # MCPスキーマ発見テスト
├── run_agent.py                   # エージェント実行スクリプト
├── requirements.txt               # 依存関係
├── README.md                      # このファイル
└── .gitignore                     # Git除外設定
```

## セキュリティ

- 認証情報のハードコードなし
- 環境変数またはCloudFormationからの動的設定
- 安全なJWTトークン認証
- AWS IAMロールベースのアクセス制御

## 設定

### CloudFormationスタック出力

エージェントは以下のCloudFormationスタック出力を期待します：

- `GatewayId`: MCP Gateway ID
- `UserPoolId`: Cognito User Pool ID  
- `UserPoolClientId`: Cognito Client ID

### 手動設定

CloudFormationが利用できない場合は、以下の環境変数を設定してください：

```bash
export HEALTH_GATEWAY_ID="your-mcp-gateway-id"
export COGNITO_USER_POOL_ID="your-cognito-user-pool-id"
export COGNITO_CLIENT_ID="your-cognito-client-id"
export COGNITO_CLIENT_SECRET="your-cognito-client-secret"
```

## デプロイメント

### ローカル開発環境

```bash
# AgentCore開発サーバーを起動
./start_agentcore_dev.sh

# 別ターミナルでテスト
source venv/bin/activate
agentcore invoke --dev "こんにちは"
```

### AWSへのデプロイ

```bash
# AWSにデプロイ
./deploy_to_aws.sh

# デプロイ状態確認
python check_deployment_status.py

# デプロイ済みエージェントのテスト
python manual_test_deployed_agent.py
```

### デプロイ後の確認

1. **エージェント状態確認**
   ```bash
   python check_deployment_status.py
   ```

2. **手動テスト実行**
   ```bash
   python manual_test_deployed_agent.py
   ```

3. **HealthMate UIからの呼び出し**
   - UIでCognito認証を実行
   - JWTトークンがエージェントに自動的に渡される
   - エージェントがユーザーIDを自動抽出して動作

## 🗑️ アンデプロイ（削除）

HealthCoachAIエージェントをAWSから完全に削除する場合：

### ワンコマンドアンデプロイ

```bash
# 全てのAWSリソースを削除
./destroy_from_aws.sh
```

このスクリプトは以下を実行します：

1. **AWS認証確認**: 認証情報とリージョンの確認
2. **現状確認**: デプロイされているリソースの表示
3. **ユーザー確認**: 削除の最終確認
4. **AgentCoreリソース削除**:
   - AgentCoreエージェント
   - ECRリポジトリ（全イメージ含む）
   - CodeBuildプロジェクト
   - IAMロール
   - S3アーティファクト
5. **メモリリソース削除**: AgentCore Memory
6. **ローカルクリーンアップ**: 設定ファイルとキャッシュの削除

### 手動アンデプロイ

個別にリソースを削除したい場合：

```bash
# 1. 仮想環境をアクティベート
source venv/bin/activate

# 2. AgentCoreリソースを削除
agentcore destroy --delete-ecr-repo

# 3. メモリリソースを削除
AWS_DEFAULT_REGION=us-west-2 agentcore memory list
AWS_DEFAULT_REGION=us-west-2 agentcore memory delete <memory-id>

# 4. ローカル設定ファイルを削除
rm -f .bedrock_agentcore.yaml
rm -rf .bedrock_agentcore
```

### アンデプロイ後の状態

- ✅ 全てのAWSリソースが削除される
- ✅ AWSコストが発生しなくなる
- ✅ ローカル設定ファイルがクリーンアップされる
- 🔄 `./deploy_to_aws.sh` で再デプロイ可能

### デプロイ要件

- Amazon Bedrock AgentCore Runtime環境
- MCP Gatewayスタックのデプロイ完了
- Cognitoユーザープールの設定完了
- 適切なIAMロールとポリシーの設定

## ライセンス

このプロジェクトはデモンストレーション目的です。必要に応じて確認・修正してください。

## サポート

質問や問題については、Amazon Bedrock AgentCoreのドキュメントを参照してください。