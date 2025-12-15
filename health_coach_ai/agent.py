"""
HealthCoachAI エージェント

Amazon Bedrock AgentCore Runtime上で動作する
健康支援AIエージェントです。
"""

import os
import asyncio
import httpx
import json
import base64
from datetime import datetime
from typing import Optional
import pytz
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager


# 環境変数設定管理
def _get_gateway_endpoint() -> str:
    """Gateway エンドポイントを環境変数から取得"""
    gateway_id = os.environ.get('HEALTHMANAGER_GATEWAY_ID')
    if not gateway_id:
        raise Exception("環境変数 HEALTHMANAGER_GATEWAY_ID が設定されていません")
    
    region = os.environ.get('AWS_REGION', 'us-west-2')
    return f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp"

# グローバル変数（JWT処理用）
_current_jwt_token = None
_current_timezone = None
_current_language = None


# JWT Token ヘルパー関数
def _decode_jwt_payload(jwt_token: str) -> dict:
    """JWTトークンのペイロードをデコード（署名検証なし）"""
    try:
        # JWTは "header.payload.signature" の形式
        parts = jwt_token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        # ペイロード部分をデコード
        payload = parts[1]
        
        # Base64URLデコードのためのパディング調整
        padding = 4 - (len(payload) % 4)
        if padding != 4:
            payload += '=' * padding
        
        # Base64デコードしてJSONパース
        decoded_bytes = base64.urlsafe_b64decode(payload)
        payload_data = json.loads(decoded_bytes.decode('utf-8'))
        
        return payload_data
        
    except Exception as e:
        print(f"JWT デコードエラー: {e}")
        return {}


def _get_jwt_token():
    """JWT認証トークンを取得（同期版）"""
    global _current_jwt_token
    
    try:
        # まずグローバル変数から取得を試行
        if _current_jwt_token:
            print(f"DEBUG: JWT token from global variable: {_current_jwt_token[:50]}...")
            return _current_jwt_token
        
        # AgentCore Runtime環境でUIから渡されたJWTトークンを取得
        try:
            jwt_token = BedrockAgentCoreContext.get_workload_access_token()
            if jwt_token:
                print(f"DEBUG: JWT token from get_workload_access_token: {jwt_token[:50]}...")
                return jwt_token
        except Exception as e:
            print(f"DEBUG: get_workload_access_token エラー: {e}")
        
        # フォールバック: リクエストヘッダーからAuthorizationを取得
        try:
            headers = BedrockAgentCoreContext.get_request_headers()
            print(f"DEBUG: Request headers: {headers}")
            
            if headers and 'Authorization' in headers:
                auth_header = headers['Authorization']
                if auth_header.startswith('Bearer '):
                    jwt_token = auth_header[7:]  # "Bearer " を除去
                    print(f"DEBUG: JWT token from Authorization header: {jwt_token[:50]}...")
                    return jwt_token
        except Exception as e:
            print(f"DEBUG: get_request_headers エラー: {e}")
        
        print(f"DEBUG: JWT token not found in any source")
        return None
        
    except Exception as e:
        print(f"DEBUG: JWT token取得エラー: {e}")
        return None


def _get_user_id_from_jwt():
    """JWTトークンからユーザーIDを取得（エラーハンドリング強化版）"""
    try:
        jwt_token = _get_jwt_token()
        if not jwt_token:
            print(f"DEBUG: No JWT token available for user ID extraction")
            return None
        
        payload = _decode_jwt_payload(jwt_token)
        if not payload:
            print(f"DEBUG: Failed to decode JWT payload")
            return None
            
        user_id = payload.get('sub')  # Cognitoの場合、subフィールドにユーザーIDが含まれる
        
        if not user_id:
            print(f"DEBUG: No 'sub' field found in JWT payload")
            # フォールバック: 他のフィールドを試す
            user_id = payload.get('username') or payload.get('email') or payload.get('user_id')
            if user_id:
                print(f"DEBUG: Using fallback user ID: {user_id}")
        
        print(f"DEBUG: Extracted user ID from JWT: {user_id}")
        return user_id
        
    except Exception as e:
        print(f"ERROR: ユーザーID取得エラー: {e}")
        return None


