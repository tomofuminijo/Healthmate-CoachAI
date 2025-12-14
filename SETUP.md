# HealthCoachAI セットアップガイド

## クイックスタート

1. **クローンとセットアップ**
   ```bash
   git clone <repository-url>
   cd health-coach-ai
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **環境変数の設定**
   ```bash
   # 必須: CloudFormationスタック名
   export HEALTH_STACK_NAME="YOUR_CLOUDFORMATION_STACK_NAME"
   
   # オプション: AWSリージョン（デフォルト: us-west-2）
   export AWS_REGION="your-aws-region"
   
   # 代替: 手動設定（CloudFormationが利用できない場合）
   export HEALTH_GATEWAY_ID="your-gateway-id"
   export COGNITO_USER_POOL_ID="your-user-pool-id"
   export COGNITO_CLIENT_ID="your-client-id"
   export COGNITO_CLIENT_SECRET="your-client-secret"
   ```

3. **セットアップのテスト**
   ```bash
   # 基本テストの実行
   python test_health_coach_agent_simple.py
   
   # インタラクティブテスト
   python manual_test_agent.py
   ```

4. **AgentCore Runtimeへのデプロイ**
   ```bash
   python run_agent.py
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
フロントエンドUI → HealthCoachAIエージェント → MCPゲートウェイ → バックエンドサービス
     ↓                    ↓                        ↓                ↓
JWT認証          JWT デコード/検証            OAuth認証        健康データ
```

## サポート

問題が発生した場合：
1. トラブルシューティングセクションを確認
2. AWS CloudWatchログを確認
3. すべての設定要件を検証
4. manual_test_agent.pyでデバッグテストを実行