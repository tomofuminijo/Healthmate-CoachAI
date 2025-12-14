#!/usr/bin/env python3
"""
HealthCoachAI ローカル手動テストプログラム

ローカル環境でHealthCoachAIエージェントを
ターミナル上でプロンプト入力による手動テストを行います。
"""

import asyncio
import uuid
import boto3
import hashlib
import hmac
import base64
import json
import sys
import readline
from botocore.exceptions import ClientError
from health_coach_ai.agent import invoke_health_coach

# ========================================
# テスト設定（ここで変更可能）
# ========================================

# タイムゾーン設定
# 例: 'Asia/Tokyo', 'America/New_York', 'Europe/London', 'America/Los_Angeles'
TEST_TIMEZONE = 'Asia/Tokyo'

# 言語設定  
# 例: 'ja', 'en', 'en-us', 'zh', 'ko', 'es', 'fr', 'de'
TEST_LANGUAGE = 'ja'

# ========================================


class LocalTestSession:
    """ローカル手動テスト用セッションクラス"""
    
    def __init__(self):
        """セッション初期化"""
        # CloudFormationから設定を取得
        self.config = self._get_config_from_cloudformation()
        self.cognito_client = boto3.client('cognito-idp', region_name=self.config['region'])
        self.test_username = None
        self.jwt_token = None
        self.session_active = False
        self.conversation_count = 0
    
    def _get_config_from_cloudformation(self) -> dict:
        """CloudFormationスタックから設定を取得"""
        try:
            stack_name = 'HealthManagerMCPStack'  # デフォルトスタック名
            region = 'us-west-2'
            
            cfn = boto3.client('cloudformation', region_name=region)
            response = cfn.describe_stacks(StackName=stack_name)
            
            if not response['Stacks']:
                raise Exception(f"CloudFormationスタック '{stack_name}' が見つかりません")
            
            outputs = {}
            for output in response['Stacks'][0].get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            # Cognito Client Secretを取得
            cognito_client = boto3.client('cognito-idp', region_name=region)
            client_response = cognito_client.describe_user_pool_client(
                UserPoolId=outputs['UserPoolId'],
                ClientId=outputs['UserPoolClientId']
            )
            client_secret = client_response['UserPoolClient']['ClientSecret']
            
            return {
                'region': region,
                'user_pool_id': outputs['UserPoolId'],
                'client_id': outputs['UserPoolClientId'],
                'client_secret': client_secret,
                'gateway_id': outputs['GatewayId']
            }
            
        except Exception as e:
            print(f"❌ CloudFormation設定取得エラー: {e}")
            sys.exit(1)
    
    def calculate_secret_hash(self, username: str) -> str:
        """Cognito Client Secret Hash を計算"""
        message = username + self.config['client_id']
        dig = hmac.new(
            self.config['client_secret'].encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()
    
    def _decode_jwt_payload(self, jwt_token: str) -> dict:
        """JWTトークンのペイロードをデコード（署名検証なし）"""
        try:
            parts = jwt_token.split('.')
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")
            
            payload = parts[1]
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload += '=' * padding
            
            decoded_bytes = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded_bytes.decode('utf-8'))
            
            return payload_data
            
        except Exception as e:
            print(f"JWT デコードエラー: {e}")
            return {}
    
    async def setup_authentication(self):
        """認証セットアップ"""
        print("🔐 認証セットアップ中...")
        
        # ランダムなテストユーザー名を生成
        self.test_username = f"local_test_{uuid.uuid4().hex[:8]}"
        test_password = "LocalTest123!"
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
            payload = self._decode_jwt_payload(self.jwt_token)
            user_id = payload.get('sub')
            
            self.conversation_count = 0
            
            print(f"   ✅ 認証成功!")
            print(f"   JWT Token: {self.jwt_token[:50]}...")
            print(f"   テストユーザー: {self.test_username}")
            print(f"   🔑 デコードしたユーザーID (sub): {user_id}")
            
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
        self.conversation_count = 0
    
    async def test_agent_query(self, query: str) -> str:
        """ローカルエージェントにクエリを送信"""
        if not self.session_active or not self.jwt_token:
            return "❌ セッションまたはJWTトークンが無効です。"
        
        try:
            self.conversation_count += 1
            
            # グローバル変数にJWTトークン、タイムゾーン、言語を設定（エージェントが使用するため）
            import health_coach_ai.agent as agent_module
            agent_module._current_jwt_token = self.jwt_token
            agent_module._current_timezone = TEST_TIMEZONE
            agent_module._current_language = TEST_LANGUAGE
            
            print(f"DEBUG: Setting timezone: {TEST_TIMEZONE}, language: {TEST_LANGUAGE}")
            
            # ローカルエージェントを呼び出し
            response = await invoke_health_coach(query)
            
            return response
        
        except Exception as e:
            return f"❌ ローカルエージェント呼び出しエラー: {e}"


def print_banner():
    """バナー表示"""
    print("=" * 80)
    print("🧪 HealthCoachAI ローカル手動テストプログラム")
    print("=" * 80)
    print()
    print("このプログラムでは、ローカル環境でHealthCoachAIエージェントを")
    print("手動でテストできます。JWTトークンは自動生成され、")
    print("実際のMCP Gatewayと連携します。")
    print()
    print(f"🌍 テスト設定:")
    print(f"   タイムゾーン: {TEST_TIMEZONE}")
    print(f"   言語: {TEST_LANGUAGE}")
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
    print("  restart  - 認証を再実行")
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
    print("🧪 ローカル環境:")
    print("  このプログラムはローカルでエージェントを実行します")
    print("  MCP Gatewayとの通信は実際のAWSリソースを使用します")
    print()


async def main():
    """メイン関数"""
    print_banner()
    
    # セッション初期化
    session = LocalTestSession()
    
    # 初回認証
    print("🚀 初期認証を実行します...")
    auth_success = await session.setup_authentication()
    
    if not auth_success:
        print("❌ 初期認証に失敗しました。プログラムを終了します。")
        return
    
    print()
    print("✅ 認証完了！ローカルHealthCoachAIエージェントとの対話を開始できます。")
    print("   'help' でコマンド一覧を表示できます。")
    print("   📊 'status' コマンドでユーザーIDを再確認できます。")
    print("   ⌨️  複数行入力可能（空行で実行）")
    print()
    
    try:
        while True:
            try:
                # マルチライン入力を取得
                user_input = get_multiline_input("🧪 HealthCoachAI (Local)> ").strip()
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
                print(f"   会話回数: {session.conversation_count}")
                
                # 現在のユーザーIDを表示
                if session.jwt_token:
                    payload = session._decode_jwt_payload(session.jwt_token)
                    user_id = payload.get('sub')
                    print(f"   🔑 現在のユーザーID (sub): {user_id}")
                
                print()
                continue
            
            elif user_input.lower() == 'restart':
                print("🔄 認証を再実行します...")
                await session.cleanup_session()
                auth_success = await session.setup_authentication()
                if auth_success:
                    print("✅ 認証再実行完了！")
                else:
                    print("❌ 認証再実行に失敗しました。")
                print()
                continue
            
            # ローカルエージェントにクエリを送信
            print("\n🤔 ローカルエージェントに送信中...")
            response = await session.test_agent_query(user_input)
            
            print("\n💬 HealthCoachAI (Local) の回答:")
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