# Healthmate-CoachAI エージェント

Amazon Bedrock AgentCore Runtime上で動作する健康支援AIエージェントです。

## 概要

Healthmate-CoachAIは、ユーザーの健康目標達成を支援するAIエージェントです。以下の機能を提供します：

- 健康データの分析とパーソナライズされたアドバイス
- 健康目標の設定と進捗追跡
- 運動や食事に関する実践的な指導
- モチベーション維持のためのサポート

## 主な機能

### 🧠 AgentCore Memory統合
- **セッション継続性**: 会話の文脈を記憶し、継続的な対話を実現
- **AgentCoreMemorySessionManager**: 自動的なセッション管理
- **フォールバック機能**: メモリ統合失敗時の安全な動作保証
- **セッションID管理**: 33文字以上の要件に対応した自動生成

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
git clone https://github.com/tomofuminijo/Healthmate-CoachAI.git
cd Healthmate-CoachAI

# 2. 仮想環境を作成・アクティベート
python3 -m venv .venv
source .venv/bin/activate

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
cd healthmate-coach-ai

# 仮想環境の作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt
```

### エージェントの実行

```bash
# 直接実行
python healthmate_coach_ai/agent.py

# ランナースクリプトを使用
python run_agent.py
```

## 開発・テスト

### 手動テスト

#### ローカル開発テスト
```bash
# インタラクティブテストプログラム
python manual_test_agent.py
```

#### デプロイ済みエージェントテスト
```bash
# デプロイ済みエージェントの手動テスト
python manual_test_deployed_agent.py
```

機能：
- **セッション継続性テスト**: AgentCore Memoryの動作確認
- **マルチライン入力対応**: 複雑なクエリの入力
- **セッション維持**: 会話の文脈を保持
- **リアルタイムJWT認証**: 自動認証とユーザー識別
- **DynamoDB確認用ユーザーID表示**: データベース確認支援
- **ストリーミング対応**: リアルタイム応答表示

### 自動テスト

```bash
# 基本機能テスト
python test_health_coach_agent_simple.py

# 包括的統合テスト
python test_health_coach_agent.py

# MCPスキーマ発見テスト
python test_mcp_schema_discovery.py
```

### セッション継続性テスト

AgentCore Memory統合の動作確認：

```bash
# デプロイ済みエージェントでセッション継続性をテスト
python manual_test_deployed_agent.py
# コマンド: memory_test
```

テスト内容：
1. **名前の記憶**: 「私の名前はジョニーです」→「私の名前は何ですか？」
2. **会話の文脈継続**: 健康目標設定→進捗確認方法の質問
3. **セッションID管理**: 同一セッションでの会話継続性確認

## アーキテクチャ

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   フロントエンド │    │ Healthmate-CoachAI │    │   MCPサーバー   │
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
healthmate_coach_ai/
├── healthmate_coach_ai/
│   ├── __init__.py
│   └── agent.py                    # メインエージェント実装（AgentCore Memory統合）
├── manual_test_agent.py           # ローカル開発テストプログラム
├── manual_test_deployed_agent.py  # デプロイ済みエージェントテストプログラム
├── test_config_helper.py          # テスト用設定ヘルパー
├── test_health_coach_agent.py     # 包括的統合テスト
├── test_health_coach_agent_simple.py  # 基本機能テスト
├── test_mcp_schema_discovery.py   # MCPスキーマ発見テスト
├── run_agent.py                   # エージェント実行スクリプト
├── deploy_to_aws.sh               # AWSデプロイスクリプト
├── destroy_from_aws.sh            # AWSアンデプロイスクリプト
├── create_custom_iam_role.py      # カスタムIAMロール作成
├── check_deployment_status.py     # デプロイ状態確認
├── .bedrock_agentcore.yaml        # AgentCore設定ファイル
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

## 🧠 AgentCore Memory統合

### セッション継続性

Healthmate-CoachAIは**AgentCore Memory**を統合し、会話の文脈を記憶します：

- **自動セッション管理**: `AgentCoreMemorySessionManager`による透明なセッション処理
- **会話の継続性**: 前回の会話内容を参照した一貫性のあるアドバイス
- **フォールバック機能**: メモリ統合失敗時も安全に動作
- **セッションID要件**: 33文字以上のセッションIDを自動生成・管理

### メモリ設定

```yaml
# .bedrock_agentcore.yaml
agents:
  healthmate_coach_ai:
    bedrock_agentcore:
      memory:
        memory_id: "healthmate_coach_ai_mem-yxqD6w75pO"
        enabled: true
```

### セッション継続性テスト

```bash
# デプロイ済みエージェントでテスト
python manual_test_deployed_agent.py
# コマンド: memory_test

# 期待される動作:
# 1. 「私の名前はジョニーです」
# 2. 「私の名前は何ですか？」→ "ジョニー"と回答
# 3. 健康目標設定 → 前の目標を参照した進捗確認
```

## 🗑️ アンデプロイ（削除）

Healthmate-CoachAIエージェントをAWSから完全に削除する場合：

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
5. **AgentCore Memoryリソース削除**: セッション管理メモリ
6. **ローカルクリーンアップ**: 設定ファイルとキャッシュの削除

### 手動アンデプロイ

個別にリソースを削除したい場合：

```bash
# 1. 仮想環境をアクティベート
source .venv/bin/activate

# 2. AgentCoreリソースを削除
agentcore destroy --delete-ecr-repo

# 3. AgentCore Memoryリソースを削除
AWS_DEFAULT_REGION=us-west-2 agentcore memory list
AWS_DEFAULT_REGION=us-west-2 agentcore memory delete healthmate_coach_ai_mem-yxqD6w75pO

# 4. ローカル設定ファイルを削除
rm -f .bedrock_agentcore.yaml
rm -rf .bedrock_agentcore
```

### アンデプロイ後の状態

- ✅ 全てのAWSリソースが削除される
- ✅ AgentCore Memoryリソースが削除される
- ✅ AWSコストが発生しなくなる
- ✅ ローカル設定ファイルがクリーンアップされる
- 🔄 `./deploy_to_aws.sh` で再デプロイ可能（メモリ統合含む）

### デプロイ要件

- Amazon Bedrock AgentCore Runtime環境
- MCP Gatewayスタックのデプロイ完了
- Cognitoユーザープールの設定完了
- 適切なIAMロールとポリシーの設定

## ライセンス

このプロジェクトはデモンストレーション目的です。必要に応じて確認・修正してください。

## サポート

質問や問題については、Amazon Bedrock AgentCoreのドキュメントを参照してください。