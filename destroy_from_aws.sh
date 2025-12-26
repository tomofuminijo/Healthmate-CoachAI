#!/bin/bash

# Healthmate-CoachAI エージェントをAWSからアンデプロイするスクリプト
# 環境別設定対応版 - HEALTHMATE_ENV環境変数に基づく環境別アンデプロイ

set -e  # エラー時に停止

# コマンドライン引数の解析
FORCE_DELETE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE_DELETE=true
            shift
            ;;
        --help|-h)
            echo "使用方法: $0 [OPTIONS]"
            echo ""
            echo "オプション:"
            echo "  --force, -f    確認をスキップして強制削除"
            echo "  --help, -h     このヘルプを表示"
            echo ""
            echo "環境変数:"
            echo "  HEALTHMATE_ENV    環境設定 (dev, stage, prod) デフォルト: dev"
            echo "  AWS_REGION        AWSリージョン デフォルト: us-west-2"
            echo ""
            echo "例:"
            echo "  $0                    # 通常の削除（確認あり）"
            echo "  $0 --force            # 強制削除（確認なし）"
            echo "  HEALTHMATE_ENV=stage $0 --force  # stage環境を強制削除"
            exit 0
            ;;
        *)
            echo "❌ 不明なオプション: $1"
            echo "ヘルプを表示するには --help を使用してください"
            exit 1
            ;;
    esac
done

echo "🗑️  Healthmate-CoachAI エージェントをAWSからアンデプロイします（環境別設定対応）"
echo "================================================================================"

if [ "$FORCE_DELETE" = true ]; then
    echo "🚨 --force フラグが指定されているため、すべての確認をスキップします"
fi

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
    
    # 環境別サフィックスの設定
    if [ "$HEALTHMATE_ENV" = "prod" ]; then
        ENV_SUFFIX=""
    else
        ENV_SUFFIX="-${HEALTHMATE_ENV}"
    fi
    
    echo "📋 環境設定:"
    echo "   🌍 環境: $HEALTHMATE_ENV"
    echo "   🏷️  サフィックス: $ENV_SUFFIX"
}

# 環境設定を実行
setup_environment_config

# AWS設定
export AWS_DEFAULT_REGION=${AWS_REGION:-us-west-2}
export AWS_REGION=$AWS_DEFAULT_REGION
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

echo "🔐 AWS設定を確認中..."
echo "📍 リージョン: $AWS_DEFAULT_REGION"
echo "🏢 アカウントID: $ACCOUNT_ID"

# AWS認証情報の確認
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ AWS認証情報が設定されていません。"
    echo "   以下のいずれかの方法でAWS認証を設定してください:"
    echo "   1. aws configure"
    echo "   2. 環境変数 (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)"
    echo "   3. IAMロール (EC2/Lambda等)"
    exit 1
fi

echo "✅ AWS認証情報確認完了"

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
    echo "⚠️  仮想環境が見つかりません。グローバル環境を使用します。"
fi

# bedrock-agentcore-controlがインストールされているか確認
if ! command -v aws &> /dev/null; then
    echo "❌ aws CLI が見つかりません。"
    echo "   以下のコマンドでインストールしてください:"
    echo "   https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# bedrock-agentcore-control プラグインの確認
if ! aws bedrock-agentcore-control help &> /dev/null; then
    echo "❌ aws bedrock-agentcore-control プラグインが見つかりません。"
    echo "   以下のコマンドでインストールしてください:"
    echo "   pip install bedrock-agentcore-starter-toolkit"
    exit 1
fi

# Agent Runtimeの存在確認
echo ""
echo "🔍 現在のデプロイ状況を確認中..."

# 環境別エージェント名を生成
AGENT_NAME="healthmate_coach_ai"
if [ "$HEALTHMATE_ENV" != "prod" ]; then
    AGENT_NAME="${AGENT_NAME}_${HEALTHMATE_ENV}"
fi

echo "   検索対象エージェント名: $AGENT_NAME"