def _get_user_timezone():
    """ペイロードから設定されたタイムゾーンを取得"""
    global _current_timezone
    
    if _current_timezone:
        print(f"DEBUG: Using timezone from payload: {_current_timezone}")
        return _current_timezone
    else:
        print(f"DEBUG: No timezone found in payload, using default: Asia/Tokyo")
        return 'Asia/Tokyo'


def _get_user_language():
    """ペイロードから設定された言語を取得"""
    global _current_language
    
    if _current_language:
        print(f"DEBUG: Using language from payload: {_current_language}")
        return _current_language
    else:
        print(f"DEBUG: No language found in payload, using default: ja")
        return 'ja'


def _get_language_name(language_code: str) -> str:
    """言語コードを言語名に変換"""
    language_map = {
        'ja': '日本語',
        'en': 'English',
        'en-us': 'English (US)',
        'en-gb': 'English (UK)',
        'zh': '中文',
        'zh-cn': '中文 (简体)',
        'zh-tw': '中文 (繁體)',
        'ko': '한국어',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'it': 'Italiano',
        'pt': 'Português',
        'ru': 'Русский'
    }
    return language_map.get(language_code.lower(), language_code)


def _get_localized_datetime(timezone_str: str = 'Asia/Tokyo'):
    """指定されたタイムゾーンでの現在日時を取得"""
    try:
        # タイムゾーンの有効性を確認
        try:
            user_timezone = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            print(f"DEBUG: Invalid timezone: {timezone_str}, using Asia/Tokyo")
            user_timezone = pytz.timezone('Asia/Tokyo')
        
        # UTC時刻を取得してユーザーのタイムゾーンに変換
        utc_now = datetime.now(pytz.UTC)
        local_datetime = utc_now.astimezone(user_timezone)
        
        return local_datetime
        
    except Exception as e:
        print(f"DEBUG: ローカル日時取得エラー: {e}")
        # エラー時はJSTで返す
        jst = pytz.timezone('Asia/Tokyo')
        utc_now = datetime.now(pytz.UTC)
        return utc_now.astimezone(jst)


