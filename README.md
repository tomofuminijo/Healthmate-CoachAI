# Healthmate-CoachAI エージェント

Amazon Bedrock AgentCore Runtime上で動作する健康支援AIエージェントです。

## 概要

Healthmate-CoachAIは、ユーザーの健康目標達成を支援するAIエージェントです。以下の機能を提供します：

- 健康データの分析とパーソナライズされたアドバイス
- 健康目標の設定と進捗追跤
- 運動や食事に関する実践的な指導
- モチベーション維持のためのサポート

## 主な機能

### 🔐 JWT認証統合（2024年12月更新）
- **JWT認証**: Cognito JWTトークンによるユーザー認証
- **認証の分離**: JWT（ユーザー識別）とM2M（サービス認証）の適切な分離
- **Discovery URL**: Cognito OpenID Connect Discovery URLによる自動設定
- **Client ID検証**: `allowedClients`配列による厳密なクライアント検証

### 🧠 AgentCore Memory統合
- **セッション継続性**: 会話の文脈を記憶し、継続的な対話を実現
- **AgentCoreMemorySessionManager**: 自動的なセッション管理
- **フォールバック機能**: メモリ統合失敗時の安全な動作保証
- **セッションID管理**: 33文字以上の要件に対応した自動生成

### 🔗 MCP統合
- **HealthManagerMCPサーバーとの連携**: 17個のツールへのアクセス
- **Activity Management**: 6ツール（行動記録・管理）
- **Health Goal Management**: 4ツール（健康目標設定・管理）
- **Health Policy Management**: 4ツール（健康ルール設定）
- **User Management**: 3ツール（ユーザー情報管理）

### 🔐 JWT認証処理
- **ユーザー識別専用**: JWTトークンからユーザーIDを自動抽出
- **Cognito統合**: Amazon Cognito認証との完全統合
- **セキュアな処理**: 署名検証なしのペイロード抽出（内部処理用）

### 🕒 時間認識機能
- **現在日時の自動取得**: ユーザーのタイムゾーンに基づく時刻計算
- **時間帯対応アドバイス**: 朝・昼・夜に応じた適切なアドバイス
- **日付・時刻考慮**: 健康管理における時間的文脈の活用

### ☁️ 動的設定管理
- **CloudFormation統合**: スタック出力からの設定自動取得
- **環境変数サポート**: 柔軟な設定管理
- **フォールバック機能**: 設定取得失敗時の安全な動作

## 🚀 クイックスタート

### 前提条件

- Python 3.12+
- AWS CLI設定済み
- Amazon Bedrock AgentCore Runtime環境
- Healthmate-Core サービス（Cognito認証基盤）のデプロイ完了
- Healthmate-HealthManager サービス（MCP Gateway）のデプロイ完了

### 1. 環境準備

```bash
# リポジトリのクローンと移動
git clone <repository-url>
cd Healthmate-CoachAI

# 仮想環境の作成とアクティベート
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 開発用依存関係のインストール
pip install -r requirements-dev.txt

# Runtime用依存関係は agent/requirements.txt に分離されています
# （デプロイ時に自動的に使用されます）
```

### 2. AWS認証の設定

```bash
# 方法1: AWS CLIで設定
aws configure

# 方法2: 環境変数で設定
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"

# AIモデル設定（オプション）
export HEALTHMATE_AI_MODEL="global.anthropic.claude-sonnet-4-5-20250929-v1:0"
```

### 3. ワンコマンドデプロイ

```bash
# JWT認証設定 + カスタムIAMロール自動作成 + デプロイ
./deploy_to_aws.sh

# 異なるAIモデルを使用する場合
export HEALTHMATE_AI_MODEL="global.anthropic.claude-3-5-sonnet-20241022-v2:0"
./deploy_to_aws.sh
```

このスクリプトは以下を自動実行します：
- カスタムIAMロールの作成（必要な場合）
- Cognito設定の自動取得（CloudFormationから）
- JWT認証設定（Discovery URL + allowedClients）
- AgentCore Runtime設定（Runtime最適化対応）
- エージェントのデプロイ（`agent/`ディレクトリのみをコンテナ化）
- M2M認証プロバイダーの設定

### 4. デプロイ後のテスト

```bash
# エージェント状態確認
agentcore status

# デプロイ済みエージェントのテスト（JWT認証対応）
python manual_test_deployed_agent.py
```

## 🔧 詳細設定

### JWT認証設定（2024年12月更新）

AgentCore RuntimeはCognito JWT認証を使用します：

#### 認証設定の自動構成

デプロイスクリプトが以下を自動的に設定します：

