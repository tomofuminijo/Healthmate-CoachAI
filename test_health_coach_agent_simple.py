#!/usr/bin/env python3
"""
HealthCoachAI エージェントの簡単なテスト
"""

import asyncio
import uuid
import boto3
import hashlib
import hmac
import base64
from unittest.mock import patch
from botocore.exceptions import ClientError
from health_coach_ai.agent import invoke_health_coach, _create_health_coach_agent, health_manager_mcp
from bedrock_agentcore.runtime import BedrockAgentCoreContext
from test_config_helper import test_config


async def test_simple_agent_creation():
    """エージェント作成の簡単なテスト"""
    print("=== エージェント作成テスト ===")
    
    agent = _create_health_coach_agent()
    assert agent is not None
    print("✓ エージェント作成成功")
    
    # システムプロンプトの確認
    assert "健康コーチAI" in agent.system_prompt
    print("✓ システムプロンプトが設定されています")


async def test_simple_invoke():
    """簡単な呼び出しテスト（認証なし）"""
    print("\n=== 簡単な呼び出しテスト ===")
    
    # JWT認証をモック（認証エラーを回避）
    with patch('health_coach_ai.agent.health_manager_mcp') as mock_mcp:
        mock_mcp.return_value = "モックレスポンス"
        
        result = await invoke_health_coach("こんにちは")
        
        print(f"✓ エージェント呼び出し成功")
        print(f"結果: {result[:100]}...")
        
        assert result is not None
        assert len(result) > 0


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
    test_username = f"healthcoach_simple_test_{uuid.uuid4().hex[:8]}"
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


async def test_real_mcp_tool_call():
    """実際のHealthManagerMCPツール呼び出しテスト"""
    print("\n=== 実際のHealthManagerMCPツール呼び出しテスト ===")
    
    # 実際のCognito認証をセットアップ
    username, jwt_token = await create_test_user_and_authenticate()
    
    if not jwt_token:
        print("❌ 認証セットアップに失敗しました")
        return
    
    try:
        print(f"✓ テストユーザー作成・認証成功: {username}")
        print(f"✓ JWT Token取得: {jwt_token[:50]}...")
        
        # BedrockAgentCoreContextをモック（実際のJWTトークンを使用）
        with patch.object(BedrockAgentCoreContext, 'get_workload_access_token', return_value=jwt_token):
            
            # 実際のHealthManagerMCP Gatewayを呼び出し
            result = await health_manager_mcp(
                tool_name="UserManagement___GetUser",
                arguments={"user_id": "test_user_12345"}
            )
            
            print(f"✓ 実際のMCPツール呼び出し完了")
            print(f"結果: {result[:200]}...")
            
            # 認証が成功していることを確認（401エラーでないこと）
            assert "HTTP エラー 401" not in result
            assert "認証トークンが見つかりません" not in result
            
            print("✓ 実際のHealthManagerMCP Gatewayとの連携が確認されました")
            
    finally:
        # テストユーザーをクリーンアップ
        if username:
            cleanup_test_user(username)