# AWS上のAgent Runtimeリストを取得してRuntime IDを検索
echo "   Agent Runtimeリストを取得中..."
AGENT_RUNTIME_JSON=$(aws bedrock-agentcore-control list-agent-runtimes --region "$AWS_DEFAULT_REGION" 2>/dev/null || echo '{"agentRuntimes":[]}')

# jqを使用してエージェント名に一致するRuntime IDを取得
AGENT_RUNTIME_ID=$(echo "$AGENT_RUNTIME_JSON" | jq -r --arg name "$AGENT_NAME" '.agentRuntimes[] | select(.agentRuntimeName == $name) | .agentRuntimeId' 2>/dev/null || echo "")

# 対象のAgent Runtimeが存在するかチェック
if [ -n "$AGENT_RUNTIME_ID" ]; then
    echo "✅ Agent Runtime '$AGENT_NAME' が見つかりました。"
    echo "   Runtime ID: $AGENT_RUNTIME_ID"
    
    # Agent Runtimeの詳細情報を取得
    echo "   Agent Runtime詳細情報を取得中..."
    AGENT_RUNTIME_INFO=$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$AGENT_RUNTIME_ID" --region "$AWS_DEFAULT_REGION" 2>/dev/null || echo "{}")
    
    if [ "$AGENT_RUNTIME_INFO" != "{}" ]; then
        AGENT_STATUS=$(echo "$AGENT_RUNTIME_INFO" | jq -r '.status // "UNKNOWN"' 2>/dev/null || echo "UNKNOWN")
        echo "   ステータス: $AGENT_STATUS"
    else
        echo "   ⚠️  Agent Runtime詳細情報の取得に失敗しました"
    fi
    
    echo ""
    echo "⚠️  以下のリソースが削除されます:"
    echo "   - AgentCore エージェント '$AGENT_NAME' (環境: $HEALTHMATE_ENV)"
    echo "   - ECR リポジトリ（全イメージ含む）"
    echo "   - CodeBuild プロジェクト"
    echo "   - IAM ロール (Healthmate-CoachAI-AgentCore-Runtime-Role${ENV_SUFFIX})"
    echo "   - S3 アーティファクト"
    if [ "$HEALTHMATE_ENV" = "dev" ]; then
        echo "   - メモリリソース (DEV環境のため削除)"
    else
        echo "   - メモリリソース (${HEALTHMATE_ENV}環境のため保持)"
    fi
    echo ""
    echo "🚨 この操作は取り消せません！"
    echo ""
    
    if [ "$FORCE_DELETE" = true ]; then
        echo "🚨 --force フラグにより確認をスキップして削除を実行します"
        response="y"
    else
        echo "本当にHealthCoachAIエージェント (環境: $HEALTHMATE_ENV) を削除しますか？ (y/N)"
        read -r response
    fi
    
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "❌ アンデプロイをキャンセルしました。"
        exit 0
    fi
    
    echo ""
    echo "🗑️  AgentCore リソースを削除中..."
    
    # AWS CLIを使用してAgent Runtimeを直接削除
    echo "   Agent Runtime '$AGENT_NAME' (ID: $AGENT_RUNTIME_ID) を削除中..."
    aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id "$AGENT_RUNTIME_ID" --region "$AWS_DEFAULT_REGION" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Agent Runtime削除完了"
    else
        echo "⚠️  Agent Runtime削除で一部エラーが発生しましたが、続行します。"
    fi
    
    # ECRリポジトリの削除
    echo "   ECRリポジトリを確認中..."
    ECR_REPO_NAME="bedrock-agentcore-${AGENT_NAME}"
    echo "   検索対象ECRリポジトリ名: $ECR_REPO_NAME"
    
    if aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_DEFAULT_REGION" &>/dev/null; then
        echo "   ECRリポジトリ '$ECR_REPO_NAME' を削除中..."
        aws ecr delete-repository --repository-name "$ECR_REPO_NAME" --region "$AWS_DEFAULT_REGION" --force 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "   ✅ ECRリポジトリ削除完了"
        else
            echo "   ⚠️  ECRリポジトリ削除に失敗しました"
        fi
    else
        echo "   ℹ️  ECRリポジトリ '$ECR_REPO_NAME' は見つかりませんでした"
        
        # デバッグ用：利用可能なECRリポジトリを表示
        echo "   🔍 利用可能なECRリポジトリを確認中..."
        AVAILABLE_REPOS=$(aws ecr describe-repositories --region "$AWS_DEFAULT_REGION" --query "repositories[?contains(repositoryName, 'bedrock-agentcore')].repositoryName" --output text 2>/dev/null || echo "")
        if [ -n "$AVAILABLE_REPOS" ]; then
            echo "   利用可能なbedrock-agentcore関連リポジトリ:"
            for repo in $AVAILABLE_REPOS; do
                echo "     - $repo"
            done
        else
            echo "   bedrock-agentcore関連のリポジトリは見つかりませんでした"
        fi
    fi
    
    # CodeBuildプロジェクトの削除
    echo "   CodeBuildプロジェクトを確認中..."
    CODEBUILD_PROJECT_NAME="bedrock-agentcore-${AGENT_NAME}"
    if aws codebuild batch-get-projects --names "$CODEBUILD_PROJECT_NAME" --region "$AWS_DEFAULT_REGION" &>/dev/null; then
        echo "   CodeBuildプロジェクト '$CODEBUILD_PROJECT_NAME' を削除中..."
        aws codebuild delete-project --name "$CODEBUILD_PROJECT_NAME" --region "$AWS_DEFAULT_REGION" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "   ✅ CodeBuildプロジェクト削除完了"
        else
            echo "   ⚠️  CodeBuildプロジェクト削除に失敗しました"
        fi
    else
        echo "   ℹ️  CodeBuildプロジェクトは見つかりませんでした"
    fi
    
    # IAMロールの削除
    echo "   IAMロールを確認中..."
    IAM_ROLE_NAME="Healthmate-CoachAI-AgentCore-Runtime-Role${ENV_SUFFIX}"
    if aws iam get-role --role-name "$IAM_ROLE_NAME" &>/dev/null; then
        echo "   IAMロール '$IAM_ROLE_NAME' を削除中..."
        # ロールにアタッチされたポリシーを削除
        ATTACHED_POLICIES=$(aws iam list-attached-role-policies --role-name "$IAM_ROLE_NAME" --query 'AttachedPolicies[*].PolicyArn' --output text 2>/dev/null || echo "")
        if [ -n "$ATTACHED_POLICIES" ]; then
            for policy_arn in $ATTACHED_POLICIES; do
                aws iam detach-role-policy --role-name "$IAM_ROLE_NAME" --policy-arn "$policy_arn" 2>/dev/null
            done
        fi
        # インラインポリシーを削除
        INLINE_POLICIES=$(aws iam list-role-policies --role-name "$IAM_ROLE_NAME" --query 'PolicyNames[*]' --output text 2>/dev/null || echo "")
        if [ -n "$INLINE_POLICIES" ]; then
            for policy_name in $INLINE_POLICIES; do
                aws iam delete-role-policy --role-name "$IAM_ROLE_NAME" --policy-name "$policy_name" 2>/dev/null
            done
        fi
        # ロールを削除
        aws iam delete-role --role-name "$IAM_ROLE_NAME" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "   ✅ IAMロール削除完了"
        else
            echo "   ⚠️  IAMロール削除に失敗しました"
        fi
    else
        echo "   ℹ️  IAMロールは見つかりませんでした"
    fi
    