```bash
# Cognito設定の自動取得（CloudFormationから）
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name Healthmate-CoreStack \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name Healthmate-CoreStack \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text)

# JWT Discovery URLの構築
JWT_DISCOVERY_URL="https://cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration"

# AgentCore設定への適用
AUTHORIZER_CONFIG="{\"customJWTAuthorizer\":{\"discoveryUrl\":\"${JWT_DISCOVERY_URL}\",\"allowedClients\":[\"${USER_POOL_CLIENT_ID}\"]}}"
```

#### JWT認証の仕組み

```
┌─────────────────┐    JWT Access Token    ┌──────────────────┐
│   HealthmateUI  │ ──────────────────────▶│ AgentCore Runtime│
│                 │                         │                  │
│ 1. Cognito認証  │                         │ 2. JWT検証       │
│ 2. Access Token │                         │    - Discovery   │
│    取得         │                         │    - Client ID   │
│                 │                         │    - Signature   │
└─────────────────┘                         └──────────────────┘
                                                     │
                                                     ▼
                                            ┌──────────────────┐
                                            │ Healthmate-CoachAI│
                                            │                  │
                                            │ 3. User ID抽出   │
                                            │    (JWT sub)     │
                                            │ 4. M2M認証       │
                                            │    (Gateway用)   │
                                            └──────────────────┘
```

#### 重要な注意事項

**Access Token vs ID Token**:
- ✅ **Access Token使用**: `client_id`クレームを含む（AgentCore検証に必要）
- ❌ **ID Token使用不可**: `aud`クレームのみ（検証エラー）

**JWT認証設定**:
```yaml
# .bedrock_agentcore.yaml（自動生成）
agents:
  healthmate_coach_ai:
    bedrock_agentcore:
      authorizer_config:
        customJWTAuthorizer:
          discoveryUrl: "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_xxxxx/.well-known/openid-configuration"
          allowedClients:
            - "your-cognito-client-id"
      request_header_allowlist:
        - "Authorization"
```

### M2M認証設定

M2M認証は引き続きHealthManagerMCP Gatewayへのアクセスに使用されます：

#### 必須環境変数
```bash
# M2M認証プロバイダー名（デプロイ時に自動設定）
export AGENTCORE_PROVIDER_NAME="healthmate-coach-ai-provider"

# HealthManagerMCP Gateway ID（デプロイ時に自動設定）
export HEALTHMANAGER_GATEWAY_ID="gateway-id-from-cloudformation"

# AgentCore Memory ID（デプロイ時に自動設定）
export BEDROCK_AGENTCORE_MEMORY_ID="healthmate_coach_ai_mem-xxxxx"
```

#### IAM権限要件

カスタムIAMロールには以下の権限が必要です：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:GetWorkloadAccessToken",
        "bedrock-agentcore:GetWorkloadAccessTokenForJWT", 
        "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "*"
    }
  ]
}
```

### CloudFormationスタック出力要件

以下のスタック出力が必要です：

#### Healthmate-Core スタック
- `UserPoolId`: Cognito User Pool ID
- `UserPoolClientId`: Cognito Client ID

#### Healthmate-HealthManager スタック  
- `GatewayId`: MCP Gateway識別子

### 手動IAMロール作成（詳細制御が必要な場合）

```bash
# M2M認証対応のカスタムIAMロールを作成
python create_custom_iam_role.py
```

作成されるIAMロール：
- **ロール名**: `Healthmate-CoachAI-AgentCore-Runtime-Role`
- **権限**: AgentCore Runtime基本権限 + M2M認証権限 + CloudFormation読み取り

### 環境変数設定（オプション）

```bash
# CloudFormationスタック名のカスタマイズ
export CORE_STACK_NAME="Custom-Healthmate-CoreStack"
export HEALTH_STACK_NAME="Custom-Healthmate-HealthManagerStack"

# AWSリージョンのカスタマイズ（デフォルト: us-west-2）
export AWS_REGION="your-aws-region"

# AIモデルのカスタマイズ（デフォルト: Claude Sonnet 4.5）
export HEALTHMATE_AI_MODEL="global.anthropic.claude-sonnet-4-5-20250929-v1:0"

