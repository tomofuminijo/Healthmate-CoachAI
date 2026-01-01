"""
Healthmate-CoachAI エージェント

Amazon Bedrock AgentCore Runtime上で動作する健康支援AIエージェントです。
環境別設定に対応しています。
"""

import os
import sys
import asyncio
import httpx
import json
import base64
import logging
from datetime import datetime
import pytz
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from healthmate_coach_ai.m2m_auth_config import M2MAuthConfig
from healthmate_coach_ai.prompt_loader import format_system_prompt
from fastapi.middleware.cors import CORSMiddleware


# EHALTHMATE_ENV 取得
env = os.environ.get('HEALTHMATE_ENV', 'dev').lower()

# ログ設定
log_level_env = os.environ.get('HEALTHMATE_LOG_LEVEL', '').upper()
if log_level_env == 'DEBUG':
    log_level = logging.DEBUG
elif log_level_env == 'INFO':
    log_level = logging.INFO
elif log_level_env == 'WARNING':
    log_level = logging.WARNING
elif log_level_env == 'ERROR':
    log_level = logging.ERROR
else:
    # HEALTHMATE_LOG_LEVELが未設定または無効な場合のフォールバック
    if env == 'prod':
        log_level = logging.WARNING
    elif env == 'stage':
        log_level = logging.INFO
    else:  # dev
        log_level = logging.DEBUG

# ロガーの初期化
logger = logging.getLogger('HealthCoachAI')
logger.setLevel(log_level)

# 標準出力へのハンドラを追加（これがCloudWatch Logsに転送されます）
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

logger.propagate = False

# 環境情報をログに出力
logger.info(f"CoachAI starting in {env} environment")
logger.info(f"log_level: {logging.getLevelName(log_level)}")
logger.info(f"AWS Region: {os.environ.get('AWS_REGION', 'us-west-2')}")


# M2M認証用デコレータのインポート
try:
    from bedrock_agentcore.identity.auth import requires_access_token
except ImportError:
    def requires_access_token(**kwargs):
        def decorator(func):
            return func
        return decorator


# 環境変数とユーティリティ関数
def _get_gateway_endpoint() -> str:
    """Gateway エンドポイントを環境変数から取得"""
    gateway_id = os.environ.get('HEALTHMANAGER_GATEWAY_ID')
    if not gateway_id:
        raise Exception("環境変数 HEALTHMANAGER_GATEWAY_ID が設定されていません")
    
    region = os.environ.get('AWS_REGION', 'us-west-2')
    return f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp"


def _validate_required_environment_variables():
    """必須環境変数の存在を事前に検証"""
    required_vars = ['AGENTCORE_PROVIDER_NAME', 'HEALTHMANAGER_GATEWAY_ID']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        raise Exception(f"必須環境変数が設定されていません: {', '.join(missing_vars)}")


# グローバル変数とM2M認証設定
_current_jwt_token = None
_current_timezone = None
_current_language = None

# M2M認証設定の初期化
_validate_required_environment_variables()
_m2m_auth_config = M2MAuthConfig.from_environment()
_M2M_PROVIDER_NAME = _m2m_auth_config.provider_name
_M2M_SCOPES = [_m2m_auth_config.cognito_scope]


@requires_access_token(
    provider_name=_M2M_PROVIDER_NAME,
    scopes=_M2M_SCOPES,
    auth_flow="M2M",
    force_authentication=False,
)
def get_mcp_client_from_gateway(access_token: str):
    """M2M認証を使用してMCPクライアントを作成"""
    if not access_token:
        raise Exception("@requires_access_tokenデコレータからアクセストークンが提供されませんでした")
    
    return {
        "gateway_endpoint": _get_gateway_endpoint(),
        "access_token": access_token
    }


# JWT Token ヘルパー関数（ユーザー識別専用）
def _decode_jwt_payload(jwt_token: str) -> dict:
    """JWTトークンのペイロードをデコード（署名検証なし）"""
    try:
        parts = jwt_token.split('.')
        if len(parts) != 3:
            return {}
        
        payload = parts[1]
        padding = 4 - (len(payload) % 4)
        if padding != 4:
            payload += '=' * padding
        
        decoded_bytes = base64.urlsafe_b64decode(payload)
        return json.loads(decoded_bytes.decode('utf-8'))
    except Exception:
        return {}


def _get_user_info():
    """現在のユーザー情報を取得"""
    global _current_jwt_token, _current_timezone, _current_language
    
    user_id = None
    if _current_jwt_token:
        payload = _decode_jwt_payload(_current_jwt_token)
        user_id = payload.get('sub')
    
    return {
        'user_id': user_id,
        'timezone': _current_timezone or 'Asia/Tokyo',
        'language': _current_language or 'ja'
    }


