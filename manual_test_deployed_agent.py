#!/usr/bin/env python3
"""
HealthCoachAI デプロイ済みエージェント手動テストプログラム

AWSにデプロイされたHealthCoachAIエージェントを
ターミナル上でプロンプト入力による手動テストを行います。
JWTアクセストークンを使用してAgentCore Runtimeを直接呼び出します。
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
import subprocess
import tempfile
import os
from botocore.exceptions import ClientError
from test_config_helper import test_config

# ========================================
# テスト設定（ここで変更可能）
# ========================================

# タイムゾーン設定
# 例: 'Asia/Tokyo', 'America/New_York', 'Europe/London', 'America/Los_Angeles'
TEST_TIMEZONE = 'Euro/London'

# 言語設定  
# 例: 'ja', 'en', 'en-us', 'zh', 'ko', 'es', 'fr', 'de'
TEST_LANGUAGE = 'en'

# ========================================


class DeployedAgentTestSession:
    """デプロイ済みエージェント手動テスト用セッションクラス"""
    
    def __init__(self):
        """セッション初期化"""
        self.config = test_config.get_all_config()
        self.cognito_client = boto3.client('cognito-idp', region_name=self.config['region'])
        self.test_username = None
        self.jwt_token = None
        self.session_active = False
        self.conversation_count = 0
        self.jwt_token_file = None
    
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
    
    async def check_agent_status(self):
        """デプロイされたエージェントの状態を確認"""
        try:
            print("🔍 デプロイされたエージェント状態を確認中...")
            
            # AgentCore CLIを使用してステータス確認
            result = subprocess.run(
                ['agentcore', 'status'],
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )
            
            if result.returncode == 0:
                print("   ✅ health_coach_ai エージェントが正常にデプロイされています")
                return True
            else:
                print(f"   ❌ エージェント状態確認エラー: {result.stderr}")
                return False
            
        except Exception as e:
            print(f"❌ エージェント状態確認エラー: {e}")
            return False
    
    async def setup_authentication(self):
        """認証セットアップ"""
        print("🔐 認証セットアップ中...")
        
        # ランダムなテストユーザー名を生成
        self.test_username = f"deployed_test_{uuid.uuid4().hex[:8]}"
        test_password = "DeployedTest123!"
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
            
            # JWTトークンを一時ファイルに保存
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jwt') as f:
                f.write(self.jwt_token)
                self.jwt_token_file = f.name
            
            # JWTトークンからユーザーIDを取得して表示
            payload = self._decode_jwt_payload(self.jwt_token)
            user_id = payload.get('sub')
            
            self.conversation_count = 0
            
            print(f"   ✅ 認証成功!")
            print(f"   JWT Token: {self.jwt_token[:50]}...")
            print(f"   テストユーザー: {self.test_username}")
            print(f"   🔑 デコードしたユーザーID (sub): {user_id}")
            print(f"   📊 DynamoDB確認用ユーザーID: {user_id}")
            print(f"   💾 JWTトークンファイル: {self.jwt_token_file}")
            
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
        
        # JWTトークンファイルを削除
        if self.jwt_token_file and os.path.exists(self.jwt_token_file):
            try:
                os.remove(self.jwt_token_file)
                print(f"   ✅ JWTトークンファイル削除: {self.jwt_token_file}")
            except Exception as e:
                print(f"   ⚠️  JWTトークンファイル削除エラー: {e}")
        
        self.session_active = False
        self.jwt_token = None
        self.test_username = None
        self.conversation_count = 0
        self.jwt_token_file = None
    
    async def test_agent_query_streaming(self, query: str):
        """デプロイされたエージェントにクエリを送信（ストリーミング対応）"""
        if not self.session_active or not self.jwt_token or not self.jwt_token_file:
            print("❌ セッションまたはJWTトークンが無効です。")
            return
        
        try:
            self.conversation_count += 1
            
            # JWTトークン、タイムゾーン、言語をペイロードに含める
            payload = json.dumps({
                "prompt": query,
                "jwt_token": self.jwt_token,
                "timezone": TEST_TIMEZONE,
                "language": TEST_LANGUAGE,
                "sessionState": {
                    "sessionAttributes": {
                        "jwt_token": self.jwt_token,
                        "timezone": TEST_TIMEZONE,
                        "language": TEST_LANGUAGE
                    }
                }
            })
            
            print(f"DEBUG: Setting timezone: {TEST_TIMEZONE}, language: {TEST_LANGUAGE}")
            
            # ストリーミング対応のsubprocessを開始
            process = subprocess.Popen([
                'agentcore', 'invoke',
                payload
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
               text=True, cwd=os.getcwd(), bufsize=1, universal_newlines=True)
            
            print("\n💬 HealthCoachAI (Deployed) の回答:")
            print("-" * 60)
            
            response_text = ""
            
            # リアルタイムで出力を処理
            try:
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    
                    if line.strip():
                        try:
                            event = json.loads(line.strip())
                            if 'event' in event and 'contentBlockDelta' in event['event']:
                                delta = event['event']['contentBlockDelta'].get('delta', {})
                                if 'text' in delta:
                                    text_chunk = delta['text']
                                    print(text_chunk, end='', flush=True)  # リアルタイム出力
                                    response_text += text_chunk
                        except json.JSONDecodeError:
                            # JSON以外の行はスキップ
                            continue
                
                # プロセス終了を待機（タイムアウト付き）
                try:
                    process.wait(timeout=60)  # 60秒でタイムアウト
                except subprocess.TimeoutExpired:
                    print("\n⚠️  応答がタイムアウトしました。プロセスを終了します...")
                    process.kill()
                    process.wait()
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  ユーザーによって中断されました。プロセスを終了します...")
                process.kill()
                process.wait()
            
            print()  # 改行
            print("-" * 60)
            
            if process.returncode != 0:
                stderr_output = process.stderr.read()
                print(f"❌ AgentCore CLI呼び出しエラー: {stderr_output}")
            elif not response_text:
                print("⚠️  エージェントからの応答を取得できませんでした。")
        
        except Exception as e:
            print(f"❌ デプロイ済みエージェント呼び出しエラー: {e}")
    
    async def test_agent_query(self, query: str) -> str:
        """デプロイされたエージェントにクエリを送信（非ストリーミング・互換性用）"""
        if not self.session_active or not self.jwt_token or not self.jwt_token_file:
            return "❌ セッションまたはJWTトークンが無効です。"
        
        try:
            self.conversation_count += 1
            
            # JWTトークン、タイムゾーン、言語をペイロードに含める
            payload = json.dumps({
                "prompt": query,
                "jwt_token": self.jwt_token,
                "timezone": TEST_TIMEZONE,
                "language": TEST_LANGUAGE,
                "sessionState": {
                    "sessionAttributes": {
                        "jwt_token": self.jwt_token,
                        "timezone": TEST_TIMEZONE,
                        "language": TEST_LANGUAGE
                    }
                }
            })
            
            result = subprocess.run([
                'agentcore', 'invoke',
                payload
            ], capture_output=True, text=True, cwd=os.getcwd())
            
            if result.returncode == 0:
                # 出力からJSONイベントを抽出してテキストを組み立て
                response_text = ""
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    if line.strip():
                        try:
                            event = json.loads(line)
                            if 'event' in event and 'contentBlockDelta' in event['event']:
                                delta = event['event']['contentBlockDelta'].get('delta', {})
                                if 'text' in delta:
                                    response_text += delta['text']
                        except json.JSONDecodeError:
                            # JSON以外の行はスキップ
                            continue
                
                return response_text or "エージェントからの応答を取得できませんでした。"
            else:
                return f"❌ AgentCore CLI呼び出しエラー: {result.stderr}"
        
        except Exception as e:
            return f"❌ デプロイ済みエージェント呼び出しエラー: {e}"


def print_banner():
    """バナー表示"""
    print("=" * 80)
    print("🚀 HealthCoachAI デプロイ済みエージェント手動テストプログラム")
    print("=" * 80)
    print()
    print("このプログラムでは、AWSにデプロイされたHealthCoachAIエージェントを")
    print("手動でテストできます。JWTトークンは自動生成され、")
    print("実際のAgentCore Runtime環境と連携します。")
    print("📡 リアルタイムストリーミング対応で、エージェントの応答が即座に表示されます。")
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
    print("🚀 デプロイ環境:")
    print("  このプログラムはAWSにデプロイされたエージェントをテストします")
    print("  AgentCore Runtime環境で実際に動作するエージェントと通信します")
    print("  📡 リアルタイムストリーミング対応 - エージェントの応答が即座に表示されます")
    print()
    print("📊 DynamoDB確認:")
    print("  'status' コマンドでユーザーID (sub) を確認できます")
    print("  このIDでDynamoDBテーブル内のデータを検索してください")
    print()


async def main():
    """メイン関数"""
    print_banner()
    
    # セッション初期化
    session = DeployedAgentTestSession()
    
    # エージェント状態を確認
    print("🔍 デプロイされたエージェント状態を確認中...")
    agent_status_success = await session.check_agent_status()
    
    if not agent_status_success:
        print("❌ エージェント状態の確認に失敗しました。")
        print("   health_coach_ai エージェントがAWSにデプロイされていることを確認してください。")
        return
    
    # 初回認証
    print("\n🚀 初期認証を実行します...")
    auth_success = await session.setup_authentication()
    
    if not auth_success:
        print("❌ 初期認証に失敗しました。プログラムを終了します。")
        return
    
    print()
    print("✅ 認証完了！デプロイされたHealthCoachAIエージェントとの対話を開始できます。")
    print("   'help' でコマンド一覧を表示できます。")
    print("   📊 'status' コマンドでユーザーIDを再確認できます。")
    print("   ⌨️  複数行入力可能（空行で実行）")
    print()
    
    try:
        while True:
            try:
                # マルチライン入力を取得
                user_input = get_multiline_input("🚀 HealthCoachAI (Deployed)> ").strip()
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
                print(f"   JWTトークンファイル: {session.jwt_token_file or 'なし'}")
                print(f"   会話回数: {session.conversation_count}")
                
                # 現在のユーザーIDを表示
                if session.jwt_token:
                    payload = session._decode_jwt_payload(session.jwt_token)
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
                    print("✅ 認証再実行完了！")
                else:
                    print("❌ 認証再実行に失敗しました。")
                print()
                continue
            
            # デプロイされたエージェントにクエリを送信（ストリーミング）
            print("\n🤔 デプロイされたエージェント (AgentCore Runtime) に送信中...")
            await session.test_agent_query_streaming(user_input)
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