# 利用可能なモデル例:
# export HEALTHMATE_AI_MODEL="global.anthropic.claude-3-5-sonnet-20241022-v2:0"
# export HEALTHMATE_AI_MODEL="global.anthropic.claude-3-5-haiku-20241022-v1:0"
```

## 🧪 開発・テスト

### デプロイ済みエージェントテスト（推奨）

JWT認証統合後のメインテストツール：

```bash
# デプロイ済みエージェントの包括的テスト
python manual_test_deployed_agent.py
```

**主な機能**:
- ✅ **JWT認証テスト**: Cognito Access Tokenによる認証確認
- ✅ **17個のMCPツール確認**: HealthManagerMCPサービスとの連携テスト
- ✅ **セッション継続性テスト**: AgentCore Memoryの動作確認
- ✅ **M2M認証テスト**: Gateway接続の自動認証確認
- ✅ **マルチライン入力対応**: 複雑なクエリの入力
- ✅ **ストリーミング対応**: リアルタイム応答表示
- ✅ **DynamoDB確認用ユーザーID表示**: データベース確認支援

**利用可能なコマンド**:
```bash
help         # ヘルプ表示
status       # セッション状態とユーザーID表示
memory_test  # セッション継続性の自動テスト
restart      # 認証の再実行
quit/exit    # プログラム終了
```

### セッション継続性テスト

AgentCore Memory統合の動作確認：

```bash
python manual_test_deployed_agent.py
# コマンド入力: memory_test
```

**自動テスト内容**:
1. **名前の記憶**: 「私の名前はジョニーです」→「私の名前は何ですか？」
2. **会話の文脈継続**: 健康目標設定→進捗確認方法の質問
3. **セッションID管理**: 同一セッションでの会話継続性確認

### ローカル開発テスト（レガシー）

```bash
# ローカル環境でのテスト（Client Secret使用）
python manual_test_agent.py
```

**注意**: このテストはClient Secretを使用する古い認証方式です。JWT認証統合後は`manual_test_deployed_agent.py`の使用を推奨します。

### 自動テスト

```bash
# AgentCore Memory統合テスト
python test_memory_integration.py

# 設定ヘルパーテスト
python test_config_helper.py
```

## 📋 API仕様

### エンドポイント情報

**AgentCore Runtime エンドポイント**:
```
https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{url_encoded_agent_arn}/invocations?qualifier=DEFAULT
```

**認証ヘッダー**:
```http
Authorization: Bearer {cognito_access_token}
Content-Type: application/json
X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: {session_id}
```

### クライアントからの呼び出し方法

#### 1. Python（requests）での呼び出し

```python
import requests
import urllib.parse
import json

# 設定
region = "us-west-2"
agent_arn = "arn:aws:bedrock-agentcore:us-west-2:123456789012:agent/healthmate_coach_ai"
access_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."  # Cognito Access Token
session_id = "healthmate-chat-1234567890-abcdef"

# エンドポイントURL構築
escaped_agent_arn = urllib.parse.quote(agent_arn, safe='')
endpoint_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

# ペイロード構築
payload = {
    "prompt": "こんにちは！今日の健康状態はいかがですか？",
    "sessionState": {
        "sessionAttributes": {
            "session_id": session_id,
            "timezone": "Asia/Tokyo",
            "language": "ja"
        }
    }
}

# リクエスト送信
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id
}

response = requests.post(endpoint_url, headers=headers, json=payload, stream=True)

# ストリーミングレスポンス処理
for line in response.iter_lines(decode_unicode=True):
    if line and line.startswith('data: '):
        try:
            data_json = line[6:]  # "data: " を除去
            if data_json.strip():
                event_data = json.loads(data_json)
                # contentBlockDelta イベントからテキストを抽出
                if 'event' in event_data and 'contentBlockDelta' in event_data['event']:
                    delta = event_data['event']['contentBlockDelta'].get('delta', {})
                    if 'text' in delta:
                        print(delta['text'], end='', flush=True)
        except json.JSONDecodeError:
            continue
```

#### 2. JavaScript（fetch）での呼び出し

```javascript
// 設定
const region = "us-west-2";
const agentArn = "arn:aws:bedrock-agentcore:us-west-2:123456789012:agent/healthmate_coach_ai";
const accessToken = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."; // Cognito Access Token
const sessionId = "healthmate-chat-1234567890-abcdef";

// エンドポイントURL構築
const escapedAgentArn = encodeURIComponent(agentArn);
const endpointUrl = `https://bedrock-agentcore.${region}.amazonaws.com/runtimes/${escapedAgentArn}/invocations?qualifier=DEFAULT`;

// ペイロード構築
const payload = {
    prompt: "こんにちは！今日の健康状態はいかがですか？",
    sessionState: {
        sessionAttributes: {
            session_id: sessionId,
            timezone: "Asia/Tokyo",
            language: "ja"
        }
    }
};

// リクエスト送信
const response = await fetch(endpointUrl, {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': sessionId
    },
    body: JSON.stringify(payload)
});