def _get_localized_datetime(timezone_str: str = 'Asia/Tokyo'):
    """指定されたタイムゾーンでの現在日時を取得"""
    try:
        user_timezone = pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        user_timezone = pytz.timezone('Asia/Tokyo')
    
    return datetime.now(pytz.UTC).astimezone(user_timezone)


async def _call_mcp_gateway_with_m2m(method: str, params: dict = None):
    """M2M認証を使用してMCP Gatewayを呼び出す関数"""
    mcp_client_config = get_mcp_client_from_gateway()
    return await _call_mcp_gateway(method, params, mcp_client_config['access_token'])


async def _call_mcp_gateway(method: str, params: dict = None, access_token: str = None):
    """MCP Gatewayを呼び出す共通関数（M2M認証専用）"""
    if not access_token:
        raise Exception("M2M認証アクセストークンが必要です。")
    
    gateway_endpoint = _get_gateway_endpoint()
    
    async with httpx.AsyncClient() as client:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params:
            payload["params"] = params
        
        response = await client.post(
            gateway_endpoint,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30.0
        )
        
        if response.status_code == 401:
            raise Exception("MCP Gateway認証エラー: M2M認証トークンが無効です。")
        elif response.status_code == 403:
            raise Exception("MCP Gateway認可エラー: 必要な権限がありません。")
        elif response.status_code == 404:
            raise Exception("MCP Gateway接続エラー: HealthManager MCPサービスが見つかりません。")
        elif response.status_code >= 500:
            raise Exception(f"MCP Gatewayサーバーエラー: 内部エラーが発生しました。")
        elif response.status_code != 200:
            raise Exception(f"HTTP エラー {response.status_code}: {response.text}")
        
        result = response.json()
        if 'error' in result:
            raise Exception(f"MCP プロトコルエラー: {result['error']}")
        
        return result.get('result')


# HealthManagerMCP統合ツール
@tool
async def list_health_tools() -> str:
    """HealthManagerMCPで利用可能なツールのリストを取得（ページング対応）"""
    try:
        all_tools = []
        cursor = None
        page_count = 0
        
        # nextCursorがnullになるまで全てのページを取得
        while True:
            page_count += 1
            logger.debug(f"ツールリスト取得 - ページ {page_count}, cursor: {cursor}")
            
            # ページング用のパラメータを設定
            params = {}
            if cursor:
                params["cursor"] = cursor
            
            result = await _call_mcp_gateway_with_m2m("tools/list", params)
            
            if not result:
                logger.warning("MCP Gateway からの応答が空です")
                break
            
            # 現在のページのツールを追加
            if 'tools' in result:
                current_tools = result['tools']
                all_tools.extend(current_tools)
                logger.debug(f"ページ {page_count}: {len(current_tools)}個のツールを取得")
            
            # nextCursorをチェック
            next_cursor = result.get('nextCursor')
            if not next_cursor:
                logger.debug("nextCursorがnull - ページング完了")
                break
            
            cursor = next_cursor
            
            # 無限ループ防止（最大10ページ）
            if page_count >= 10:
                logger.warning("ページング制限に達しました（最大10ページ）")
                break
        
        if not all_tools:
            return "利用可能なツールが見つかりませんでした。"
        
        logger.info(f"合計 {len(all_tools)}個のツールを {page_count}ページから取得しました")
        
        # ツール情報を整形
        tool_descriptions = []
        for tool in all_tools:
            name = tool.get('name', 'Unknown')
            description = tool.get('description', 'No description')
            input_schema = tool.get('inputSchema', {})
            
            tool_info = f"**{name}**\n説明: {description}\n"
            
            if input_schema and 'properties' in input_schema:
                tool_info += "パラメータ:\n"
                for prop_name, prop_info in input_schema['properties'].items():
                    prop_type = prop_info.get('type', 'unknown')
                    prop_desc = prop_info.get('description', '')
                    required = prop_name in input_schema.get('required', [])
                    req_mark = " (必須)" if required else " (任意)"
                    tool_info += f"  - {prop_name} ({prop_type}){req_mark}: {prop_desc}\n"
            
            tool_descriptions.append(tool_info)
        
        return f"利用可能なHealthManagerMCPツール ({len(all_tools)}個、{page_count}ページから取得):\n\n" + "\n".join(tool_descriptions)
        
    except Exception as e:
        logger.error(f"ツールリスト取得エラー: {e}")
        return f"ツールリスト取得エラー: {e}"


