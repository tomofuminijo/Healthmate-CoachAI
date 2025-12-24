#!/usr/bin/env python3
"""
Healthmate-CoachAI用カスタムIAMロール作成スクリプト（環境別設定対応）

AgentCore Runtime用の適切な権限を持つカスタムIAMロールを環境別に作成します。
"""

import boto3
import json
import sys
import time
import os
from botocore.exceptions import ClientError


def get_environment_config():
    """環境設定を取得"""
    env = os.environ.get('HEALTHMATE_ENV', 'dev')
    
    # 有効な環境値の検証
    if env not in ['dev', 'stage', 'prod']:
        print(f"❌ 無効な環境値: {env}")
        print("   有効な値: dev, stage, prod")
        print("   デフォルトのdev環境を使用します")
        env = 'dev'
    
    # 環境別サフィックスの設定
    env_suffix = "" if env == "prod" else f"-{env}"
    
    return env, env_suffix


def load_policy_document(file_path: str) -> dict:
    """ポリシードキュメントをファイルから読み込み"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ ポリシーファイル読み込みエラー ({file_path}): {e}")
        sys.exit(1)


def create_iam_role_and_policies():
    """カスタムIAMロールとポリシーを環境別に作成"""
    
    # 環境設定を取得
    env, env_suffix = get_environment_config()
    
    # AWS設定
    region = 'us-west-2'
    account_id = boto3.client('sts').get_caller_identity()['Account']
    role_name = f'Healthmate-CoachAI-AgentCore-Runtime-Role{env_suffix}'
    
    print("=" * 80)
    print("🔐 Healthmate-CoachAI用カスタムIAMロール作成（環境別設定対応）")
    print("=" * 80)
    print(f"🌍 環境: {env}")
    print(f"📍 リージョン: {region}")
    print(f"🏢 アカウントID: {account_id}")
    print(f"🎭 ロール名: {role_name}")
    print()
    
    # IAMクライアント初期化
    iam = boto3.client('iam', region_name=region)
    
    try:
        # 1. 信頼ポリシーを読み込み
        print("📋 信頼ポリシーを読み込み中...")
        trust_policy = load_policy_document('agentcore-trust-policy.json')
        
        # 2. IAMロールを作成
        print(f"🎭 IAMロール '{role_name}' を作成中...")
        try:
            iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f'Healthmate-CoachAI AgentCore Runtime Custom Role ({env} environment)',
                MaxSessionDuration=3600
            )
            print(f"   ✅ IAMロール作成完了")
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"   ⚠️  IAMロール '{role_name}' は既に存在します")
            else:
                raise
        
        # 3. インラインポリシーを作成・アタッチ
        policies = [
            {
                'name': 'Healthmate-CoachAI-Runtime-Policy',
                'file': 'bedrock-agentcore-runtime-policy.json',
                'description': 'AgentCore Runtime Basic Permissions'
            }
        ]
        
        for policy_info in policies:
            policy_name = policy_info['name']
            policy_file = policy_info['file']
            
            print(f"📜 インラインポリシー '{policy_name}' を作成中...")
            
            # ポリシードキュメントを読み込み
            policy_document = load_policy_document(policy_file)
            
            try:
                # インラインポリシーをロールに直接アタッチ
                iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document)
                )
                print(f"   ✅ インラインポリシー作成・アタッチ完了")
            except ClientError as e:
                print(f"   ❌ インラインポリシー作成エラー: {e}")
                raise
        
        # 4. ロール作成完了を待機
        print("⏳ IAMロールの作成完了を待機中...")
        time.sleep(10)  # IAMの整合性確保のため少し待機
        
        # 5. 作成されたロールの詳細を表示
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        print()
        print("✅ カスタムIAMロール作成完了！")
        print()
        print("� 作成されたプリソース:")
        print(f"   🌍 環境: {env}")
        print(f"   🎭 ロール名: {role_name}")
        print(f"   🔗 ロールARN: {role_arn}")
        print()
        print("📜 アタッチされたインラインポリシー:")
        for policy_info in policies:
            print(f"   - {policy_info['name']} (インラインポリシー)")
        print()
        print("🚀 次のステップ:")
        print("   deploy_to_aws.sh を実行してエージェントをデプロイしてください")
        print(f"   このロールARNが自動的に使用されます: {role_arn}")
        print()
        print("💡 環境切り替え:")
        print("   export HEALTHMATE_ENV=stage && python3 create_custom_iam_role.py")
        print("   export HEALTHMATE_ENV=prod && python3 create_custom_iam_role.py")
        print()
        
        return role_arn
        
    except Exception as e:
        print(f"❌ IAMロール作成エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    create_iam_role_and_policies()