// ストリーミングレスポンス処理
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            try {
                const dataJson = line.substring(6); // "data: " を除去
                if (dataJson.trim()) {
                    const eventData = JSON.parse(dataJson);
                    // contentBlockDelta イベントからテキストを抽出
                    if (eventData.event && eventData.event.contentBlockDelta) {
                        const delta = eventData.event.contentBlockDelta.delta;
                        if (delta && delta.text) {
                            console.log(delta.text);
                        }
                    }
                }
            } catch (e) {
                // JSON解析エラーは無視
            }
        }
    }
}
```

#### 3. FastAPI（HealthmateUI）での呼び出し

```python
import httpx
import urllib.parse
from fastapi import HTTPException

class HealthCoachClient:
    def __init__(self, region: str, agent_arn: str):
        self.region = region
        self.agent_arn = agent_arn
        self.endpoint_url = self._build_endpoint_url()
    
    def _build_endpoint_url(self) -> str:
        escaped_arn = urllib.parse.quote(self.agent_arn, safe='')
        return f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"
    
    async def send_message(self, 
                          message: str, 
                          session_id: str, 
                          access_token: str,
                          timezone: str = "Asia/Tokyo",
                          language: str = "ja") -> str:
        """HealthCoachAIにメッセージを送信"""
        
        payload = {
            "prompt": message,
            "sessionState": {
                "sessionAttributes": {
                    "session_id": session_id,
                    "timezone": timezone,
                    "language": language
                }
            }
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.endpoint_url,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                # ストリーミングレスポンスの処理
                response_text = ""
                async for line in response.aiter_lines():
                    if line.startswith('data: '):
                        try:
                            data_json = line[6:]  # "data: " を除去
                            if data_json.strip():
                                event_data = json.loads(data_json)
                                if 'event' in event_data and 'contentBlockDelta' in event_data['event']:
                                    delta = event_data['event']['contentBlockDelta'].get('delta', {})
                                    if 'text' in delta:
                                        response_text += delta['text']
                        except json.JSONDecodeError:
                            continue
                
                return response_text
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise HTTPException(status_code=401, detail="JWT認証エラー: アクセストークンが無効です")
                elif e.response.status_code == 403:
                    raise HTTPException(status_code=403, detail="認可エラー: 必要な権限がありません")
                else:
                    raise HTTPException(status_code=e.response.status_code, detail=f"AgentCore Runtime エラー: {e}")

# 使用例
coach_client = HealthCoachClient(
    region="us-west-2",
    agent_arn="arn:aws:bedrock-agentcore:us-west-2:123456789012:agent/healthmate_coach_ai"
)

response = await coach_client.send_message(
    message="今日の運動記録を確認してください",
    session_id="healthmate-chat-1234567890-abcdef",
    access_token=cognito_access_token
)
```

### 認証フロー詳細

#### 1. Cognito認証（クライアント側）

```python
import boto3
from botocore.exceptions import ClientError

def authenticate_user(username: str, password: str, user_pool_id: str, client_id: str) -> str:
    """Cognito認証を実行してAccess Tokenを取得"""
    
    cognito_client = boto3.client('cognito-idp', region_name='us-west-2')
    
    try:
        # USER_PASSWORD_AUTH フローで認証
        response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        # Access Tokenを返す（ID Tokenではない）
        return response['AuthenticationResult']['AccessToken']
        
    except ClientError as e:
        raise Exception(f"Cognito認証エラー: {e}")

# 使用例
access_token = authenticate_user(
    username="user@example.com",
    password="password123",
    user_pool_id="us-west-2_xxxxxxxxx",
    client_id="your-cognito-client-id"
)
```

#### 2. セッション管理

```python
import uuid

def generate_session_id() -> str:
    """AgentCore Memory要件に準拠したセッションIDを生成（33文字以上）"""
    return f"healthmate-chat-{uuid.uuid4().hex}"

def validate_session_id(session_id: str) -> bool:
    """セッションIDの妥当性を検証"""
    return len(session_id) >= 33

# 使用例
session_id = generate_session_id()
print(f"生成されたセッションID: {session_id}")  # healthmate-chat-1234567890abcdef1234567890abcdef
print(f"文字数: {len(session_id)}")  # 47文字（33文字以上の要件を満たす）
```

### ペイロード構造

HealthmateUI サービスから送信される最適化されたペイロード：

```json
{
  "prompt": "ユーザーからのメッセージ",
  "sessionState": {
    "sessionAttributes": {
      "session_id": "healthmate-chat-1234567890-abcdef",
      "timezone": "Asia/Tokyo",
      "language": "ja"
    }
  }
}
```

**注意**: JWT トークンは Authorization ヘッダーで送信されます：
```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

### ペイロード要素の説明

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `prompt` | ✅ | ユーザーからのメッセージ |
| `sessionState.sessionAttributes.session_id` | ✅ | セッション継続性のためのID（33文字以上） |
| `sessionState.sessionAttributes.timezone` | ⚪ | ユーザーのタイムゾーン（デフォルト: "Asia/Tokyo"） |
| `sessionState.sessionAttributes.language` | ⚪ | ユーザーの言語設定（デフォルト: "ja"） |

### 認証ヘッダー

| ヘッダー | 必須 | 説明 |
|---------|------|------|
| `Authorization` | ✅ | Cognito JWT Access Token（Bearer形式、user_id抽出用） |

### 認証アーキテクチャ

JWT認証統合後の認証フロー：

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   HealthmateUI  │    │ AgentCore Runtime│    │ Healthmate-CoachAI│
│                 │    │                  │    │                 │
│ 1. Cognito認証  │───▶│ 2. JWT検証       │───▶│ 3. JWT処理      │
│ 2. Access Token │    │    - Discovery   │    │    - User ID    │
│    取得         │    │    - Client ID   │    │    - 抽出       │
│                 │    │    - Signature   │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │ HealthManagerMCP│
                                               │                 │
                                               │ 4. M2M認証      │
                                               │    (Service)    │
                                               │ 5. Health Data  │
                                               │    Operations   │
                                               └─────────────────┘
```

**認証の分離**:
- **JWT認証**: ユーザー識別専用（UI → AgentCore Runtime → Agent）
- **M2M認証**: サービス認証専用（Agent → MCP Gateway）

**JWT検証プロセス**:
1. **Discovery URL取得**: Cognito OpenID Connect設定を自動取得
2. **公開鍵取得**: JWT署名検証用の公開鍵を取得
3. **Client ID検証**: `allowedClients`配列でクライアントIDを検証
4. **署名検証**: JWT署名の妥当性を検証
5. **有効期限確認**: トークンの有効期限を確認

### 自動処理される情報

- **user_id**: JWT トークンの `sub` フィールドから自動抽出
- **現在日時**: ユーザーのタイムゾーンに基づいて自動計算
- **セッション管理**: AgentCore Memory による自動セッション継続
- **M2M認証**: `@requires_access_token`デコレータによる自動認証

## 🏗️ アーキテクチャ

### システム全体図

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   HealthmateUI  │    │ Healthmate-CoachAI │    │ HealthManagerMCP│
│   (Frontend)    │───▶│   (AI Agent)     │───▶│   (Backend)     │
│                 │    │                  │    │                 │
│ • JWT Auth      │    │ • JWT Decode     │    │ • User Mgmt     │
│ • User Session  │    │ • M2M Auth       │    │ • Health Goals  │
│ • UI State      │    │ • Time Aware     │    │ • Activities    │
│                 │    │ • Memory Mgmt    │    │ • Policies      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   AWS Services   │
                       │                  │
                       │ • Cognito        │
                       │ • DynamoDB       │
                       │ • CloudFormation │
                       │ • AgentCore      │
                       └──────────────────┘
```

### 認証フロー

```
HealthmateUI ──JWT Token──▶ CoachAI ──M2M Auth──▶ HealthManagerMCP
    │                          │                        │
    ▼                          ▼                        ▼
User Identity            Service Identity         Health Data
(Cognito sub)           (@requires_access_token)   (DynamoDB)
```

### データフロー

```
1. User Input (HealthmateUI)
   ↓
2. JWT + Session Info (Agent Payload)
   ↓  
3. User ID Extraction (JWT sub field)
   ↓
4. M2M Authentication (Auto via decorator)
   ↓
5. MCP Tool Calls (17 available tools)
   ↓
6. Health Data Operations (DynamoDB)
   ↓
7. AI Response Generation (Strands Agent)
   ↓
8. Session Memory Update (AgentCore Memory)
   ↓
9. Streaming Response (Back to UI)
```

## 📁 プロジェクト構成

```
Healthmate-CoachAI/
├── agent/                              # Runtime専用ディレクトリ（Dockerイメージに含まれる）
│   ├── healthmate_coach_ai/
│   │   ├── __init__.py
│   │   ├── agent.py                    # メインエージェント実装（M2M認証+Memory統合）
│   │   └── m2m_auth_config.py          # M2M認証設定
│   ├── requirements.txt                # Runtime専用依存関係（最小構成）
│   └── .dockerignore                   # Docker除外設定
├── manual_test_deployed_agent.py       # デプロイ済みエージェントテスト（推奨）
├── test_config_helper.py               # 設定ヘルパー（CloudFormation統合）
├── manual_test_agent.py                # ローカル開発テスト（レガシー）
├── create_custom_iam_role.py           # M2M認証対応IAMロール作成
├── check_deployment_status.py          # デプロイ状態確認
├── deploy_to_aws.sh                    # AWSデプロイスクリプト（M2M認証対応）
├── destroy_from_aws.sh                 # AWSアンデプロイスクリプト
├── .bedrock_agentcore.yaml             # AgentCore設定ファイル（自動生成）
├── agentcore-trust-policy.json         # IAM信頼ポリシー
├── bedrock-agentcore-runtime-policy.json # M2M認証対応ランタイムポリシー
├── requirements-dev.txt                # 開発・テスト用依存関係
├── README.md                           # このファイル
└── .gitignore                          # Git除外設定
```

### ディレクトリ構造の最適化（2024年12月更新）

#### 🐳 Runtime専用ディレクトリ (`agent/`)
- **目的**: Dockerイメージに含まれるファイルのみを格納
- **効果**: コンテナイメージサイズの大幅削減
- **内容**: 
  - エージェント実装ファイル
  - Runtime専用依存関係（6個のパッケージのみ）
  - Docker設定ファイル

#### 📦 依存関係の分離
- **`agent/requirements.txt`**: Runtime環境用（6個の最小構成）
  ```
  strands-agents>=0.1.0
  bedrock-agentcore[strands-agents]>=0.1.0
  httpx>=0.24.0
  pytz>=2023.3
  fastapi>=0.104.0
  boto3>=1.34.0
  ```
- **`requirements-dev.txt`**: 開発・テスト用（10個の追加パッケージ）
  ```
  bedrock-agentcore-starter-toolkit>=0.1.0
  PyYAML>=6.0
  pytest>=7.4.0
  pytest-asyncio>=0.21.0
  hypothesis>=6.88.0
  mcp>=1.0.0
  black>=23.0.0
  flake8>=6.0.0
  mypy>=1.5.0
  ```

#### 🚀 デプロイ設定の更新
`deploy_to_aws.sh`内で以下の引数が追加されました：
```bash
agentcore configure \
    --entrypoint agent/healthmate_coach_ai/agent.py \
    --requirements-file agent/requirements.txt \
    # ... その他の設定
```

### 主要ファイルの説明

#### 🚀 デプロイ・設定
- **`deploy_to_aws.sh`**: JWT認証対応のワンコマンドデプロイ（Runtime最適化対応）
- **`create_custom_iam_role.py`**: M2M認証に必要な権限を含むIAMロール作成
- **`bedrock-agentcore-runtime-policy.json`**: M2M認証権限を含むポリシー定義

#### 🧪 テスト・開発
- **`manual_test_deployed_agent.py`**: JWT認証対応のメインテストツール
- **`test_config_helper.py`**: CloudFormation統合テスト
- **`requirements-dev.txt`**: 開発環境専用の依存関係

#### 🤖 エージェント実装（Runtime専用）
- **`agent/healthmate_coach_ai/agent.py`**: 
  - JWT処理（ユーザー識別専用）
  - M2M認証統合（`@requires_access_token`）
  - AgentCore Memory統合
  - 17個のMCPツール連携
- **`agent/requirements.txt`**: Runtime環境で必要な最小限の依存関係

## 🔒 セキュリティ

### JWT認証セキュリティ

- **Discovery URL検証**: Cognito OpenID Connect設定による自動検証
- **Client ID検証**: `allowedClients`配列による厳密なクライアント制限
- **署名検証**: JWT署名の暗号学的検証
- **有効期限確認**: トークンの時間ベース検証
- **Access Token使用**: `client_id`クレーム含有（ID Tokenは使用不可）

### M2M認証セキュリティ

- **自動認証**: `@requires_access_token`デコレータによる透明な認証
- **認証分離**: JWT（ユーザー識別）とM2M（サービス認証）の適切な分離
- **トークン管理**: AgentCore Runtimeによる安全なトークン管理
- **スコープ制限**: `HealthManager/HealthTarget:invoke`スコープによる権限制限

### データ保護

- **認証情報のハードコードなし**: 環境変数とCloudFormationによる動的設定
- **JWT処理**: 署名検証なしのペイロード抽出（内部処理専用）
- **ログ保護**: JWTトークンや機密情報のログ出力防止
- **IAMロールベースアクセス**: 最小権限の原則に基づく権限設定

### 通信セキュリティ

- **HTTPS通信**: 全てのAPI通信でHTTPS使用
- **トークン暗号化**: AWS Secrets Managerによるクライアントシークレット管理
- **セッション管理**: AgentCore Memoryによる安全なセッション継続

## ⚙️ 設定要件

### CloudFormationスタック出力

エージェントは以下のCloudFormationスタック出力を期待します：

#### Healthmate-Core スタック
- `UserPoolId`: Cognito User Pool ID
- `UserPoolClientId`: Cognito Client ID

#### Healthmate-HealthManager スタック
- `GatewayId`: MCP Gateway識別子

### 環境変数（自動設定）

デプロイ時に以下の環境変数が自動設定されます：

```bash
# M2M認証設定（deploy_to_aws.shで自動設定）
AGENTCORE_PROVIDER_NAME="healthmate-coach-ai-provider"

# MCP Gateway設定（CloudFormationから自動取得）
HEALTHMANAGER_GATEWAY_ID="gateway-id-from-stack"

# AgentCore Memory設定（デプロイ時に自動設定）
BEDROCK_AGENTCORE_MEMORY_ID="healthmate_coach_ai_mem-xxxxx"

# AWS設定
AWS_REGION="us-west-2"
```

### 手動設定（CloudFormationが利用できない場合）

```bash
# 必須設定
export AGENTCORE_PROVIDER_NAME="your-provider-name"
export HEALTHMANAGER_GATEWAY_ID="your-mcp-gateway-id"
export BEDROCK_AGENTCORE_MEMORY_ID="your-memory-id"

# オプション設定
export CORE_STACK_NAME="your-core-stack-name"
export HEALTH_STACK_NAME="your-healthmanager-stack-name"
export AWS_REGION="your-aws-region"
```

## 🚀 デプロイメント

### AWSへのデプロイ

```bash
# JWT認証対応のワンコマンドデプロイ
./deploy_to_aws.sh
```

**デプロイ内容**:
- カスタムIAMロール作成（M2M認証権限含む）
- Cognito設定の自動取得（CloudFormationから）
- JWT認証設定（Discovery URL + allowedClients）
- AgentCore Runtime設定
- M2M認証プロバイダー設定
- AgentCore Memory設定
- エージェントコンテナデプロイ

### デプロイ後の確認

```bash
# 1. エージェント状態確認
agentcore status

# 2. デプロイ状態詳細確認
python check_deployment_status.py

# 3. M2M認証テスト
python manual_test_deployed_agent.py
```

**期待される結果**:
- ✅ Agent Runtime ARNが表示される
- ✅ JWT認証が正常に動作する
- ✅ 17個のMCPツールにアクセス可能
- ✅ セッション継続性が動作する
- ✅ M2M認証が自動で動作する

### HealthmateUIからの呼び出し

JWT認証統合後の呼び出しフロー：

1. **UIでCognito認証を実行**
   ```python
   # Cognito認証でAccess Tokenを取得
   access_token = cognito_client.initiate_auth(...)['AuthenticationResult']['AccessToken']
   ```

2. **AgentCore RuntimeエンドポイントにHTTPSリクエスト**
   ```python
   headers = {
       "Authorization": f"Bearer {access_token}",
       "Content-Type": "application/json",
       "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id
   }
   
   payload = {
       "prompt": user_message,
       "sessionState": {
           "sessionAttributes": {
               "session_id": session_id,
               "jwt_token": access_token,
               "timezone": "Asia/Tokyo",
               "language": "ja"
           }
       }
   }
   ```

3. **AgentCore RuntimeがJWT検証を実行**
   - Discovery URLから公開鍵を取得
   - Client IDを`allowedClients`で検証
   - JWT署名と有効期限を検証

4. **エージェントがユーザーIDを自動抽出して動作**
   ```python
   # agent.py内で自動実行
   user_id = jwt_payload.get('sub')  # JWTのsubクレームからユーザーID抽出
   ```

5. **M2M認証で HealthManagerMCPサービスにアクセス**
   ```python
   # @requires_access_tokenデコレータが自動実行
   mcp_access_token = get_m2m_token()  # M2M認証トークン取得
   ```

## 🧠 AgentCore Memory統合

### セッション継続性

Healthmate-CoachAIは**AgentCore Memory**を統合し、会話の文脈を記憶します：

- **自動セッション管理**: `AgentCoreMemorySessionManager`による透明なセッション処理
- **会話の継続性**: 前回の会話内容を参照した一貫性のあるアドバイス
- **フォールバック機能**: メモリ統合失敗時も安全に動作
- **セッションID要件**: 33文字以上のセッションIDを自動生成・管理

### メモリ設定

```yaml
# .bedrock_agentcore.yaml（自動生成）
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
# コマンド入力: memory_test
```

**期待される動作**:
1. 「私の名前はジョニーです」→ AIが名前を記憶
2. 「私の名前は何ですか？」→ "ジョニー"と正確に回答
3. 健康目標設定 → 前の目標を参照した進捗確認
4. セッション間での情報継続

## 🗑️ アンデプロイ（削除）

### ワンコマンドアンデプロイ

```bash
# 全てのAWSリソースを削除
./destroy_from_aws.sh
```

**削除内容**:
1. **AWS認証確認**: 認証情報とリージョンの確認
2. **現状確認**: デプロイされているリソースの表示
3. **ユーザー確認**: 削除の最終確認
4. **AgentCoreリソース削除**:
   - AgentCoreエージェント
   - ECRリポジトリ（全イメージ含む）
   - CodeBuildプロジェクト
   - カスタムIAMロール（M2M認証権限含む）
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
agentcore memory list
agentcore memory delete healthmate_coach_ai_mem-yxqD6w75pO

# 4. ローカル設定ファイルを削除
rm -f .bedrock_agentcore.yaml
rm -rf .bedrock_agentcore
```

### アンデプロイ後の状態

- ✅ 全てのAWSリソースが削除される
- ✅ JWT認証設定が削除される
- ✅ M2M認証設定が削除される
- ✅ AgentCore Memoryリソースが削除される
- ✅ AWSコストが発生しなくなる
- ✅ ローカル設定ファイルがクリーンアップされる
- 🔄 `./deploy_to_aws.sh` で再デプロイ可能（JWT認証・M2M認証・メモリ統合含む）

## 🛠️ トラブルシューティング

### よくある問題

#### 1. JWT認証エラー
```
ERROR: JWT認証エラー: アクセストークンが無効です
```
**解決方法**:
```bash
# Cognito設定を確認
aws cloudformation describe-stacks --stack-name Healthmate-CoreStack

# JWT Discovery URLの確認
echo "https://cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration"

# Access Token（ID Tokenではない）を使用していることを確認
```

#### 2. Client ID不一致エラー
```
ERROR: JWT Client ID validation failed
```
**解決方法**:
```bash
# allowedClientsの確認
cat .bedrock_agentcore.yaml | grep -A 5 allowedClients

# Access Tokenのclient_idクレーム確認（ID Tokenのaudクレームではない）
```

#### 3. M2M認証エラー
```
ERROR: M2M認証設定エラー: プロバイダー名が設定されていません
```
**解決方法**:
```bash
# 環境変数を確認
echo $AGENTCORE_PROVIDER_NAME

# 再デプロイで自動設定
./deploy_to_aws.sh
```

#### 4. MCP接続エラー
```
ERROR: MCP Gateway接続エラー (404): HealthManager MCPサービスが見つかりません
```
**解決方法**:
```bash
# CloudFormationスタックの確認
aws cloudformation describe-stacks --stack-name Healthmate-HealthManagerStack

# Gateway IDの確認
echo $HEALTHMANAGER_GATEWAY_ID
```

#### 5. セッション継続性エラー
```
ERROR: AgentCore Memory設定エラー: 環境変数 BEDROCK_AGENTCORE_MEMORY_ID が設定されていません
```
**解決方法**:
```bash
# Memory IDの確認
agentcore memory list

# 再デプロイでMemory設定
./deploy_to_aws.sh
```

#### 6. 認証フローエラー
```
ERROR: Auth flow not enabled for this client
```
**解決方法**:
- Cognitoクライアント設定で`USER_PASSWORD_AUTH`フローを有効化
- または`ADMIN_NO_SRP_AUTH`フローを有効化

### デバッグモード

詳細なログ出力の有効化：

```bash
# 環境変数でデバッグモード有効化
export LOG_LEVEL=DEBUG
export PYTHONPATH=.

# テスト実行
python manual_test_deployed_agent.py
```

### 設定確認コマンド

```bash
# 全体的な設定状態確認
python test_config_helper.py

# デプロイ状態確認
python check_deployment_status.py

# AgentCore状態確認
agentcore status
```

## 📄 ライセンス

このプロジェクトはHealthmateプロダクトの一部として開発されています。

## 🆘 サポート

### ドキュメント参照
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/)
- [Strands Agent SDK Documentation](https://github.com/awslabs/strands)
- [Model Context Protocol (MCP) Specification](https://modelcontextprotocol.io/)

### 問題報告
問題が発生した場合は、以下の情報を含めて報告してください：

1. **エラーメッセージ**: 完全なエラーログ
2. **実行環境**: Python版、AWS CLI版、リージョン
3. **実行コマンド**: 実行したコマンドとパラメータ
4. **設定状態**: 環境変数とCloudFormationスタック状態
5. **再現手順**: エラーを再現するための手順

### 関連サービス
- **Healthmate-Core**: 認証基盤サービス
- **Healthmate-HealthManager**: MCP バックエンドサービス  
- **HealthmateUI**: Web フロントエンドサービス