@tool
async def health_manager_mcp(tool_name: str, arguments: dict) -> str:
    """HealthManagerMCPサーバーのツールを呼び出す汎用ツール"""
    try:
        result = await _call_mcp_gateway_with_m2m("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if not result:
            return "ツールの実行結果が空でした。"
        
        # レスポンスの内容を適切に処理
        if 'content' in result:
            content = result['content']
            if isinstance(content, list) and content:
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
    """AgentCoreMemorySessionManagerを使用してHealthmate-CoachAIエージェントを作成（環境別対応）"""
    
    # ユーザー情報を取得
    user_info = _get_user_info()
    current_datetime = _get_localized_datetime(user_info['timezone'])
    
    # 日時情報をフォーマット
    current_date = current_datetime.strftime("%Y年%m月%d日")
    current_time = current_datetime.strftime("%H時%M分")
    current_weekday = ["月", "火", "水", "木", "金", "土", "日"][current_datetime.weekday()]
    
    # 環境変数からメモリーIDを取得（必須）
    memory_id = os.environ.get('BEDROCK_AGENTCORE_MEMORY_ID')
    if not memory_id:
        raise Exception("環境変数 BEDROCK_AGENTCORE_MEMORY_ID が設定されていません。deploy_to_aws.shを使用してデプロイしてください。")
    
    logger.debug(f"使用するメモリID: {memory_id}")
    
    # セッションIDの長さを検証
    if len(session_id) < 33:
        raise Exception(f"Session ID が短すぎます（{len(session_id)}文字、33文字以上が必要）")
    
    # AgentCore Memory設定を作成
    memory_config = AgentCoreMemoryConfig(
        memory_id=memory_id,
        session_id=session_id,
        actor_id=actor_id,
        # 長期メモリ戦略
        retrieval_config={ 
            "/healthmate/userpreferences/actors/{actorId}": RetrievalConfig(
                top_k=5,
                relevance_score=0.7
            ),
            "/healthmate/semantics/actors/{actorId}": RetrievalConfig(
                top_k=10,
                relevance_score=0.7
            ),
            "/healthmate/summaries/actors/{actorId}/sessions/": RetrievalConfig(
                top_k=5,
                relevance_score=0.6
            ),
            "/healthmate/episodes/actors/{actorId}/sessions/": RetrievalConfig(
                top_k=5,             
                relevance_score=0.6  
            ),
            "/healthmate/episodes/actors/{actorId}": RetrievalConfig(
                top_k=3,             
                relevance_score=0.75 
            )
        }
    )
    
    # AgentCoreMemorySessionManagerを作成
    session_manager = AgentCoreMemorySessionManager(
        agentcore_memory_config=memory_config,
        region_name=os.environ.get('AWS_REGION', 'us-west-2')
    )
    
    # システムプロンプト（環境別ファイルから読み込み）
    try:
        system_prompt = format_system_prompt(
            environment=env,
            current_date=current_date,
            current_weekday=current_weekday,
            current_time=current_time,
            timezone=user_info['timezone'],
            language=user_info['language'],
            actor_id=actor_id
        )
        logger.debug(f"システムプロンプト読み込み完了: {env}環境 ({len(system_prompt)}文字)")
    except Exception as e:
        logger.error(f"システムプロンプト読み込みエラー: {e}")
        raise Exception(f"システムプロンプトの読み込みに失敗しました: {e}")
    
    # 環境変数からモデル識別子を取得
    model_id = os.environ.get('HEALTHMATE_AI_MODEL')
    if not model_id:
        raise Exception("環境変数 HEALTHMATE_AI_MODEL が設定されていません")
    
    # 使用するモデルをログに出力
    logger.debug(f"system_prompt: {system_prompt}")
    logger.info(f"model_id: {model_id}")
    
    # Strandsエージェントを作成（メモリ統合付き）
    return Agent(
        model=model_id,
        tools=[list_health_tools, health_manager_mcp],
        session_manager=session_manager,
        system_prompt=system_prompt
    )





async def send_event(queue, message, stage, tool_name=None):
    """エージェントのステータスを送信"""
    if queue:
        progress = {"message": message, "stage": stage}
        if tool_name:
            progress["tool_name"] = tool_name
        await queue.put({"event": {"subAgentProgress": progress}})


async def _extract_health_coach_events(queue, event, state):
    """HealthCoachAIのストリーミングイベントを処理"""
    if isinstance(event, str):
        state["text"] += event
        if queue:
            await queue.put({"event": {"contentBlockDelta": {"delta": {"text": event}}}})
    
    elif isinstance(event, dict) and "event" in event:
        event_data = event["event"]
        
        # ツール使用を検出
        if "contentBlockStart" in event_data:
            block = event_data["contentBlockStart"]
            start_data = block.get("start", {})
            if "toolUse" in start_data:
                tool_use = start_data["toolUse"]
                tool = tool_use.get("name", "unknown")
                await send_event(queue, f"健康データを{tool}で処理中", "tool_use", tool)
        
        # テキスト増分を処理
        if "contentBlockDelta" in event_data:
            block = event_data["contentBlockDelta"]
            delta = block.get("delta", {})
            if "text" in delta:
                state["text"] += delta["text"]
                if queue:
                    await queue.put(event)


async def invoke_health_coach(query, session_id, actor_id, queue=None):
    """Healthmate-CoachAIを呼び出し（AgentCore Memory統合必須）"""
    state = {"text": ""}
    
    if queue:
        await send_event(queue, "Healthmate-CoachAIが起動中", "start")
    
    try:
        # AgentCore Memoryを使用してエージェントを作成
        agent = await _create_health_coach_agent_with_memory(session_id, actor_id)
        
        # エージェントを実行（メモリは自動的に管理される）
        async for event in agent.stream_async(query):
            await _extract_health_coach_events(queue, event, state)
        
        if queue:
            await send_event(queue, "Healthmate-CoachAIが応答を完了", "complete")
        
        return state["text"]
        
    except Exception as e:
        error_msg = f"AgentCore Memory統合エラー: {e}"
        if queue:
            await send_event(queue, error_msg, "error")
        raise Exception(f"AgentCore Memoryが利用できません。システム管理者に連絡してください。詳細: {e}")


# AgentCore アプリケーションを初期化
app = BedrockAgentCoreApp()

# Add CORS middleware to allow browser requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Customize in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.entrypoint
async def invoke(payload, context):
    """Healthmate-CoachAI のエントリーポイント"""
    logger.debug(f"app.entrypoint payload: {payload}")
    logger.debug(f"app.entrypoint context: {context}")

    # ペイロードからデータを抽出
    prompt = payload.get("prompt", "")
    
    # コンテキストから、Authヘッダーを抽出
    auth_header = context.request_headers.get('Authorization')

    # 必須フィールドの検証
    if not auth_header:
        yield {"event": {"contentBlockDelta": {"delta": {"text": "エラー: Authorizationヘッダーが必要です。"}}}}
        return

    # 必須フィールドを抽出
    jwt_token_from_context = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header
    session_id_from_context = context.session_id
    timezone_from_payload = payload.get("timezone", "Asia/Tokyo")
    language_from_payload = payload.get("language", "ja")
    
    # 必須フィールドの検証
    if not jwt_token_from_context:
        yield {"event": {"contentBlockDelta": {"delta": {"text": "エラー: JWT認証トークンが必要です。"}}}}
        return
    
    if not session_id_from_context or len(session_id_from_context) < 33:
        yield {"event": {"contentBlockDelta": {"delta": {"text": "エラー: 有効なセッションIDが必要です（33文字以上）。"}}}}
        return
    
    # グローバル変数を設定
    global _current_jwt_token, _current_timezone, _current_language
    _current_jwt_token = jwt_token_from_context
    _current_timezone = timezone_from_payload
    _current_language = language_from_payload
    
    # JWTからユーザーIDを抽出
    user_info = _get_user_info()
    actor_id = user_info['user_id']
    if not actor_id:
        yield {"event": {"contentBlockDelta": {"delta": {"text": "エラー: JWT トークンからユーザーIDを抽出できませんでした。"}}}}
        return
    
    # デフォルトメッセージ
    if not prompt:
        yield {"event": {"contentBlockDelta": {"delta": {"text": "こんにちは！健康に関してどのようなサポートが必要ですか？"}}}}
        return
    
    # HealthCoachAI用のキューを初期化
    queue = asyncio.Queue()
    
    try:
        # HealthCoachAIを呼び出し、ストリーミングレスポンスを処理
        response_task = asyncio.create_task(invoke_health_coach(prompt, session_id_from_context, actor_id, queue))
        
        # イベント処理ループ
        while True:
            # キューからイベントを取得（タイムアウト付き）
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                # レスポンスタスクが完了したかチェック
                if response_task.done():
                    # 残りのイベントを処理
                    while not queue.empty():
                        try:
                            event = queue.get_nowait()
                            yield event
                        except asyncio.QueueEmpty:
                            break
                    break
                continue
                
    except Exception as e:
        yield {"event": {"contentBlockDelta": {"delta": {"text": f"申し訳ございません。処理中にエラーが発生しました: {e}"}}}}


# AgentCore ランタイムを起動
if __name__ == "__main__":
    app.run()