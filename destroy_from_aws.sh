#!/bin/bash

# Healthmate-CoachAI エージェントをAWSからアンデプロイするスクリプト
# 全てのAWSリソースとローカル設定を削除

set -e  # エラー時に停止

echo "🗑️  Healthmate-CoachAI エージェントをAWSからアンデプロイします"
echo "=" * 80

# AWS設定
export AWS_DEFAULT_REGION=${AWS_REGION:-us-west-2}
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
if [ -d "venv" ]; then
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
    echo "   - AgentCore エージェント"
    echo "   - ECR リポジトリ（全イメージ含む）"
    echo "   - CodeBuild プロジェクト"
    echo "   - IAM ロール"
    echo "   - S3 アーティファクト"
    echo "   - ローカル設定ファイル"
    echo ""
    echo "🚨 この操作は取り消せません！"
    echo ""
    echo "本当にHealthCoachAIエージェントを削除しますか？ (y/N)"
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

# メモリリソースの確認と削除
MEMORY_LIST=$(AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION aws bedrock-agentcore-control list-memories --query "memories[*].id" --output text 2>/dev/null || echo "[]")

if echo "$MEMORY_LIST" | grep -q "healthmate_coach_ai_mem"; then
    echo "🔍 Healthmate-CoachAI関連のメモリリソースが見つかりました。削除中..."
    
    # healthmate_coach_ai_mem で始まるメモリIDを抽出して削除
    MEMORY_IDS=$(echo "$MEMORY_LIST" | grep -o 'healthmate_coach_ai_mem-[A-Za-z0-9]*' || true)
    
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
echo "🎉 HealthCoachAI エージェントのアンデプロイが完了しました！"
echo ""
echo "📋 削除されたリソース:"
echo "   ✅ AgentCore エージェント"
echo "   ✅ ECR リポジトリ（全イメージ）"
echo "   ✅ CodeBuild プロジェクト"
echo "   ✅ IAM ロール"
echo "   ✅ S3 アーティファクト"
echo "   ✅ メモリリソース"
echo "   ✅ ローカル設定ファイル"
echo ""
echo "💰 これで関連するAWSコストは発生しなくなります。"
echo ""
echo "🔄 再デプロイする場合は以下のコマンドを実行してください:"
echo "   ./deploy_to_aws.sh"
echo ""