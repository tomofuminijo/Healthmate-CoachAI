#!/usr/bin/env python3
"""
Healthmate-CoachAI デプロイ済みエージェント手動テストプログラム（環境別設定対応）

AWSにデプロイされたHealthmate-CoachAIエージェントを
ターミナル上でプロンプト入力による手動テストを行います。
JWT IDトークンを使用してboto3 bedrock-agentcoreクライアントで直接呼び出します。

環境別設定対応:
- HEALTHMATE_ENV環境変数に基づく環境別テスト（dev/stage/prod）
- 環境別エージェント名の自動解決
- 環境別設定ファイルの読み込み
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
import tempfile
import os
import yaml
import requests
import urllib.parse
from botocore.exceptions import ClientError
from test_config_helper import test_config

# ========================================
# 環境設定
# ========================================

def get_environment_config():
    """環境設定を取得"""
    # HEALTHMATE_ENV環境変数の取得（デフォルト: dev）
    environment = os.environ.get('HEALTHMATE_ENV', 'dev')
    
    # 有効な環境値の検証
    if environment not in ['dev', 'stage', 'prod']:
        print(f"❌ 無効な環境値: {environment}")
        print("   有効な値: dev, stage, prod")
        print("   デフォルトのdev環境を使用します")
        environment = 'dev'
    
    # 環境別サフィックスの設定
    env_suffix = f"-{environment}"
    
    # 環境別エージェント名の生成
    agent_name = "healthmate_coach_ai"
    agent_name = f"{agent_name}_{environment}"
    
    return {
        'environment': environment,
        'env_suffix': env_suffix,
        'agent_name': agent_name
    }

# 環境設定を取得
ENV_CONFIG = get_environment_config()

# ========================================
# テスト設定（ここで変更可能）
# ========================================

# タイムゾーン設定
# 例: 'Asia/Tokyo', 'America/New_York', 'Europe/London', 'America/Los_Angeles'
TEST_TIMEZONE = 'Asia/Tokyo'
#TEST_TIMEZONE = 'America/New_York'

# 言語設定  
# 例: 'ja', 'en', 'en-us', 'zh', 'ko', 'es', 'fr', 'de'
TEST_LANGUAGE = 'ja'
#TEST_LANGUAGE = 'en'

# ========================================


class DeployedAgentTestSession:
    """デプロイ済みエージェント手動テスト用セッションクラス"""
    
    def __init__(self):
        """セッション初期化"""
        self.config = test_config.get_all_config()
        self.cognito_client = boto3.client('cognito-idp', region_name=self.config['region'])
        self.agentcore_client = boto3.client('bedrock-agentcore', region_name=self.config['region'])
        self.test_username = None
        self.jwt_token = None
        self.session_active = False
        self.conversation_count = 0
        self.jwt_token_file = None
        self.agent_runtime_arn = None
    
    def calculate_secret_hash(self, username: str) -> str:
        """Cognito Client Secret Hash を計算（Client Secret不要の場合はNoneを返す）"""
        # Client Secretが設定されていない場合はNoneを返す
        if not hasattr(self.config, 'client_secret') or not self.config.get('client_secret'):
            return None
        
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
    
    def _load_agent_runtime_arn(self):
        """AgentCore設定ファイルからAgent Runtime ARNを取得（環境別対応）"""
        try:
            config_file = '.bedrock_agentcore.yaml'
            if not os.path.exists(config_file):
                raise FileNotFoundError(f"AgentCore設定ファイル '{config_file}' が見つかりません")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                agentcore_config = yaml.safe_load(f)
            
            # 環境別エージェント名でARNを取得
            agent_name = ENV_CONFIG['agent_name']
            agents = agentcore_config.get('agents', {})
            agent_config = agents.get(agent_name, {})
            bedrock_agentcore = agent_config.get('bedrock_agentcore', {})
            agent_arn = bedrock_agentcore.get('agent_arn')
            
            if not agent_arn:
                # 利用可能なエージェント名を表示
                available_agents = list(agents.keys())
                raise ValueError(f"Agent Runtime ARNが設定ファイルに見つかりません。\n"
                               f"期待されるエージェント名: {agent_name}\n"
                               f"利用可能なエージェント: {available_agents}")
            
            self.agent_runtime_arn = agent_arn
            print(f"   ✅ Agent Runtime ARN: {agent_arn}")
            print(f"   🌍 環境: {ENV_CONFIG['environment']}")
            print(f"   🤖 エージェント名: {agent_name}")
            return True
            
        except Exception as e:
            print(f"   ❌ Agent Runtime ARN取得エラー: {e}")
            return False

    async def check_agent_status(self):
        """デプロイされたエージェントの状態を確認"""
        try:
            print("🔍 デプロイされたエージェント状態を確認中...")
            
            # Agent Runtime ARNを取得
            if not self._load_agent_runtime_arn():
                return False
            
            # Agent Runtime ARNが取得できれば、エージェントは利用可能と判断
            print(f"   ✅ {ENV_CONFIG['agent_name']} エージェントのRuntime ARNが確認できました")
            print(f"   🌍 テスト環境: {ENV_CONFIG['environment']}")
            return True
            
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
            
            # 認証実行（ALLOW_USER_PASSWORD_AUTHフローを使用）
            secret_hash = self.calculate_secret_hash(self.test_username)
            
            # AuthParametersを構築（Secret Hashが不要な場合は含めない）
            auth_parameters = {
                'USERNAME': self.test_username,
                'PASSWORD': test_password
            }
            
            # Secret Hashが利用可能な場合のみ追加
            if secret_hash:
                auth_parameters['SECRET_HASH'] = secret_hash
            
            # まずADMIN_NO_SRP_AUTHを試行
            try:
                response = self.cognito_client.admin_initiate_auth(
                    UserPoolId=self.config['user_pool_id'],
                    ClientId=self.config['client_id'],
                    AuthFlow='ADMIN_NO_SRP_AUTH',
                    AuthParameters=auth_parameters
                )
            except ClientError as e:
                if 'Auth flow not enabled' in str(e):
                    print("   ⚠️  ADMIN_NO_SRP_AUTH フローが無効です。ALLOW_USER_PASSWORD_AUTH を試行します...")
                    # ALLOW_USER_PASSWORD_AUTHフローを試行
                    response = self.cognito_client.initiate_auth(
                        ClientId=self.config['client_id'],
                        AuthFlow='USER_PASSWORD_AUTH',
                        AuthParameters=auth_parameters
                    )
                else:
                    raise
            
            self.jwt_token = response['AuthenticationResult']['AccessToken']  # AccessTokenを使用
            self.session_active = True
            
            # JWTトークンを一時ファイルに保存
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jwt') as f:
                f.write(self.jwt_token)
                self.jwt_token_file = f.name
            
            # JWTトークンからユーザーIDを取得して表示
            payload = self._decode_jwt_payload(self.jwt_token)
            user_id = payload.get('sub')
            client_id = payload.get('aud')
            
            self.conversation_count = 0
            
            print(f"   ✅ 認証成功!")
            print(f"   JWT Token: {self.jwt_token[:50]}...")
            print(f"   テストユーザー: {self.test_username}")
            print(f"   � DデコードしたユーザーID (sub): {user_id}")
            print(f"   �  JWT Client ID (aud): {client_id}")
            print(f"   🔑 期待されるClient ID: {self.config['client_id']}")
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
    

    async def test_agent_query_streaming(self, query: str, session_id: str = None):
        """デプロイされたエージェントにクエリを送信（ストリーミング対応）"""
        if not self.session_active or not self.jwt_token or not self.agent_runtime_arn:
            print("❌ セッションまたはJWTトークンが無効です。")
            return
        
        try:
            self.conversation_count += 1
            
            # セッションIDが指定されていない場合は生成
            if not session_id:
                session_id = f'healthmate-test-session-{uuid.uuid4().hex}'
            
            print(f"🔗 使用セッションID: {session_id}")
            
            # JWTトークン、タイムゾーン、言語をペイロードに含める
            payload = {
                "prompt": query,
                "timezone": TEST_TIMEZONE,
                "language": TEST_LANGUAGE
            }
            

            print("\n💬 Healthmate-CoachAI (Deployed) の回答:")
            print("-" * 60)
            
            # JWT認証の場合、AWS SDKは使用できないため、直接HTTPSリクエストを送信
            # AgentCore Runtime エンドポイントURLを構築（AWS公式ドキュメント準拠）
            escaped_agent_arn = urllib.parse.quote(self.agent_runtime_arn, safe='')
            runtime_endpoint_url = f"https://bedrock-agentcore.{self.config['region']}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
            
            print(f"🔗 エンドポイント URL: {runtime_endpoint_url}")  # デバッグ用
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.jwt_token}',
                'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
            }
            
            import requests
            response = requests.post(
                runtime_endpoint_url,
                headers=headers,
                json=payload,
                stream=True
            )
            
            # ストリーミングレスポンスを処理
            response_text = ""
            
            try:
                response.raise_for_status()  # HTTPエラーをチェック
                
                # ストリーミングレスポンスを逐次処理
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
                                        text_chunk = delta['text']
                                        print(text_chunk, end='', flush=True)
                                        response_text += text_chunk
                        except json.JSONDecodeError:
                            continue
                
                if not response_text:
                    print("⚠️  エージェントからの応答を取得できませんでした。")
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  ユーザーによって中断されました。")
            except requests.exceptions.RequestException as e:
                print(f"❌ HTTPリクエストエラー: {e}")
                if hasattr(e.response, 'text'):
                    print(f"レスポンス内容: {e.response.text}")
            
            print()  # 改行
            print("-" * 60)
            
            if not response_text:
                print("⚠️  エージェントからの応答を取得できませんでした。")
        
        except Exception as e:
            print(f"❌ デプロイ済みエージェント呼び出しエラー: {e}")
            import traceback
            traceback.print_exc()
    

def print_banner():
    """バナー表示（環境別対応）"""
    print("=" * 80)
    print("🚀 HealthCoachAI デプロイ済みエージェント手動テストプログラム（環境別設定対応）")
    print("=" * 80)
    print()
    print("このプログラムでは、AWSにデプロイされたHealthCoachAIエージェントを")
    print("手動でテストできます。JWTトークンは自動生成され、")
    print("boto3 bedrock-agentcore クライアントで直接AgentCore Runtime環境と連携します。")
    print("🔗 boto3統合により、安定したエージェント呼び出しを実現します。")
    print()
    print(f"🌍 環境設定:")
    print(f"   環境: {ENV_CONFIG['environment']}")
    print(f"   エージェント名: {ENV_CONFIG['agent_name']}")
    print(f"   タイムゾーン: {TEST_TIMEZONE}")
    print(f"   言語: {TEST_LANGUAGE}")
    print()
    print(f"💡 環境切り替え方法:")
    print(f"   export HEALTHMATE_ENV=dev && python3 manual_test_deployed_agent.py")
    print(f"   export HEALTHMATE_ENV=stage && python3 manual_test_deployed_agent.py")
    print(f"   export HEALTHMATE_ENV=prod && python3 manual_test_deployed_agent.py")
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
    print("  memory_test - セッション継続性の自動テストを実行")
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
    print("🔗 セッション管理テスト例:")
    print("  1. 私の名前はジョニーです")
    print("  2. 私の名前を覚えていますか？")
    print("  (同じセッションIDで会話の継続性をテスト)")
    print()
    print("🚀 デプロイ環境:")
    print("  このプログラムはAWSにデプロイされたエージェントをテストします")
    print("  AgentCore Runtime環境で実際に動作するエージェントと通信します")
    print("  � boルto3 bedrock-agentcore クライアント統合 - 安定したAPI呼び出し")
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
        print(f"   {ENV_CONFIG['agent_name']} エージェント（環境: {ENV_CONFIG['environment']}）がAWSにデプロイされていることを確認してください。")
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
    
    # セッション管理テスト用のセッションID
    test_session_id = f'healthmate-test-session-{uuid.uuid4().hex}'
    print(f"🔗 テスト用セッションID: {test_session_id}")
    print("   このセッションIDで会話の継続性をテストします")
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
            await session.test_agent_query_streaming(user_input, test_session_id)
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