else
    echo "ℹ️  Agent Runtime '$AGENT_NAME' は見つかりませんでした。"
    echo "   エージェントは既にアンデプロイされている可能性があります。"
    echo ""
    echo "🔍 利用可能なAgent Runtimeを表示します..."
    
    # デバッグ用：利用可能なAgent Runtimeを表示
    AVAILABLE_RUNTIMES=$(echo "$AGENT_RUNTIME_JSON" | jq -r '.agentRuntimes[]? | "\(.agentRuntimeName) (ID: \(.agentRuntimeId))"' 2>/dev/null || echo "なし")
    if [ "$AVAILABLE_RUNTIMES" != "なし" ] && [ -n "$AVAILABLE_RUNTIMES" ]; then
        echo "   利用可能なAgent Runtime:"
        echo "$AVAILABLE_RUNTIMES" | while read -r line; do
            echo "     - $line"
        done
    else
        echo "   利用可能なAgent Runtimeはありません。"
    fi
    
    echo ""
    echo "🔍 メモリリソースのみ確認します..."
fi

echo ""
echo "🧠 メモリリソースを確認中..."

# メモリリソースの確認と削除（DEV環境のみ）
if [ "$HEALTHMATE_ENV" = "dev" ]; then
    echo "🔍 DEV環境のため、メモリリソースを削除します..."
    
    # 環境別メモリID名を生成
    AGENT_NAME="healthmate_coach_ai"
    if [ "$HEALTHMATE_ENV" != "prod" ]; then
        AGENT_NAME="${AGENT_NAME}_${HEALTHMATE_ENV}"
    fi
    MEMORY_ID_PREFIX="${AGENT_NAME}_mem"
    
    echo "   検索対象メモリIDプレフィックス: $MEMORY_ID_PREFIX"
    
    # メモリリソースの確認と削除
    MEMORY_LIST=$(aws bedrock-agentcore-control list-memories --region "$AWS_DEFAULT_REGION" --query "memories[*].id" --output text 2>/dev/null || echo "[]")
    
    if echo "$MEMORY_LIST" | grep -q "$MEMORY_ID_PREFIX"; then
        echo "🔍 Healthmate-CoachAI関連のメモリリソースが見つかりました。削除中..."
        
        # 環境別メモリIDを抽出して削除
        MEMORY_IDS=$(echo "$MEMORY_LIST" | grep -o "${MEMORY_ID_PREFIX}-[A-Za-z0-9]*" || true)
        
        if [ -n "$MEMORY_IDS" ]; then
            for MEMORY_ID in $MEMORY_IDS; do
                echo "   削除中: $MEMORY_ID"
                aws bedrock-agentcore-control delete-memory --memory-id "$MEMORY_ID" --region "$AWS_DEFAULT_REGION" 2>/dev/null || echo "   ⚠️  $MEMORY_ID の削除に失敗しました（既に削除済みの可能性）"
            done
            echo "✅ メモリリソース削除完了"
        else
            echo "ℹ️  削除対象のメモリリソースが見つかりませんでした。"
        fi
    else
        echo "ℹ️  Healthmate-CoachAI関連のメモリリソースは見つかりませんでした。"
    fi
