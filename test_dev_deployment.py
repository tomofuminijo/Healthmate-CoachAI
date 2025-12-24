#!/usr/bin/env python3
"""
CoachAI dev環境デプロイテストスクリプト

dev環境でのAgentCoreデプロイと環境別MCP連携確認を行います。
"""

import os
import sys
import subprocess
import time
import json
from pathlib import Path

def check_prerequisites():
    """デプロイ前提条件の確認"""
    print("🔍 デプロイ前提条件の確認")
    print("=" * 50)
    
    # 必要なファイルの存在確認
    required_files = [
        "deploy_to_aws.sh",
        "create_custom_iam_role.py",
        "agentcore-trust-policy.json",
        "bedrock-agentcore-runtime-policy.json"
    ]
    
    for file_name in required_files:
        file_path = Path(file_name)
        if file_path.exists():
            print(f"   ✅ {file_name} が存在します")
        else:
            print(f"   ❌ {file_name} が見つかりません")
            return False
    
    # AWS CLI の確認
    try:
        result = subprocess.run(['aws', 'sts', 'get-caller-identity'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            identity = json.loads(result.stdout)
            print(f"   ✅ AWS認証成功: {identity.get('Arn', 'Unknown')}")
        else:
            print(f"   ❌ AWS認証エラー: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ AWS CLI確認エラー: {e}")
        return False
    
    # agentcore CLI の確認
    try:
        result = subprocess.run(['agentcore', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"   ✅ AgentCore CLI利用可能")
        else:
            print(f"   ❌ AgentCore CLI確認エラー: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ AgentCore CLI確認エラー: {e}")
        return False
    
    print("\n✅ 全前提条件クリア")
    return True


def check_dependent_stacks():
    """依存するCloudFormationスタックの確認"""
    print("\n🏗️  依存スタックの確認")
    print("=" * 50)
    
    # 現在存在するスタックを確認（環境サフィックスなし）
    base_stacks = [
        "Healthmate-CoreStack",
        "Healthmate-HealthManagerStack"
    ]
    
    # dev環境用スタックも確認
    dev_stacks = [
        "Healthmate-CoreStack-dev", 
        "Healthmate-HealthManagerStack-dev"
    ]
    
    found_stacks = []
    
    # まず基本スタックを確認
    for stack_name in base_stacks:
        try:
            result = subprocess.run([
                'aws', 'cloudformation', 'describe-stacks',
                '--stack-name', stack_name
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                stack_info = json.loads(result.stdout)
                stack_status = stack_info['Stacks'][0]['StackStatus']
                print(f"   ✅ {stack_name}: {stack_status}")
                found_stacks.append(stack_name)
            else:
                print(f"   ⚠️  {stack_name}: スタックが見つかりません")
                
        except Exception as e:
            print(f"   ⚠️  {stack_name} 確認エラー: {e}")
    
    # dev環境スタックを確認
    for stack_name in dev_stacks:
        try:
            result = subprocess.run([
                'aws', 'cloudformation', 'describe-stacks',
                '--stack-name', stack_name
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                stack_info = json.loads(result.stdout)
                stack_status = stack_info['Stacks'][0]['StackStatus']
                print(f"   ✅ {stack_name}: {stack_status}")
                found_stacks.append(stack_name)
            else:
                print(f"   ⚠️  {stack_name}: スタックが見つかりません")
                
        except Exception as e:
            print(f"   ⚠️  {stack_name} 確認エラー: {e}")
    
    if len(found_stacks) >= 2:
        print(f"\n✅ 依存スタック確認完了 ({len(found_stacks)}個のスタックが利用可能)")
        print("   注意: dev環境用スタックが存在しない場合、基本スタックを使用してテストします")
        return True
    else:
        print(f"\n❌ 必要な依存スタックが不足しています ({len(found_stacks)}/2)")
        print("   Healthmate-CoreとHealthmate-HealthManagerのスタックが必要です")
        return False


def test_environment_variables():
    """環境変数の設定テスト"""
    print("\n🌍 環境変数設定テスト")
    print("=" * 50)
    
    # dev環境を設定
    os.environ['HEALTHMATE_ENV'] = 'dev'
    print("   HEALTHMATE_ENV=dev を設定")
    
    # 他の必要な環境変数を確認
    env_vars = {
        'AWS_REGION': os.environ.get('AWS_REGION', 'us-west-2'),
        'HEALTHMATE_ENV': os.environ.get('HEALTHMATE_ENV'),
    }
    
    for var_name, var_value in env_vars.items():
        print(f"   {var_name}={var_value}")
    
    print("\n✅ 環境変数設定完了")
    return True


def simulate_deployment_config():
    """デプロイ設定のシミュレーション"""
    print("\n🔧 デプロイ設定シミュレーション")
    print("=" * 50)
    
    # 環境別設定値の計算
    env = 'dev'
    env_suffix = f"-{env}"
    
    expected_config = {
        'environment': env,
        'env_suffix': env_suffix,
        'role_name': f'Healthmate-CoachAI-AgentCore-Runtime-Role{env_suffix}',
        'agent_name': f'healthmate_coach_ai{env_suffix}',
        'memory_id': f'healthmate_coach_ai_mem{env_suffix}',
        'provider_name': f'healthmanager-oauth2-provider{env_suffix}',
        'core_stack': f'Healthmate-CoreStack{env_suffix}',
        'hm_stack': f'Healthmate-HealthManagerStack{env_suffix}'
    }
    
    print("   予想される設定値:")
    for key, value in expected_config.items():
        print(f"     {key}: {value}")
    
    print("\n✅ デプロイ設定シミュレーション完了")
    return True


def check_deployment_readiness():
    """デプロイ準備状況の総合確認"""
    print("\n📋 デプロイ準備状況の総合確認")
    print("=" * 50)
    
    checks = [
        ("前提条件", check_prerequisites),
        ("依存スタック", check_dependent_stacks),
        ("環境変数", test_environment_variables),
        ("デプロイ設定", simulate_deployment_config)
    ]
    
    passed = 0
    failed = 0
    
    for check_name, check_func in checks:
        try:
            if check_func():
                print(f"   ✅ {check_name}: 成功")
                passed += 1
            else:
                print(f"   ❌ {check_name}: 失敗")
                failed += 1
        except Exception as e:
            print(f"   ❌ {check_name}: エラー - {e}")
            failed += 1
    
    print(f"\n📊 確認結果: 成功 {passed}, 失敗 {failed}")
    
    if failed == 0:
        print("\n🎉 デプロイ準備完了！")
        print("\n🚀 次のステップ:")
        print("   1. HEALTHMATE_ENV=dev ./deploy_to_aws.sh でデプロイ実行")
        print("   2. agentcore status でデプロイ状況確認")
        print("   3. python manual_test_deployed_agent.py でテスト実行")
        return True
    else:
        print(f"\n⚠️  {failed}個の確認項目が失敗しました。")
        print("   問題を解決してからデプロイを実行してください。")
        return False


def main():
    """メイン実行"""
    print("🧪 Healthmate-CoachAI dev環境デプロイテスト")
    print("=" * 80)
    
    try:
        success = check_deployment_readiness()
        return success
        
    except KeyboardInterrupt:
        print("\n\n⚠️  テストが中断されました")
        return False
    except Exception as e:
        print(f"\n❌ テスト実行エラー: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)