#!/usr/bin/env python3
"""
MCP Schema Discovery テスト
"""

import asyncio
import uuid
import boto3
import hashlib
import hmac
import base64
from unittest.mock import patch
from health_coach_ai.agent import list_health_tools, health_manager_mcp, invoke_health_coach
from bedrock_agentcore.runtime import BedrockAgentCoreContext
from test_config_helper import test_config


def calculate_secret_hash(username: str) -> str:
    """Cognito Client Secret Hash を計算"""
    client_id = test_config.get_client_id()
    client_secret = test_config.get_client_secret()
    
    message = username + client_id
    dig = hmac.new(
        client_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()


async def create_test_user_and_authenticate():
    """テストユーザーを作成して認証"""
    # CloudFormationから設定を取得
    config = test_config.get_all_config()
    
    cognito_client = boto3.client('cognito-idp', region_name=config['region'])
    test_username = f"mcp_schema_test_{uuid.uuid4().hex[:8]}"
    test_password = "HealthTest123!"
    test_email = f"{test_username}@example.com"
    
    try:
        # ユーザー作成
        cognito_client.admin_create_user(
            UserPoolId=config['user_pool_id'],
            Username=test_username,
            UserAttributes=[
                {'Name': 'email', 'Value': test_email},
                {'Name': 'email_verified', 'Value': 'true'}
            ],
            TemporaryPassword=test_password,
            MessageAction='SUPPRESS'
        )
        
        # パスワードを永続化
        cognito_client.admin_set_user_password(
            UserPoolId=config['user_pool_id'],
            Username=test_username,
            Password=test_password,
            Permanent=True
        )
        
        # 認証実行
        secret_hash = calculate_secret_hash(test_username)
        response = cognito_client.admin_initiate_auth(
            UserPoolId=config['user_pool_id'],
            ClientId=config['client_id'],
            AuthFlow='ADMIN_NO_SRP_AUTH',
            AuthParameters={
                'USERNAME': test_username,
                'PASSWORD': test_password,
                'SECRET_HASH': secret_hash
            }
        )
        
        access_token = response['AuthenticationResult']['AccessToken']
        return test_username, access_token
        
    except Exception as e:
        print(f"認証セットアップエラー: {e}")
        return None, None


def cleanup_test_user(username):
    """テストユーザーを削除"""
    try:
        config = test_config.get_all_config()
        cognito_client = boto3.client('cognito-idp', region_name=config['region'])
        cognito_client.admin_delete_user(
            UserPoolId=config['user_pool_id'],
            Username=username
        )
        print(f"✓ テストユーザー削除: {username}")
    except Exception as e:
        print(f"⚠️ ユーザー削除エラー: {e}")


async def test_mcp_schema_discovery():
    """MCP スキーマ発見テスト"""
    print("=== MCP スキーマ発見テスト ===")
    
    # 実際のCognito認証をセットアップ
    username, jwt_token = await create_test_user_and_authenticate()
    
    if not jwt_token:
        print("❌ 認証セットアップに失敗しました")
        return
    
    try:
        print(f"✓ テストユーザー作成・認証成功: {username}")
        
        # BedrockAgentCoreContextをモック（実際のJWTトークンを使用）
        with patch.object(BedrockAgentCoreContext, 'get_workload_access_token', return_value=jwt_token):
            
            # 1. 利用可能なツールのリストを取得
            print("\n--- 1. HealthManagerMCPツールリスト取得 ---")
            tools_list = await list_health_tools()
            print(f"ツールリスト結果:\n{tools_list}")
            
            # 2. エージェントにスキーマ発見を依頼
            print("\n--- 2. エージェントによるスキーマ発見 ---")
            result = await invoke_health_coach("利用可能な健康管理ツールを教えてください。どのような機能がありますか？")
            print(f"エージェント応答:\n{result[:500]}...")
            
            # 3. 具体的なユーザー管理テスト
            print("\n--- 3. 具体的なユーザー管理テスト ---")
            test_user_id = f"schema_test_{uuid.uuid4().hex[:8]}"
            result2 = await invoke_health_coach(f"ユーザーID {test_user_id} の情報を確認してください。見つからない場合は、新規ユーザーとして作成してください。")
            print(f"ユーザー管理テスト結果:\n{result2[:500]}...")
            
    finally:
        # テストユーザーをクリーンアップ
        if username:
            cleanup_test_user(username)


async def main():
    """メインテスト実行"""
    print("HealthManagerMCP スキーマ発見テスト")
    print("=" * 50)
    
    try:
        await test_mcp_schema_discovery()
        
        print("\n" + "=" * 50)
        print("🎉 スキーマ発見テスト完了！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())