#!/usr/bin/env python3
"""
HealthCoachAI エージェント手動テストプログラム

ターミナル上でプロンプト入力による手動テストを行います。
JWTトークンは自動生成されます。
"""

import asyncio
import uuid
import boto3
import hashlib
import hmac
import base64
import sys
import readline
from unittest.mock import patch
from botocore.exceptions import ClientError
from health_coach_ai.agent import invoke_health_coach, _create_health_coach_agent, _decode_jwt_payload
from bedrock_agentcore.runtime import BedrockAgentCoreContext
from test_config_helper import test_config


class ManualTestSession:
    """手動テスト用セッションクラス"""
    
    def __init__(self):
        """セッション初期化"""
        self.config = test_config.get_all_config()
        self.cognito_client = boto3.client('cognito-idp', region_name=self.config['region'])
        self.test_username = None
        self.jwt_token = None
        self.session_active = False
        self.agent = None  # エージェントインスタンスを保持
        self.conversation_count = 0  # 会話回数をカウント
    
    def calculate_secret_hash(self, username: str) -> str:
        """Cognito Client Secret Hash を計算"""
        message = username + self.config['client_id']
        dig = hmac.new(
            self.config['client_secret'].encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()
    
    async def setup_authentication(self):
        """認証セットアップ"""
        print("🔐 認証セットアップ中...")
        
        # ランダムなテストユーザー名を生成
        self.test_username = f"manual_test_{uuid.uuid4().hex[:8]}"
        test_password = "ManualTest123!"
        test_email = f"{self.test_username}@example.com"
        
        try:
            # テストユーザー作成
            print(f"   ユーザー作成: {self.test_username}")
            self.cognito_client.admin_create_user(
                UserPoolId=self.config['user_pool_id'],
                Username=self.test_username,
                UserAttributes=[
                    {'Name': 'email', 'Value': test_email},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                TemporaryPassword=test_password,
                MessageAction='SUPPRESS'
            )
            
            # パスワードを永続化
            self.cognito_client.admin_set_user_password(
                UserPoolId=self.config['user_pool_id'],
                Username=self.test_username,
                Password=test_password,
                Permanent=True
            )
            
            # 認証実行
            secret_hash = self.calculate_secret_hash(self.test_username)
            response = self.cognito_client.admin_initiate_auth(
                UserPoolId=self.config['user_pool_id'],
                ClientId=self.config['client_id'],
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': self.test_username,
                    'PASSWORD': test_password,
                    'SECRET_HASH': secret_hash
                }
            )
            
            self.jwt_token = response['AuthenticationResult']['AccessToken']
            self.session_active = True
            
            # JWTトークンからユーザーIDを取得して表示
            payload = _decode_jwt_payload(self.jwt_token)
            user_id = payload.get('sub')
            
            # エージェントインスタンスを作成（セッション維持のため）
            # BedrockAgentCoreContextをモック（実際のJWTトークンを使用）
            with patch.object(BedrockAgentCoreContext, 'get_workload_access_token', return_value=self.jwt_token):
                self.agent = await _create_health_coach_agent()
            self.conversation_count = 0
            
            print(f"   ✅ 認証成功!")
            print(f"   JWT Token: {self.jwt_token[:50]}...")
            print(f"   テストユーザー: {self.test_username}")
            print(f"   🔑 デコードしたユーザーID (sub): {user_id}")
            print(f"   📊 DynamoDB確認用ユーザーID: {user_id}")
            print(f"   ✅ エージェントセッション開始")
            
            return True
            
        except Exception as e:
            print(f"   ❌ 認証セットアップエラー: {e}")
            return False
    
    async def cleanup_session(self):
        """セッションクリーンアップ"""
        if self.test_username:
            try:
                self.cognito_client.admin_delete_user(
                    UserPoolId=self.config['user_pool_id'],
                    Username=self.test_username
                )
                print(f"   ✅ テストユーザー削除: {self.test_username}")
            except Exception as e:
                print(f"   ⚠️  ユーザー削除エラー: {e}")
        
        self.session_active = False
        self.jwt_token = None
        self.test_username = None
        self.agent = None
        self.conversation_count = 0
    
    async def test_agent_query(self, query: str) -> str:
        """エージェントにクエリを送信（セッション維持）"""
        if not self.session_active or not self.jwt_token or not self.agent:
            return "❌ セッションが無効です。認証を再実行してください。"
        
        try:
            # BedrockAgentCoreContextをモック（実際のJWTトークンを使用）
            with patch.object(BedrockAgentCoreContext, 'get_workload_access_token', return_value=self.jwt_token):
                
                # 同じエージェントインスタンスを使用してセッションを維持
                self.conversation_count += 1
                
                # エージェントのストリーミング実行
                response_text = ""
                async for event in self.agent.stream_async(query):
                    if isinstance(event, str):
                        response_text += event
                    elif isinstance(event, dict) and "event" in event:
                        event_data = event["event"]
                        if "contentBlockDelta" in event_data:
                            delta = event_data["contentBlockDelta"].get("delta", {})
                            if "text" in delta:
                                response_text += delta["text"]
                
                return response_text
        
        except Exception as e:
            return f"❌ エージェント呼び出しエラー: {e}"


def print_banner():
    """バナー表示"""
    print("=" * 80)
    print("🏥 HealthCoachAI エージェント手動テストプログラム")
    print("=" * 80)
    print()
    print("このプログラムでは、HealthCoachAIエージェントを手動でテストできます。")
    print("JWTトークンは自動生成され、実際のHealthManagerMCPサーバーと連携します。")
    print()


def get_multiline_input(prompt: str) -> str:
    """マルチライン入力を取得"""
    print(f"{prompt}")
    print("💡 複数行入力可能です。入力完了後、空行でEnterを押してください。")
    print("   単一行の場合は、そのままEnterを押してください。")
    print()
    
    lines = []
    line_count = 0
    
    try:
        while True:
            line_count += 1
            if line_count == 1:
                line_prompt = "   > "
            else:
                line_prompt = "  .. "
            
            try:
                line = input(line_prompt)
                
                # 最初の行が空の場合はスキップ
                if line_count == 1 and not line.strip():
                    continue
                
                # 2行目以降で空行が入力された場合は実行
                if line_count > 1 and not line.strip():
                    break
                
                # 行を追加
                lines.append(line)
                
                # 最初の行の場合、続けて入力するか確認
                if line_count == 1:
                    print("   (続けて入力する場合はそのまま入力、完了の場合は空行でEnter)")
                
            except (EOFError, KeyboardInterrupt):
                if lines:
                    print("\n入力がキャンセルされました。")
                    return ""
                else:
                    raise
        
        result = '\n'.join(lines).strip()
        print()  # 空行を追加
        return result
        
    except (KeyboardInterrupt, EOFError):
        raise


def print_help():
    """ヘルプ表示"""
    print("\n📋 利用可能なコマンド:")
    print("  help     - このヘルプを表示")
    print("  quit     - プログラムを終了")
    print("  exit     - プログラムを終了")
    print("  clear    - 画面をクリア")
    print("  status   - セッション状態とユーザーIDを表示")
    print("  restart  - 認証を再実行（会話履歴はリセット）")
    print()
    print("⌨️  入力方法:")
    print("  単一行入力 - テキスト入力後、Enterで実行")
    print("  複数行入力 - 各行でEnterを押して継続、空行で実行")
    print("  Ctrl + C   - 入力をキャンセル")
    print()
    print("💡 テスト例:")
    print("  こんにちは")
    print("  利用可能なツールを教えてください")
    print("  私の健康データを確認してください")
    print("  新規ユーザーを作成してください")
    print("  健康目標を設定したいです")
    print()
    print("🔄 セッション維持:")
    print("  会話履歴は自動的に保持されます")
    print("  前の会話内容を参照した質問も可能です")
    print()
    print("📊 DynamoDB確認:")
    print("  'status' コマンドでユーザーID (sub) を確認できます")
    print("  このIDでDynamoDBテーブル内のデータを検索してください")
    print()


async def main():
    """メイン関数"""
    print_banner()
    
    # セッション初期化
    session = ManualTestSession()
    
    # 初回認証
    print("🚀 初期認証を実行します...")
    auth_success = await session.setup_authentication()
    
    if not auth_success:
        print("❌ 初期認証に失敗しました。プログラムを終了します。")
        return
    
    print()
    print("✅ 認証完了！HealthCoachAIエージェントとの対話を開始できます。")
    print("   'help' でコマンド一覧を表示できます。")
    print("   🔄 会話履歴は自動的に保持されます。")
    print("   📊 'status' コマンドでユーザーIDを再確認できます。")
    print("   ⌨️  複数行入力可能（空行で実行）")
    print()
    
    try:
        while True:
            try:
                # マルチライン入力を取得
                user_input = get_multiline_input("🤖 HealthCoachAI> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 プログラムを終了します...")
                break
            
            # 空入力の場合はスキップ
            if not user_input:
                continue
            
            # コマンド処理
            if user_input.lower() in ['quit', 'exit']:
                print("👋 プログラムを終了します...")
                break
            
            elif user_input.lower() == 'help':
                print_help()
                continue
            
            elif user_input.lower() == 'clear':
                import os
                os.system('clear' if os.name == 'posix' else 'cls')
                print_banner()
                continue
            
            elif user_input.lower() == 'status':
                print(f"\n📊 セッション状態:")
                print(f"   認証状態: {'✅ 有効' if session.session_active else '❌ 無効'}")
                print(f"   テストユーザー: {session.test_username or 'なし'}")
                print(f"   JWT Token: {'✅ 有効' if session.jwt_token else '❌ なし'}")
                print(f"   エージェント: {'✅ 有効' if session.agent else '❌ なし'}")
                print(f"   会話回数: {session.conversation_count}")
                
                # 現在のユーザーIDを表示
                if session.jwt_token:
                    payload = _decode_jwt_payload(session.jwt_token)
                    user_id = payload.get('sub')
                    print(f"   🔑 現在のユーザーID (sub): {user_id}")
                    print(f"   📊 DynamoDB確認用: {user_id}")
                
                print()
                continue
            
            elif user_input.lower() == 'restart':
                print("🔄 認証を再実行します...")
                await session.cleanup_session()
                auth_success = await session.setup_authentication()
                if auth_success:
                    print("✅ 認証再実行完了！新しいエージェントセッションが開始されました。")
                else:
                    print("❌ 認証再実行に失敗しました。")
                print()
                continue
            
            # エージェントにクエリを送信
            print("\n🤔 考え中...")
            response = await session.test_agent_query(user_input)
            
            print("\n💬 HealthCoachAI の回答:")
            print("-" * 60)
            print(response)
            print("-" * 60)
            print()
    
    finally:
        # セッションクリーンアップ
        print("\n🧹 セッションクリーンアップ中...")
        await session.cleanup_session()
        print("✅ クリーンアップ完了")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 プログラムが中断されました。")
    except Exception as e:
        print(f"\n❌ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()