else
    echo "ℹ️  ${HEALTHMATE_ENV}環境のため、メモリリソースは保持されます。"
    echo "   メモリリソースを削除したい場合は、DEV環境で実行してください。"
fi


echo ""
echo "🎉 HealthCoachAI エージェント (環境: $HEALTHMATE_ENV) のアンデプロイが完了しました！"
echo ""
echo "📋 削除されたリソース:"
echo "   ✅ AgentCore エージェント '$AGENT_NAME' (環境: $HEALTHMATE_ENV)"
echo "   ✅ ECR リポジトリ（全イメージ）"
echo "   ✅ CodeBuild プロジェクト"
echo "   ✅ IAM ロール (Healthmate-CoachAI-AgentCore-Runtime-Role${ENV_SUFFIX})"
echo "   ✅ S3 アーティファクト"
if [ "$HEALTHMATE_ENV" = "dev" ]; then
    echo "   ✅ メモリリソース (DEV環境のため削除)"
else
    echo "   ⚪ メモリリソース (${HEALTHMATE_ENV}環境のため保持)"
fi
echo "   ✅ ローカルキャッシュディレクトリ"
echo ""
echo "💰 これで関連するAWSコストは発生しなくなります。"
echo ""
echo "🔄 再デプロイする場合は以下のコマンドを実行してください:"
echo "   HEALTHMATE_ENV=$HEALTHMATE_ENV ./deploy_to_aws.sh"
echo ""
echo "💡 環境切り替え方法:"
echo "   export HEALTHMATE_ENV=stage && ./destroy_from_aws.sh"
echo "   export HEALTHMATE_ENV=prod && ./destroy_from_aws.sh"
echo ""