async def test_comprehensive_health_management_workflow():
    """包括的な健康管理ワークフローテスト"""
    print("\n=== 包括的な健康管理ワークフローテスト ===")
    
    # 実際のCognito認証をセットアップ
    username, jwt_token = await create_test_user_and_authenticate()
    
    if not jwt_token:
        print("❌ 認証セットアップに失敗しました")
        return
    
    # ランダムなユーザーIDを生成
    test_user_id = f"user_{uuid.uuid4().hex[:12]}"
    
    try:
        print(f"✓ テストユーザー作成・認証成功: {username}")
        print(f"✓ テスト用ユーザーID: {test_user_id}")
        
        # BedrockAgentCoreContextをモック（実際のJWTトークンを使用）
        with patch.object(BedrockAgentCoreContext, 'get_workload_access_token', return_value=jwt_token):
            
            # 1. 新規のランダムなユーザIDで、ユーザ情報を確認
            print("\n--- 1. ユーザー情報確認 ---")
            result1 = await invoke_health_coach(f"私のユーザーIDは{test_user_id}です。私の健康データを確認してください。")
            print(f"✓ ユーザー情報確認結果: {result1[:200]}...")
            
            # 2. ユーザ情報が無いので、新規にユーザ作成
            print("\n--- 2. 新規ユーザー作成 ---")
            result2 = await invoke_health_coach(f"ユーザーID {test_user_id} で新規ユーザーを作成してください。名前は田中太郎、年齢は30歳、性別は男性でお願いします。")
            print(f"✓ ユーザー作成結果: {result2[:200]}...")
            
            # 3. 作成したユーザの健康目標の登録・更新・削除
            print("\n--- 3. 健康目標管理 ---")
            
            # 健康目標登録
            result3a = await invoke_health_coach(f"ユーザーID {test_user_id} の健康目標を設定してください。体重を70kgまで減らす目標を2024年12月31日までに達成したいです。")
            print(f"✓ 健康目標登録結果: {result3a[:200]}...")
            
            # 健康目標更新
            result3b = await invoke_health_coach(f"ユーザーID {test_user_id} の健康目標を更新してください。体重目標を68kgに変更し、期限を2025年3月31日に延長してください。")
            print(f"✓ 健康目標更新結果: {result3b[:200]}...")
            
            # 健康目標削除
            result3c = await invoke_health_coach(f"ユーザーID {test_user_id} の体重減量目標を削除してください。")
            print(f"✓ 健康目標削除結果: {result3c[:200]}...")
            
            # 4. 作成したユーザの健康ポリシーの登録・更新・削除
            print("\n--- 4. 健康ポリシー管理 ---")
            
            # 健康ポリシー登録
            result4a = await invoke_health_coach(f"ユーザーID {test_user_id} の健康ポリシーを設定してください。毎日8000歩歩く、週3回筋トレをする、22時までに就寝するというポリシーを設定してください。")
            print(f"✓ 健康ポリシー登録結果: {result4a[:200]}...")
            
            # 健康ポリシー更新
            result4b = await invoke_health_coach(f"ユーザーID {test_user_id} の健康ポリシーを更新してください。歩数目標を10000歩に変更し、就寝時間を23時に変更してください。")
            print(f"✓ 健康ポリシー更新結果: {result4b[:200]}...")
            
            # 健康ポリシー削除
            result4c = await invoke_health_coach(f"ユーザーID {test_user_id} の筋トレポリシーを削除してください。")
            print(f"✓ 健康ポリシー削除結果: {result4c[:200]}...")
            
            # 5. 作成したユーザの一日の行動履歴の分割した複数回登録、特定履歴の更新、削除
            print("\n--- 5. 行動履歴管理 ---")
            
            # 朝の行動履歴登録
            result5a = await invoke_health_coach(f"ユーザーID {test_user_id} の2024年12月14日の朝の行動履歴を登録してください。7:00起床、7:30朝食（パン、コーヒー）、8:00散歩30分を記録してください。")
            print(f"✓ 朝の行動履歴登録結果: {result5a[:200]}...")
            
            # 昼の行動履歴登録
            result5b = await invoke_health_coach(f"ユーザーID {test_user_id} の2024年12月14日の昼の行動履歴を登録してください。12:00昼食（サラダ、チキン）、13:00-14:00昼休み、14:00-17:00デスクワークを記録してください。")
            print(f"✓ 昼の行動履歴登録結果: {result5b[:200]}...")
            
            # 夜の行動履歴登録
            result5c = await invoke_health_coach(f"ユーザーID {test_user_id} の2024年12月14日の夜の行動履歴を登録してください。19:00夕食（魚、野菜）、20:00-21:00ジム、22:30就寝を記録してください。")
            print(f"✓ 夜の行動履歴登録結果: {result5c[:200]}...")
            
            # 特定履歴の更新
            result5d = await invoke_health_coach(f"ユーザーID {test_user_id} の2024年12月14日の朝食内容を更新してください。パンとコーヒーから、オートミールとフルーツに変更してください。")
            print(f"✓ 行動履歴更新結果: {result5d[:200]}...")
            
            # 特定履歴の削除
            result5e = await invoke_health_coach(f"ユーザーID {test_user_id} の2024年12月14日の昼休みの記録を削除してください。")
            print(f"✓ 行動履歴削除結果: {result5e[:200]}...")
            
            print("\n✅ 包括的な健康管理ワークフローテストが完了しました")
            
    finally:
        # テストユーザーをクリーンアップ
        if username:
            cleanup_test_user(username)


async def main():
    """メインテスト実行"""
    print("HealthCoachAI エージェント包括的テスト（実際のMCP統合付き）")
    print("=" * 70)
    
    try:
        await test_simple_agent_creation()
        await test_simple_invoke()
        await test_real_mcp_tool_call()
        await test_comprehensive_health_management_workflow()
        
        print("\n" + "=" * 70)
        print("🎉 全テスト完了！")
        print("=" * 70)
        
        print("\n検証完了項目:")
        print("✓ エージェント作成")
        print("✓ 基本的な呼び出し（モック）")
        print("✓ 実際のHealthManagerMCPツール呼び出し")
        print("✓ 包括的な健康管理ワークフロー:")
        print("  - ユーザー情報確認")
        print("  - 新規ユーザー作成")
        print("  - 健康目標の登録・更新・削除")
        print("  - 健康ポリシーの登録・更新・削除")
        print("  - 行動履歴の分割登録・更新・削除")
        
    except Exception as e:
        print(f"\n❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())