async def _call_mcp_gateway(method: str, params: dict = None):
    """MCP Gatewayを呼び出す共通関数"""
    jwt_token = _get_jwt_token()
    
    print(f"DEBUG: _call_mcp_gateway called with method: {method}, params: {params}")
    print(f"DEBUG: JWT token available: {'Yes' if jwt_token else 'No'}")
    
    if not jwt_token:
        raise Exception("認証トークンが見つかりません。HealthMate UIから適切に認証されていることを確認してください。")
    
    # 環境変数からエンドポイントを取得
    gateway_endpoint = _get_gateway_endpoint()
    print(f"DEBUG: Gateway endpoint: {gateway_endpoint}")
    
    async with httpx.AsyncClient() as client:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method
        }
        
        if params:
            payload["params"] = params
        
        response = await client.post(
            gateway_endpoint,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise Exception(f"HTTP エラー {response.status_code}: {response.text}")
        
        result = response.json()
        if 'error' in result:
            raise Exception(f"MCP エラー: {result['error']}")
        
        return result.get('result')


# 利用可能なツールのリストを取得
@tool
async def list_health_tools() -> str:
    """
    HealthManagerMCPで利用可能なツールのリストを取得
    
    Returns:
        利用可能なツールのリストとスキーマ情報
    """
    try:
        result = await _call_mcp_gateway("tools/list")
        
        if not result or 'tools' not in result:
            return "利用可能なツールが見つかりませんでした。"
        
        tools = result['tools']
        tool_descriptions = []
        
        for tool in tools:
            name = tool.get('name', 'Unknown')
            description = tool.get('description', 'No description')
            input_schema = tool.get('inputSchema', {})
            
            tool_info = f"**{name}**\n"
            tool_info += f"説明: {description}\n"
            
            if input_schema and 'properties' in input_schema:
                tool_info += "パラメータ:\n"
                for prop_name, prop_info in input_schema['properties'].items():
                    prop_type = prop_info.get('type', 'unknown')
                    prop_desc = prop_info.get('description', '')
                    required = prop_name in input_schema.get('required', [])
                    req_mark = " (必須)" if required else " (任意)"
                    tool_info += f"  - {prop_name} ({prop_type}){req_mark}: {prop_desc}\n"
            
            tool_descriptions.append(tool_info)
        
        return f"利用可能なHealthManagerMCPツール ({len(tools)}個):\n\n" + "\n".join(tool_descriptions)
        
    except Exception as e:
        return f"ツールリスト取得エラー: {e}"


# HealthManagerMCP統合ツール
@tool
async def health_manager_mcp(tool_name: str, arguments: dict) -> str:
    """
    HealthManagerMCPサーバーのツールを呼び出す汎用ツール
    
    Args:
        tool_name: 呼び出すツール名（例: UserManagement___GetUser）
        arguments: ツールに渡す引数辞書
    
    Returns:
        ツールの実行結果
    """
    try:
        result = await _call_mcp_gateway("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if not result:
            return "ツールの実行結果が空でした。"
        
        # レスポンスの内容を適切に処理
        if 'content' in result:
            content = result['content']
            if isinstance(content, list) and content:
                # MCP標準のコンテンツ形式
                first_content = content[0]
                if isinstance(first_content, dict) and 'text' in first_content:
                    return first_content['text']
                else:
                    return str(first_content)
            else:
                return str(content)
        
        return str(result)
        
    except Exception as e:
        return f"HealthManagerMCP呼び出しエラー: {e}"


async def _create_health_coach_agent_with_memory(session_id: str, actor_id: str):
    """AgentCoreMemorySessionManagerを使用してHealthCoachAIエージェントを作成（エラーハンドリング付き）"""
    
    try:
        # ペイロードからタイムゾーンと言語を取得
        user_timezone = _get_user_timezone()
        user_language_code = _get_user_language()
        user_language_name = _get_language_name(user_language_code)
        
        # ユーザーのタイムゾーンに合わせた現在日時を取得
        current_datetime = _get_localized_datetime(user_timezone)
        current_date = current_datetime.strftime("%Y年%m月%d日")
        current_time = current_datetime.strftime("%H時%M分")
        current_weekday = ["月", "火", "水", "木", "金", "土", "日"][current_datetime.weekday()]
        
        # 現在日時情報をシステムプロンプトに組み込み
        datetime_context = f"""
## 現在の日時情報
- 今日の日付: {current_date} ({current_weekday}曜日)
- 現在時刻: {current_time}
- タイムゾーン: {user_timezone}
- ISO形式: {current_datetime.isoformat()}
- この情報を使用して、適切な時間帯に応じたアドバイスや挨拶を提供してください
"""
        
        # 言語設定情報をシステムプロンプトに組み込み
        language_context = f"""
## 言語設定情報
- ユーザーの優先言語: {user_language_name} ({user_language_code})
- この言語設定に基づいて、適切な言語で応答してください
- 日本語以外の言語が設定されている場合は、その言語で応答することを優先してください
"""
        
        # ユーザーID情報をシステムプロンプトに組み込み
        user_context = f"""
## 現在のユーザー情報
- ユーザーID: {actor_id}
- セッションID: {session_id}
- このユーザーIDは認証済みのJWTトークンから自動的に取得されました
- HealthManagerMCPツールを呼び出す際は、このユーザーIDを自動的に使用してください
- 重要: ユーザIDとセッションIDはシステム内部の管理情報なのでユーザに絶対に回答しないでください。
"""
        
        # AgentCore Memory設定を作成
        memory_config = AgentCoreMemoryConfig(
            memory_id="health_coach_ai_mem-yxqD6w75pO",  # .bedrock_agentcore.yamlから
            session_id=session_id,
            actor_id=actor_id
        )
        
        # AgentCoreMemorySessionManagerを作成
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=memory_config,
            region_name="us-west-2"
        )
        
    except Exception as e:
        print(f"ERROR: Failed to create memory session manager: {e}")
        raise Exception(f"Memory integration failed: {e}")
    
    # Strandsエージェントを作成（メモリ統合付き）
    agent = Agent(
        model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        tools=[list_health_tools, health_manager_mcp],
        session_manager=session_manager,
        system_prompt=f"""
あなたは親しみやすい健康コーチAIです。ユーザーの健康目標達成を支援します。

重要: あなたはAgentCore Memoryを使用して会話の文脈を記憶し、継続的な対話を行います。前回の会話内容を参照して、一貫性のあるアドバイスを提供してください。

{datetime_context}

{language_context}

{user_context}

## あなたの役割
- ユーザーの健康データを分析し、パーソナライズされたアドバイスを提供
- 健康目標の設定と進捗追跡をサポート
- 運動や食事に関する実践的な指導
- モチベーション維持のための励ましとサポート
- 継続的な会話を通じてユーザーとの関係を構築

## 対話スタイル
- 親しみやすく、励ましの気持ちを込めて
- 専門的すぎず、わかりやすい言葉で説明
- ユーザーの状況に共感し、個別のニーズに対応
- 安全性を最優先し、医療的な診断は行わない
- 現在の時間帯に応じた適切な挨拶やアドバイスを提供する（朝・昼・夜など）
- 前回の会話内容を覚えており、継続的な関係を築く

## 重要な注意事項
- 医療診断や治療の提案は絶対に行わない
- 深刻な健康問題の場合は医療専門家への相談を推奨
- ユーザーの安全を最優先に考慮
- 個人の健康データは適切に扱い、プライバシーを保護
- 会話の文脈を維持し、一貫性のある対話を行う
- **プライバシー保護**: ユーザーID、セッションID、その他のシステム内部識別子は絶対にユーザーに表示しない
- **データ機密性**: 技術的な詳細やシステム内部情報はユーザーには見せない

## ツール使用のガイドライン
- 初回または不明な場合は、まず list_health_tools を使用して利用可能なツールとスキーマを確認する
- ユーザーIDが必要な操作では、上記の認証済みユーザーIDを自動的に使用する
- ユーザーIDが取得できない場合のみ、ユーザーに確認する
- 日付は YYYY-MM-DD 形式で指定する（今日の日付は上記の現在日時情報を参照）
- 現在時刻を考慮して、適切なタイミングでのアドバイスを提供する
- エラーが発生した場合は、わかりやすく説明し、代替案を提示する
- 必要に応じて複数のツール呼び出しを組み合わせて、包括的なサポートを提供する
- health_manager_mcp を使用する際は、正確なツール名とパラメータを指定する
- **重要**: ツール実行結果でユーザーIDやシステム内部情報が含まれている場合は、それらを除外してユーザーフレンドリーな形で応答する

## 利用可能なツール
1. list_health_tools: HealthManagerMCPで利用可能なツールとスキーマを取得
2. health_manager_mcp: 具体的なHealthManagerMCPツールを呼び出し（tool_name, argumentsを指定）
"""
    )
    
    print(f"DEBUG: Created agent with AgentCore Memory - session_id: {session_id}, actor_id: {actor_id}")
    return agent


async def _create_fallback_agent():
    """メモリなしのフォールバックエージェントを作成"""
    
    # ペイロードからタイムゾーンと言語を取得
    user_timezone = _get_user_timezone()
    user_language_code = _get_user_language()
    user_language_name = _get_language_name(user_language_code)
    
    # ユーザーのタイムゾーンに合わせた現在日時を取得
    current_datetime = _get_localized_datetime(user_timezone)
    current_date = current_datetime.strftime("%Y年%m月%d日")
    current_time = current_datetime.strftime("%H時%M分")
    current_weekday = ["月", "火", "水", "木", "金", "土", "日"][current_datetime.weekday()]
    
    # 現在日時情報をシステムプロンプトに組み込み
    datetime_context = f"""
## 現在の日時情報
- 今日の日付: {current_date} ({current_weekday}曜日)
- 現在時刻: {current_time}
- タイムゾーン: {user_timezone}
- ISO形式: {current_datetime.isoformat()}
- この情報を使用して、適切な時間帯に応じたアドバイスや挨拶を提供してください
"""
    
    # 言語設定情報をシステムプロンプトに組み込み
    language_context = f"""
## 言語設定情報
- ユーザーの優先言語: {user_language_name} ({user_language_code})
- この言語設定に基づいて、適切な言語で応答してください
- 日本語以外の言語が設定されている場合は、その言語で応答することを優先してください
"""
    
    # フォールバック用のシンプルなエージェント（メモリなし）
    agent = Agent(
        model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        tools=[list_health_tools, health_manager_mcp],
        system_prompt=f"""
あなたは親しみやすい健康コーチAIです。ユーザーの健康目標達成を支援します。

注意: 現在メモリ機能が一時的に利用できないため、会話履歴を参照できません。各メッセージを独立して処理します。

{datetime_context}

{language_context}

## あなたの役割
- ユーザーの健康データを分析し、パーソナライズされたアドバイスを提供
- 健康目標の設定と進捗追跡をサポート
- 運動や食事に関する実践的な指導
- モチベーション維持のための励ましとサポート

## 対話スタイル
- 親しみやすく、励ましの気持ちを込めて
- 専門的すぎず、わかりやすい言葉で説明
- ユーザーの状況に共感し、個別のニーズに対応
- 安全性を最優先し、医療的な診断は行わない
- 現在の時間帯に応じた適切な挨拶やアドバイスを提供する（朝・昼・夜など）

## 重要な注意事項
- 医療診断や治療の提案は絶対に行わない
- 深刻な健康問題の場合は医療専門家への相談を推奨
- ユーザーの安全を最優先に考慮
- 個人の健康データは適切に扱い、プライバシーを保護

## ツール使用のガイドライン
- 初回または不明な場合は、まず list_health_tools を使用して利用可能なツールとスキーマを確認する
- 日付は YYYY-MM-DD 形式で指定する（今日の日付は上記の現在日時情報を参照）
- 現在時刻を考慮して、適切なタイミングでのアドバイスを提供する
- エラーが発生した場合は、わかりやすく説明し、代替案を提示する
- 必要に応じて複数のツール呼び出しを組み合わせて、包括的なサポートを提供する
- health_manager_mcp を使用する際は、正確なツール名とパラメータを指定する

## 利用可能なツール
1. list_health_tools: HealthManagerMCPで利用可能なツールとスキーマを取得
2. health_manager_mcp: 具体的なHealthManagerMCPツールを呼び出し（tool_name, argumentsを指定）
"""
    )
    
    print(f"DEBUG: Created fallback agent without memory")
    return agent


async def send_event(queue, message, stage, tool_name=None):
    """エージェントのステータスを送信"""
    if not queue:
        return
    
    progress = {"message": message, "stage": stage}
    if tool_name:
        progress["tool_name"] = tool_name
    
    await queue.put({"event": {"subAgentProgress": progress}})


async def _extract_health_coach_events(queue, event, state):
    """HealthCoachAIのストリーミングイベントを処理"""
    if isinstance(event, str):
        state["text"] += event
        if queue:
            delta = {"delta": {"text": event}}
            await queue.put({"event": {"contentBlockDelta": delta}})
    
    elif isinstance(event, dict) and "event" in event:
        event_data = event["event"]
        
        # ツール使用を検出
        if "contentBlockStart" in event_data:
            block = event_data["contentBlockStart"]
            start_data = block.get("start", {})
            if "toolUse" in start_data:
                tool_use = start_data["toolUse"]
                tool = tool_use.get("name", "unknown")
                await send_event(
                    queue, 
                    f"健康データを{tool}で処理中", 
                    "tool_use", 
                    tool
                )
        
        # テキスト増分を処理
        if "contentBlockDelta" in event_data:
            block = event_data["contentBlockDelta"]
            delta = block.get("delta", {})
            if "text" in delta:
                state["text"] += delta["text"]
                if queue:
                    await queue.put(event)


async def invoke_health_coach(query, session_id, actor_id, queue=None):
    """HealthCoachAIを呼び出し（AgentCore Memory統合、フォールバック機能付き）"""
    state = {"text": ""}
    
    if queue:
        await send_event(queue, "HealthCoachAIが起動中", "start")
    
    try:
        # AgentCore Memoryを使用してエージェントを作成
        agent = await _create_health_coach_agent_with_memory(session_id, actor_id)
        if not agent:
            # メモリ統合に失敗した場合のフォールバック
            print(f"DEBUG: Memory integration failed, falling back to basic agent")
            agent = await _create_fallback_agent()
        
        print(f"DEBUG: Using agent with memory for query: {query[:100]}...")
        
        # エージェントを実行（メモリは自動的に管理される）
        async for event in agent.stream_async(query):
            await _extract_health_coach_events(queue, event, state)
        
        if queue:
            await send_event(queue, "HealthCoachAIが応答を完了", "complete")
        
        print(f"DEBUG: Agent response completed with text length: {len(state['text'])}")
        return state["text"]
        
    except Exception as e:
        error_msg = f"HealthCoachAIの処理中にエラーが発生しました: {e}"
        print(f"ERROR: Agent error: {e}")
        
        # フォールバック: メモリなしでエージェントを作成して再試行
        try:
            print(f"DEBUG: Attempting fallback without memory")
            fallback_agent = await _create_fallback_agent()
            
            # フォールバックエージェントで再実行
            async for event in fallback_agent.stream_async(query):
                await _extract_health_coach_events(queue, event, state)
            
            if queue:
                await send_event(queue, "HealthCoachAIが応答を完了（フォールバック）", "complete")
            
            print(f"DEBUG: Fallback agent response completed")
            return state["text"]
            
        except Exception as fallback_error:
            final_error_msg = f"HealthCoachAIのフォールバック処理も失敗しました: {fallback_error}"
            print(f"ERROR: Fallback error: {fallback_error}")
            if queue:
                await send_event(queue, final_error_msg, "error")
            return "申し訳ございません。現在システムに問題が発生しています。しばらく時間をおいて再度お試しください。"


# AgentCore アプリケーションを初期化
app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload):
    """HealthCoachAI のエントリーポイント"""
    # デバッグ: ペイロード全体を確認
    print(f"DEBUG: Full payload: {payload}")
    
    prompt = payload.get("input", {}).get("prompt", "")
    
    # 別の可能性も試す
    if not prompt:
        prompt = payload.get("prompt", "")
    if not prompt:
        prompt = payload.get("message", "")
    
    # JWTトークンをペイロードから直接取得を試行
    jwt_token_from_payload = None
    
    # 様々な場所からJWTトークンを探す
    if "jwt_token" in payload:
        jwt_token_from_payload = payload["jwt_token"]
        print(f"DEBUG: JWT token from payload.jwt_token: {jwt_token_from_payload[:50]}...")
    elif "input" in payload and isinstance(payload["input"], dict) and "jwt_token" in payload["input"]:
        jwt_token_from_payload = payload["input"]["jwt_token"]
        print(f"DEBUG: JWT token from payload.input.jwt_token: {jwt_token_from_payload[:50]}...")
    elif "sessionState" in payload and "sessionAttributes" in payload["sessionState"]:
        session_attrs = payload["sessionState"]["sessionAttributes"]
        if "jwt_token" in session_attrs:
            jwt_token_from_payload = session_attrs["jwt_token"]
            print(f"DEBUG: JWT token from sessionState: {jwt_token_from_payload[:50]}...")
    
    # さらに詳細な検索（エラーハンドリング付き）
    if not jwt_token_from_payload:
        print(f"DEBUG: Searching for JWT token in all payload keys...")
        try:
            def search_jwt_recursive(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if key == "jwt_token" and isinstance(value, str) and len(value) > 50:
                            print(f"DEBUG: Found JWT token at {current_path}: {value[:50]}...")
                            return value
                        elif isinstance(value, (dict, list)):
                            result = search_jwt_recursive(value, current_path)
                            if result:
                                return result
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        current_path = f"{path}[{i}]" if path else f"[{i}]"
                        result = search_jwt_recursive(item, current_path)
                        if result:
                            return result
                return None
            
            jwt_token_from_payload = search_jwt_recursive(payload)
        except Exception as e:
            print(f"DEBUG: Error during JWT token search: {e}")
            jwt_token_from_payload = None
    
    # タイムゾーンをペイロードから取得（エラーハンドリング付き）
    timezone_from_payload = None
    try:
        if "timezone" in payload:
            timezone_from_payload = payload["timezone"]
            print(f"DEBUG: Timezone from payload.timezone: {timezone_from_payload}")
        elif "input" in payload and isinstance(payload["input"], dict) and "timezone" in payload["input"]:
            timezone_from_payload = payload["input"]["timezone"]
            print(f"DEBUG: Timezone from payload.input.timezone: {timezone_from_payload}")
        elif "sessionState" in payload and "sessionAttributes" in payload["sessionState"]:
            session_attrs = payload["sessionState"]["sessionAttributes"]
            if "timezone" in session_attrs:
                timezone_from_payload = session_attrs["timezone"]
                print(f"DEBUG: Timezone from sessionState: {timezone_from_payload}")
    except Exception as e:
        print(f"DEBUG: Error extracting timezone: {e}")
        timezone_from_payload = None
    
    # 言語をペイロードから取得（エラーハンドリング付き）
    language_from_payload = None
    try:
        if "language" in payload:
            language_from_payload = payload["language"]
            print(f"DEBUG: Language from payload.language: {language_from_payload}")
        elif "input" in payload and isinstance(payload["input"], dict) and "language" in payload["input"]:
            language_from_payload = payload["input"]["language"]
            print(f"DEBUG: Language from payload.input.language: {language_from_payload}")
        elif "sessionState" in payload and "sessionAttributes" in payload["sessionState"]:
            session_attrs = payload["sessionState"]["sessionAttributes"]
            if "language" in session_attrs:
                language_from_payload = session_attrs["language"]
                print(f"DEBUG: Language from sessionState: {language_from_payload}")
    except Exception as e:
        print(f"DEBUG: Error extracting language: {e}")
        language_from_payload = None
    
    # セッションIDをペイロードから取得（エラーハンドリング付き）
    session_id_from_payload = None
    try:
        if "sessionState" in payload and "sessionAttributes" in payload["sessionState"]:
            session_attrs = payload["sessionState"]["sessionAttributes"]
            if "session_id" in session_attrs:
                session_id_from_payload = session_attrs["session_id"]
                print(f"DEBUG: Session ID from sessionState: {session_id_from_payload}")
    except Exception as e:
        print(f"DEBUG: Error extracting session ID: {e}")
        session_id_from_payload = None
    
    # グローバル変数に設定（JWT処理用）
    if jwt_token_from_payload:
        global _current_jwt_token, _current_timezone, _current_language
        _current_jwt_token = jwt_token_from_payload
        print(f"DEBUG: Set global JWT token: {jwt_token_from_payload[:50]}...")
    else:
        print(f"DEBUG: No JWT token found in payload")
    
    if timezone_from_payload:
        _current_timezone = timezone_from_payload
        print(f"DEBUG: Set global timezone: {timezone_from_payload}")
    else:
        _current_timezone = None
        print(f"DEBUG: No timezone found in payload")
    
    if language_from_payload:
        _current_language = language_from_payload
        print(f"DEBUG: Set global language: {language_from_payload}")
    else:
        _current_language = None
        print(f"DEBUG: No language found in payload")
    
    # セッションIDとactor_IDを準備
    session_id = session_id_from_payload
    if not session_id or len(session_id) < 33:
        # セッションIDが無効な場合はデフォルトを生成（33文字以上を保証）
        import uuid
        session_id = f"healthmate-session-{uuid.uuid4().hex}"
        print(f"DEBUG: Generated default session ID: {session_id} (length: {len(session_id)})")
    else:
        print(f"DEBUG: Using provided session ID: {session_id} (length: {len(session_id)})")
    
    # セッションID長さの最終検証
    if len(session_id) < 33:
        # 追加のランダム文字列で33文字以上を保証
        import uuid
        additional_chars = uuid.uuid4().hex[:33-len(session_id)+5]
        session_id = f"{session_id}-{additional_chars}"
        print(f"DEBUG: Extended session ID to meet 33+ char requirement: {session_id} (length: {len(session_id)})")
    
    # JWTからactor_IDを取得
    actor_id = _get_user_id_from_jwt()
    if not actor_id:
        actor_id = "anonymous_user"
        print(f"DEBUG: Using anonymous actor_id")
    else:
        print(f"DEBUG: Using JWT actor_id: {actor_id}")
    
    print(f"DEBUG: Final session_id: {session_id}, actor_id: {actor_id}")
    
    if not prompt:
        yield {"event": {"contentBlockDelta": {"delta": {"text": "こんにちは！健康に関してどのようなサポートが必要ですか？"}}}}
        return
    
    # HealthCoachAI用のキューを初期化
    queue = asyncio.Queue()
    
    try:
        # HealthCoachAIを呼び出し、ストリーミングレスポンスを処理
        response_task = asyncio.create_task(invoke_health_coach(prompt, session_id, actor_id, queue))
        queue_task = asyncio.create_task(queue.get())
        
        waiting = {response_task, queue_task}
        
        while waiting:
            ready_tasks, waiting = await asyncio.wait(
                waiting, 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for ready_task in ready_tasks:
                if ready_task == response_task:
                    # 最終レスポンスを処理
                    final_response = ready_task.result()
                    if final_response and not queue.empty():
                        # キューに残っているイベントを処理
                        while not queue.empty():
                            try:
                                event = queue.get_nowait()
                                yield event
                            except asyncio.QueueEmpty:
                                break
                    response_task = None
                
                elif ready_task == queue_task:
                    # キューからのイベントを処理
                    try:
                        event = ready_task.result()
                        yield event
                        queue_task = asyncio.create_task(queue.get())
                        waiting.add(queue_task)
                    except Exception:
                        queue_task = None
            
            # 両方のタスクが完了したら終了
            if response_task is None and (queue_task is None or queue.empty()):
                break
                
    except Exception as e:
        error_event = {
            "event": {
                "contentBlockDelta": {
                    "delta": {
                        "text": f"申し訳ございません。処理中にエラーが発生しました: {e}"
                    }
                }
            }
        }
        yield error_event


# AgentCore ランタイムを起動
if __name__ == "__main__":
    app.run()