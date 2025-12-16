#!/bin/bash

# Healthmate-CoachAI サービス名変更に伴う古いリソースのクリーンアップスクリプト

set -e

echo "=== Healthmate-CoachAI 古いリソースクリーンアップ準備 ==="

# 色付きメッセージ用の関数
print_info() {
    echo -e "\033[34m[INFO]\033[0m $1"
}

print_warning() {
    echo -e "\033[33m[WARNING]\033[0m $1"
}

print_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

print_success() {
    echo -e "\033[32m[SUCCESS]\033[0m $1"
}

# 1. 古いAgentCoreエージェントの確認
print_info "古いAgentCoreエージェントを確認中..."

# AgentCore設定ファイルが存在するかチェック
if [ -f ".bedrock_agentcore.yaml" ]; then
    print_warning "AgentCore設定ファイルが見つかりました: .bedrock_agentcore.yaml"
    
    # 現在のステータスを確認
    if agentcore status > /dev/null 2>&1; then
        print_warning "既存のAgentCoreエージェントが動作中です"
        echo "現在のステータス:"
        agentcore status
        
        echo ""
        read -p "既存のエージェントを削除しますか？ (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "既存のAgentCoreエージェントを削除中..."
            agentcore destroy --yes
            print_success "既存のAgentCoreエージェントを削除しました"
        else
            print_warning "既存のエージェントは保持されます"
        fi
    else
        print_info "AgentCore設定ファイルは存在しますが、エージェントは動作していません"
    fi
else
    print_info "AgentCore設定ファイルが見つかりません（初回デプロイの可能性）"
fi

# 2. 古いIAMロールの確認
print_info "古いIAMロールを確認中..."

OLD_ROLE_NAME="HealthCoachAI-AgentCore-Runtime-Role"
NEW_ROLE_NAME="Healthmate-CoachAI-AgentCore-Runtime-Role"

# 古いロール名の確認
if aws iam get-role --role-name "$OLD_ROLE_NAME" > /dev/null 2>&1; then
    print_warning "古いIAMロールが見つかりました: $OLD_ROLE_NAME"
    
    echo ""
    read -p "古いIAMロールを削除しますか？ (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "古いIAMロールを削除中..."
        
        # アタッチされたポリシーを確認・デタッチ
        ATTACHED_POLICIES=$(aws iam list-attached-role-policies --role-name "$OLD_ROLE_NAME" --query 'AttachedPolicies[].PolicyArn' --output text)
        
        if [ ! -z "$ATTACHED_POLICIES" ]; then
            print_info "アタッチされたポリシーをデタッチ中..."
            for policy_arn in $ATTACHED_POLICIES; do
                aws iam detach-role-policy --role-name "$OLD_ROLE_NAME" --policy-arn "$policy_arn"
                print_info "デタッチ完了: $policy_arn"
            done
        fi
        
        # インラインポリシーを確認・削除
        INLINE_POLICIES=$(aws iam list-role-policies --role-name "$OLD_ROLE_NAME" --query 'PolicyNames' --output text)
        
        if [ ! -z "$INLINE_POLICIES" ]; then
            print_info "インラインポリシーを削除中..."
            for policy_name in $INLINE_POLICIES; do
                aws iam delete-role-policy --role-name "$OLD_ROLE_NAME" --policy-name "$policy_name"
                print_info "削除完了: $policy_name"
            done
        fi
        
        # ロールを削除
        aws iam delete-role --role-name "$OLD_ROLE_NAME"
        print_success "古いIAMロール '$OLD_ROLE_NAME' を削除しました"
    else
        print_warning "古いIAMロールは保持されます"
    fi
else
    print_info "古いIAMロール '$OLD_ROLE_NAME' は見つかりませんでした"
fi

# 3. 新しいIAMロールの確認
print_info "新しいIAMロールを確認中..."

if aws iam get-role --role-name "$NEW_ROLE_NAME" > /dev/null 2>&1; then
    print_success "新しいIAMロール '$NEW_ROLE_NAME' が既に存在します"
else
    print_info "新しいIAMロール '$NEW_ROLE_NAME' はまだ作成されていません"
    print_info "デプロイ時に自動作成されます"
fi

# 4. CloudFormationスタックの確認（もしあれば）
print_info "関連するCloudFormationスタックを確認中..."

# HealthCoachAI関連のスタックを検索
OLD_STACKS=$(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[?contains(StackName, `HealthCoachAI`)].StackName' --output text)

if [ ! -z "$OLD_STACKS" ]; then
    print_warning "HealthCoachAI関連のCloudFormationスタックが見つかりました:"
    echo "$OLD_STACKS"
    
    echo ""
    read -p "これらのスタックを削除しますか？ (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for stack_name in $OLD_STACKS; do
            print_info "CloudFormationスタックを削除中: $stack_name"
            aws cloudformation delete-stack --stack-name "$stack_name"
            print_info "削除開始: $stack_name (完了まで数分かかる場合があります)"
        done
        print_success "CloudFormationスタックの削除を開始しました"
    else
        print_warning "CloudFormationスタックは保持されます"
    fi
else
    print_info "HealthCoachAI関連のCloudFormationスタックは見つかりませんでした"
fi

# 5. 環境変数の確認
print_info "環境変数を確認中..."

if [ ! -z "$HEALTHMANAGER_GATEWAY_ID" ]; then
    print_success "HEALTHMANAGER_GATEWAY_ID が設定されています: $HEALTHMANAGER_GATEWAY_ID"
else
    print_warning "HEALTHMANAGER_GATEWAY_ID が設定されていません"
    print_info "デプロイ前に Healthmate-HealthManager サービスから取得してください"
fi

if [ ! -z "$AWS_REGION" ]; then
    print_success "AWS_REGION が設定されています: $AWS_REGION"
else
    print_info "AWS_REGION が設定されていません（デフォルト: us-west-2）"
fi

echo ""
print_success "=== クリーンアップ準備完了 ==="
print_info "次のステップ:"
print_info "1. 必要に応じて環境変数を設定"
print_info "2. ./deploy_to_aws.sh を実行して新しい設定でデプロイ"
print_info "3. デプロイ後に manual_test_deployed_agent.py でテスト実行"

echo ""