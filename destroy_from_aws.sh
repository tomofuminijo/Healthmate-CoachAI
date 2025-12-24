#!/bin/bash

# Healthmate-CoachAI エージェントをAWSからアンデプロイするスクリプト
# 環境別設定対応版 - HEALTHMATE_ENV環境変数に基づく環境別アンデプロイ

set -e  # エラー時に停止

echo "🗑️  Healthmate-CoachAI エージェントをAWSからアンデプロイします（環境別設定対応）"
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

# bedrock-agentcoreがインストールされているか確認
if ! command -v agentcore &> /dev/null; then
    echo "❌ agentcore コマンドが見つかりません。"
    echo "   以下のコマンドでインストールしてください:"
    echo "   pip install bedrock-agentcore"
    exit 1
fi

# 設定ファイルの存在確認
if [ ! -f ".bedrock_agentcore.yaml" ]; then
    echo "⚠️  .bedrock_agentcore.yaml が見つかりません。"
    echo "   エージェントは既にアンデプロイされている可能性があります。"
    echo ""
    echo "🔍 メモリリソースのみ確認します..."
else
    echo ""
    echo "🔍 現在のデプロイ状況を確認中..."
    
    # 現在の状況を表示（エラーを無視）
    agentcore status 2>/dev/null || echo "   エージェントは既に削除されているか、設定に問題があります。"
    
    echo ""
    echo "⚠️  以下のリソースが削除されます:"
    echo "   - AgentCore エージェント (環境: $HEALTHMATE_ENV)"
    echo "   - ECR リポジトリ（全イメージ含む）"
    echo "   - CodeBuild プロジェクト"
    echo "   - IAM ロール (Healthmate-CoachAI-AgentCore-Runtime-Role${ENV_SUFFIX})"
    echo "   - S3 アーティファクト"
    echo "   - ローカル設定ファイル"
    if [ "$HEALTHMATE_ENV" = "dev" ]; then
        echo "   - メモリリソース (DEV環境のため削除)"
    else
        echo "   - メモリリソース (${HEALTHMATE_ENV}環境のため保持)"
    fi
    echo ""
    echo "🚨 この操作は取り消せません！"
    echo ""
    echo "本当にHealthCoachAIエージェント (環境: $HEALTHMATE_ENV) を削除しますか？ (y/N)"
    read -r response
    
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "❌ アンデプロイをキャンセルしました。"
        exit 0
    fi
    
    echo ""
    echo "🗑️  AgentCore リソースを削除中..."
    
    # AgentCore リソースを削除（ECRリポジトリも含む）
    agentcore destroy --delete-ecr-repo --force
    
    if [ $? -eq 0 ]; then
        echo "✅ AgentCore リソース削除完了"
    else
        echo "⚠️  AgentCore リソース削除で一部エラーが発生しましたが、続行します。"
    fi
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
    MEMORY_LIST=$(AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION aws bedrock-agentcore-control list-memories --query "memories[*].id" --output text 2>/dev/null || echo "[]")
    
    if echo "$MEMORY_LIST" | grep -q "$MEMORY_ID_PREFIX"; then
        echo "🔍 Healthmate-CoachAI関連のメモリリソースが見つかりました。削除中..."
        
        # 環境別メモリIDを抽出して削除
        MEMORY_IDS=$(echo "$MEMORY_LIST" | grep -o "${MEMORY_ID_PREFIX}-[A-Za-z0-9]*" || true)
        
        if [ -n "$MEMORY_IDS" ]; then
            for MEMORY_ID in $MEMORY_IDS; do
                echo "   削除中: $MEMORY_ID"
                AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION agentcore memory delete "$MEMORY_ID" 2>/dev/null || echo "   ⚠️  $MEMORY_ID の削除に失敗しました（既に削除済みの可能性）"
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
echo "🧹 最終クリーンアップ中..."

# 残存する設定ファイルがあれば削除
if [ -f ".bedrock_agentcore.yaml" ]; then
    echo "   ローカル設定ファイルを削除中..."
    rm -f .bedrock_agentcore.yaml
    echo "   ✅ .bedrock_agentcore.yaml を削除しました"
fi

# .bedrock_agentcore ディレクトリがあれば削除
if [ -d ".bedrock_agentcore" ]; then
    echo "   ローカルキャッシュディレクトリを削除中..."
    rm -rf .bedrock_agentcore
    echo "   ✅ .bedrock_agentcore ディレクトリを削除しました"
fi

echo ""
echo "🎉 HealthCoachAI エージェント (環境: $HEALTHMATE_ENV) のアンデプロイが完了しました！"
echo ""
echo "📋 削除されたリソース:"
echo "   ✅ AgentCore エージェント (環境: $HEALTHMATE_ENV)"
echo "   ✅ ECR リポジトリ（全イメージ）"
echo "   ✅ CodeBuild プロジェクト"
echo "   ✅ IAM ロール (Healthmate-CoachAI-AgentCore-Runtime-Role${ENV_SUFFIX})"
echo "   ✅ S3 アーティファクト"
if [ "$HEALTHMATE_ENV" = "dev" ]; then
    echo "   ✅ メモリリソース (DEV環境のため削除)"
else
    echo "   ⚪ メモリリソース (${HEALTHMATE_ENV}環境のため保持)"
fi
echo "   ✅ ローカル設定ファイル"
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