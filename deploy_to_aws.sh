#!/bin/bash

# Healthmate-CoachAI エージェントをAWSにデプロイするスクリプト
# 環境別設定対応版 - HEALTHMATE_ENV環境変数に基づく環境別デプロイ

set -e  # エラー時に停止

echo "🚀 Healthmate-CoachAI エージェントをAWSにデプロイします（環境別設定対応）"
echo "================================================================================"

# 環境設定の初期化
setup_environment_config() {
    # HEALTHMATE_ENV環境変数の取得（デフォルト: dev）
    export HEALTHMATE_ENV=${HEALTHMATE_ENV:-dev}
    
    # 有効な環境値の検証
    case "$HEALTHMATE_ENV" in
        dev|stage|prod)
            echo "🌍 環境設定: $HEALTHMATE_ENV"
            ;;
        *)
            echo "❌ 無効な環境値: $HEALTHMATE_ENV"
            echo "   有効な値: dev, stage, prod"
            echo "   デフォルトのdev環境を使用します"
            export HEALTHMATE_ENV=dev
            ;;
    esac
    
    # ログレベル設定
    if [ -n "$HEALTHMATE_LOG_LEVEL" ]; then
        # HEALTHMATE_LOG_LEVEL環境変数が設定されている場合はその値を使用
        LOG_LEVEL="$HEALTHMATE_LOG_LEVEL"
        echo "🔧 ログレベル: $LOG_LEVEL (環境変数から設定)"
    else
        # HEALTHMATE_LOG_LEVEL環境変数が未設定の場合は、HEALTHMATE_ENVに基づいて自動設定
        case "$HEALTHMATE_ENV" in
            dev)
                LOG_LEVEL="DEBUG"
                ;;
            stage)
                LOG_LEVEL="WARNING"
                ;;
            prod)
                LOG_LEVEL="INFO"
                ;;
            *)
                LOG_LEVEL="INFO"
                ;;
        esac
        echo "🔧 ログレベル: $LOG_LEVEL (環境 $HEALTHMATE_ENV に基づいて自動設定)"
    fi
    
    # 環境別サフィックスの設定
    ENV_SUFFIX="-${HEALTHMATE_ENV}"
    
    echo "📋 環境設定:"
    echo "   🌍 環境: $HEALTHMATE_ENV"
    echo "   📊 ログレベル: $LOG_LEVEL"
    echo "   🏷️  サフィックス: $ENV_SUFFIX"
}

# AWS設定と認証情報の設定
setup_aws_credentials() {
    export AWS_DEFAULT_REGION=${AWS_REGION:-us-west-2}
    export AWS_REGION=$AWS_DEFAULT_REGION
    
    echo "🔐 AWS認証情報を設定中..."
    
    # AWS認証情報の有効性確認
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo "❌ AWS認証情報が無効です"
        echo "   以下のいずれかの方法でAWS認証を設定してください:"
        echo "   1. aws login (推奨)"
        echo "   2. aws configure (アクセスキー)"
        echo "   3. aws sso login (SSO)"
        exit 1
    fi
    
    echo "✅ AWS認証情報が有効です"
    
    # aws configure export-credentials を使用して認証情報を取得（aws login対応）
    if CREDS_OUTPUT=$(aws configure export-credentials --format env 2>/dev/null) && [ -n "$CREDS_OUTPUT" ]; then
        eval "$CREDS_OUTPUT"
        echo "   認証方式: aws login (一時的な認証情報)"
    else
        echo "   認証方式: 既存の設定を使用"
    fi
    
    # アカウントIDとロール設定（環境別対応）
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ROLE_NAME="Healthmate-CoachAI-AgentCore-Runtime-Role${ENV_SUFFIX}"
    CUSTOM_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
    
    echo "📍 リージョン: $AWS_REGION"
    echo "🏢 アカウントID: $ACCOUNT_ID"
    echo "🎭 カスタムロール: $CUSTOM_ROLE_ARN"
}

# 環境設定を実行
setup_environment_config

# AWS設定を実行
setup_aws_credentials

