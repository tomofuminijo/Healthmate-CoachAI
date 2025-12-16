# Healthmate-CoachAI セットアップガイド

## 🚀 クイックスタート（推奨方法）

### 1. リポジトリのクローンと環境準備

```bash
git clone https://github.com/tomofuminijo/Healthmate-CoachAI.git
cd Healthmate-CoachAI
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. AWS認証の設定

```bash
# 方法1: AWS CLIで設定
aws configure

# 方法2: 環境変数で設定
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"
```

### 3. ワンコマンドデプロイ

```bash
# カスタムIAMロール自動作成 + デプロイ
./deploy_to_aws.sh
```

このスクリプトは以下を自動実行します：
- カスタムIAMロールの作成（必要な場合）
- 適切な権限ポリシーのアタッチ
- AgentCore Runtime設定
- エージェントのデプロイ

### 4. デプロイ後のテスト

```bash
# エージェント状態確認
agentcore status

# デプロイ済みエージェントのテスト
python3 manual_test_deployed_agent.py
```

## 🔧 詳細セットアップ

### カスタムIAMロール作成（手動）

```bash
# 必要な権限を持つカスタムIAMロールを作成
python3 create_custom_iam_role.py
```

作成されるIAMロール：
- **ロール名**: `Healthmate-CoachAI-AgentCore-Runtime-Role`
- **権限**: AgentCore Runtime基本権限 + CloudFormation読み取り + Cognito読み取り

### 環境変数設定（オプション）

```bash
# CloudFormationスタック名（デフォルト: Healthmate-HealthManagerStack）
export HEALTH_STACK_NAME="YOUR_STACK_NAME"

# AWSリージョン（デフォルト: us-west-2）
export AWS_REGION="your-aws-region"
```

## 設定要件

### CloudFormationスタック出力

CloudFormationスタックは以下の出力を提供する必要があります：

- `GatewayId`: MCP Gateway識別子
- `UserPoolId`: Cognito User Pool ID
- `UserPoolClientId`: Cognito Client ID

### AWS権限

実行ロールに以下の権限が必要です：

- CloudFormation: `describe-stacks`
- Cognito IDP: `describe-user-pool-client`
- Bedrock AgentCore: Gatewayアクセス

## トラブルシューティング

### よくある問題

1. **認証エラー**
   - Cognito設定の確認
   - JWTトークンの有効性チェック
   - 適切なIAM権限の確保

2. **MCP接続エラー**
   - Gateway IDとリージョンの確認
   - ネットワーク接続のチェック
   - 認証トークンの検証

3. **設定エラー**
   - CloudFormationスタックの存在確認
   - 環境変数のチェック
   - AWS認証情報の検証

### デバッグモード

デバッグログの有効化：
```bash
export PYTHONPATH=.
export LOG_LEVEL=DEBUG
python manual_test_agent.py
```

## アーキテクチャ概要

```
フロントエンドUI → Healthmate-CoachAIエージェント → MCPゲートウェイ → バックエンドサービス
     ↓                    ↓                        ↓                ↓
JWT認証          JWT デコード/検証            OAuth認証        健康データ
```

## サポート

問題が発生した場合：
1. トラブルシューティングセクションを確認
2. AWS CloudWatchログを確認
3. すべての設定要件を検証
4. manual_test_agent.pyでデバッグテストを実行