# カスタムIAMロールの存在確認
echo ""
echo "🔍 カスタムIAMロールの存在を確認中..."
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "✅ カスタムIAMロール '$ROLE_NAME' が存在します"
    
    # IAMロールのインラインポリシーを更新
    echo "🔄 IAMロールのインラインポリシーを最新版に更新中..."
    INLINE_POLICY_NAME="Healthmate-CoachAI-Runtime-Policy"
    
    # bedrock-agentcore-runtime-policy.jsonファイルの存在確認
    if [ ! -f "bedrock-agentcore-runtime-policy.json" ]; then
        echo "❌ bedrock-agentcore-runtime-policy.json ファイルが見つかりません"
        exit 1
    fi
    
    # インラインポリシーを更新（既存の場合は上書き）
    echo "📜 インラインポリシーを更新中..."
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$INLINE_POLICY_NAME" \
        --policy-document file://bedrock-agentcore-runtime-policy.json
    
    if [ $? -eq 0 ]; then
        echo "✅ インラインポリシー更新完了"
    else
        echo "❌ インラインポリシー更新に失敗しました"
        exit 1
    fi
else
    echo "❌ カスタムIAMロール '$ROLE_NAME' が見つかりません"
    echo "🔧 カスタムIAMロールを自動作成中..."
    
    # 環境別IAMロール作成のため、create_custom_iam_role.pyに環境変数を渡す
    HEALTHMATE_ENV="$HEALTHMATE_ENV" python3 create_custom_iam_role.py
    if [ $? -ne 0 ]; then
        echo "❌ カスタムIAMロール作成に失敗しました"
        exit 1
    fi
    echo "✅ カスタムIAMロール作成完了"
fi

# 仮想環境をアクティベート（存在する場合）
if [ -d ".venv" ]; then
    echo ""
    echo "🐍 仮想環境をアクティベート中..."
    source .venv/bin/activate
    echo "✅ 仮想環境アクティベート完了"
elif [ -d "venv" ]; then
    echo ""
    echo "🐍 仮想環境をアクティベート中..."
    source venv/bin/activate
    echo "✅ 仮想環境アクティベート完了"
else
    echo ""
    echo "⚠️  仮想環境が見つかりません。グローバル環境を使用します。"
fi

echo ""
echo "📦 依存関係を確認中..."
pip install -q --upgrade bedrock-agentcore strands-agents

echo ""
echo "🔧 AgentCore設定を更新中..."
echo "   カスタムIAMロールを使用: $CUSTOM_ROLE_ARN"

# CloudFormationから環境別Gateway IDを取得
echo ""
echo "🔍 Healthmate-HealthManagerスタックからGateway IDを取得中..."
STACK_NAME="Healthmate-HealthManagerStack${ENV_SUFFIX}"
GATEWAY_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`GatewayId`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$GATEWAY_ID" ] || [ "$GATEWAY_ID" = "None" ]; then
    echo "❌ CloudFormationスタック '$STACK_NAME' からGateway IDを取得できませんでした"
    echo "   スタックが存在し、GatewayId出力があることを確認してください"
    exit 1
fi

echo "✅ Gateway ID取得成功: $GATEWAY_ID"

# Cognito設定を環境別に取得
echo ""
echo "🔍 Healthmate-Coreスタックから認証設定を取得中..."
CORE_STACK_NAME="Healthmate-CoreStack${ENV_SUFFIX}"
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$CORE_STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$USER_POOL_ID" ] || [ "$USER_POOL_ID" = "None" ]; then
    echo "❌ CloudFormationスタック '$CORE_STACK_NAME' からUser Pool IDを取得できませんでした"
    echo "   スタックが存在し、UserPoolId出力があることを確認してください"
    exit 1
fi

echo "✅ User Pool ID取得成功: $USER_POOL_ID"

# JWT認証設定を作成
JWT_DISCOVERY_URL="https://cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration"
USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$CORE_STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$USER_POOL_CLIENT_ID" ] || [ "$USER_POOL_CLIENT_ID" = "None" ]; then
    echo "❌ CloudFormationスタック '$CORE_STACK_NAME' からUser Pool Client IDを取得できませんでした"
    echo "   スタックが存在し、UserPoolClientId出力があることを確認してください"
    exit 1
fi

AUTHORIZER_CONFIG="{\"customJWTAuthorizer\":{\"discoveryUrl\":\"${JWT_DISCOVERY_URL}\",\"allowedClients\":[\"${USER_POOL_CLIENT_ID}\"]}}"

echo "🔐 JWT認証設定:"
echo "   Discovery URL: $JWT_DISCOVERY_URL"
echo "   Allowed Clients: $USER_POOL_CLIENT_ID"

# 環境別プロバイダー名の生成
PROVIDER_NAME="healthmanager-oauth2-provider${ENV_SUFFIX}"
echo "🔗 AgentCore Provider Name: $PROVIDER_NAME"

# AgentCore設定でカスタムロールとJWT認証を指定（環境別対応）
echo ""
echo "🔧 AgentCore設定を実行中..."

# エージェント名の生成（ハイフンをアンダースコアに変換）
AGENT_NAME="healthmate_coach_ai_${HEALTHMATE_ENV}"
echo "🤖 エージェント名: $AGENT_NAME"

agentcore configure \
    --entrypoint agent/healthmate_coach_ai/agent.py \
    --requirements-file agent/requirements.txt \
    --name "$AGENT_NAME" \
    --execution-role "$CUSTOM_ROLE_ARN" \
    --deployment-type container \
    --ecr auto \
    --authorizer-config "$AUTHORIZER_CONFIG" \
    --request-header-allowlist "Authorization" \
    --non-interactive

echo ""
echo "🔍 更新された設定を確認中..."
cat .bedrock_agentcore.yaml

echo ""
echo "🚀 AgentCore デプロイを開始します..."
echo "   エージェント名: $AGENT_NAME"
echo "   エントリーポイント: healthmate_coach_ai/agent.py"
echo "   カスタムIAMロール: $CUSTOM_ROLE_ARN"
echo "   🔐 認証方式: JWT (Cognito)"
echo "   🔑 JWT Discovery URL: $JWT_DISCOVERY_URL"

# AIモデル設定
HEALTHMATE_AI_MODEL=${HEALTHMATE_AI_MODEL:-"global.anthropic.claude-haiku-4-5-20251001-v1:0"}
#HEALTHMATE_AI_MODEL=${HEALTHMATE_AI_MODEL:-"global.amazon.nova-2-lite-v1:0"}
#HEALTHMATE_AI_MODEL=${HEALTHMATE_AI_MODEL:-"global.anthropic.claude-sonnet-4-5-20250929-v1:0"}

echo ""
echo "🔍 デプロイ設定:"
echo "   ✅ HEALTHMANAGER_GATEWAY_ID: $GATEWAY_ID"
echo "   ✅ AWS_REGION: $AWS_REGION"
echo "   ✅ HEALTHMATE_AI_MODEL: $HEALTHMATE_AI_MODEL"
echo "   ✅ HEALTHMATE_ENV: $HEALTHMATE_ENV"
echo "   ✅ HEALTHMATE_LOG_LEVEL: $LOG_LEVEL"
echo "   ✅ AGENTCORE_PROVIDER_NAME: $PROVIDER_NAME"

# AgentCore デプロイを実行（環境変数追加）
echo ""
echo "🚀 AgentCore デプロイを開始..."
agentcore launch \
    --env HEALTHMANAGER_GATEWAY_ID="$GATEWAY_ID" \
    --env AWS_REGION="$AWS_REGION" \
    --env HEALTHMATE_AI_MODEL="$HEALTHMATE_AI_MODEL" \
    --env HEALTHMATE_ENV="$HEALTHMATE_ENV" \
    --env HEALTHMATE_LOG_LEVEL="$LOG_LEVEL" \
    --env AGENTCORE_PROVIDER_NAME="$PROVIDER_NAME"

echo ""
echo "✅ デプロイが完了しました！"
echo ""
echo "📋 デプロイ情報:"
echo "   🎭 IAMロール: $CUSTOM_ROLE_ARN"
echo "   📍 リージョン: $AWS_REGION"
echo "   🏢 アカウント: $ACCOUNT_ID"
echo "   🌍 環境: $HEALTHMATE_ENV"
echo "   🔐 認証方式: JWT (Cognito)"
echo "   🔑 JWT Discovery URL: $JWT_DISCOVERY_URL"
echo "   🤖 AIモデル: $HEALTHMATE_AI_MODEL"
echo "   � ロログレベル: $LOG_LEVEL"
echo "   🔗 プロバイダー名: $PROVIDER_NAME"
echo ""
echo "🚀 次のステップ:"
echo "   1. agentcore status でエージェント状態を確認"
echo "   2. python manual_test_deployed_agent.py でテスト実行"
echo "   3. HealthmateUI からエージェントを呼び出し"
echo ""
echo "💡 環境切り替え方法:"
echo "   export HEALTHMATE_ENV=stage && ./deploy_to_aws.sh"
echo "   export HEALTHMATE_ENV=prod && ./deploy_to_aws.sh"
echo ""
echo "💡 モデル変更方法:"
echo "   export HEALTHMATE_AI_MODEL=\"新しいモデル名\" && ./deploy_to_aws.sh"
echo ""
echo "💡 ログレベル変更方法:"
echo "   export HEALTHMATE_LOG_LEVEL=DEBUG && ./deploy_to_aws.sh"
echo "   export HEALTHMATE_LOG_LEVEL=WARNING && ./deploy_to_aws.sh"
echo ""