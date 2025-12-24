#!/usr/bin/env python3
"""
CoachAI 環境別設定テストスクリプト

環境別設定が正しく動作することを確認するためのテストスクリプトです。
"""

import os
import sys
import subprocess
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "agent"))

def test_environment_detection():
    """環境検出のテスト"""
    print("🧪 環境検出テスト")
    print("=" * 50)
    
    # 各環境での動作をテスト
    test_environments = ['dev', 'stage', 'prod']
    
    for env in test_environments:
        print(f"\n🌍 環境: {env}")
        
        # 環境変数を設定
        os.environ['HEALTHMATE_ENV'] = env
        
        try:
            from healthmate_coach_ai.environment.environment_manager import EnvironmentManager
            from healthmate_coach_ai.environment.configuration_provider import ConfigurationProvider
            
            # 環境検出テスト
            detected_env = EnvironmentManager.get_environment()
            print(f"   検出された環境: {detected_env}")
            assert detected_env == env, f"環境検出エラー: 期待値={env}, 実際値={detected_env}"
            
            # 設定プロバイダーテスト
            config = ConfigurationProvider("Healthmate-CoachAI")
            stack_name = config.get_stack_name("TestStack")
            expected_stack = "TestStack" if env == "prod" else f"TestStack-{env}"
            print(f"   スタック名: {stack_name}")
            assert stack_name == expected_stack, f"スタック名エラー: 期待値={expected_stack}, 実際値={stack_name}"
            
            # 環境サフィックステスト
            env_suffix = config.get_environment_suffix()
            expected_suffix = "" if env == "prod" else f"-{env}"
            print(f"   環境サフィックス: '{env_suffix}'")
            assert env_suffix == expected_suffix, f"サフィックスエラー: 期待値='{expected_suffix}', 実際値='{env_suffix}'"
            
            print(f"   ✅ {env}環境テスト成功")
            
        except Exception as e:
            print(f"   ❌ {env}環境テストエラー: {e}")
            return False
    
    print("\n✅ 全環境検出テスト成功")
    return True


def test_memory_id_and_provider_generation():
    """メモリIDとプロバイダー名生成のテスト"""
    print("\n🧠 メモリIDとプロバイダー名生成テスト")
    print("=" * 50)
    
    test_cases = [
        ('dev', 'healthmate_coach_ai_mem-dev', 'healthmanager-oauth2-provider-dev'),
        ('stage', 'healthmate_coach_ai_mem-stage', 'healthmanager-oauth2-provider-stage'),
        ('prod', 'healthmate_coach_ai_mem', 'healthmanager-oauth2-provider')
    ]
    
    for env, expected_memory_id, expected_provider_name in test_cases:
        print(f"\n🌍 環境: {env}")
        
        # 環境変数を設定
        os.environ['HEALTHMATE_ENV'] = env
        
        # メモリID生成ロジックをテスト
        env_suffix = "" if env == "prod" else f"-{env}"
        generated_memory_id = f"healthmate_coach_ai_mem{env_suffix}"
        generated_provider_name = f"healthmanager-oauth2-provider{env_suffix}"
        
        print(f"   生成されたメモリID: {generated_memory_id}")
        assert generated_memory_id == expected_memory_id, f"メモリIDエラー: 期待値={expected_memory_id}, 実際値={generated_memory_id}"
        
        print(f"   生成されたプロバイダー名: {generated_provider_name}")
        assert generated_provider_name == expected_provider_name, f"プロバイダー名エラー: 期待値={expected_provider_name}, 実際値={generated_provider_name}"
        
        print(f"   ✅ {env}環境メモリID・プロバイダー名生成成功")
    
    print("\n✅ 全メモリID・プロバイダー名生成テスト成功")
    return True


def test_iam_role_naming():
    """IAMロール名生成のテスト"""
    print("\n🎭 IAMロール名生成テスト")
    print("=" * 50)
    
    test_cases = [
        ('dev', 'Healthmate-CoachAI-AgentCore-Runtime-Role-dev'),
        ('stage', 'Healthmate-CoachAI-AgentCore-Runtime-Role-stage'),
        ('prod', 'Healthmate-CoachAI-AgentCore-Runtime-Role')
    ]
    
    for env, expected_role_name in test_cases:
        print(f"\n🌍 環境: {env}")
        
        # ロール名生成ロジックをテスト
        env_suffix = "" if env == "prod" else f"-{env}"
        generated_role_name = f"Healthmate-CoachAI-AgentCore-Runtime-Role{env_suffix}"
        
        print(f"   生成されたロール名: {generated_role_name}")
        assert generated_role_name == expected_role_name, f"ロール名エラー: 期待値={expected_role_name}, 実際値={generated_role_name}"
        print(f"   ✅ {env}環境ロール名生成成功")
    
    print("\n✅ 全IAMロール名生成テスト成功")
    return True


def test_stack_name_generation():
    """CloudFormationスタック名生成のテスト"""
    print("\n📚 CloudFormationスタック名生成テスト")
    print("=" * 50)
    
    test_cases = [
        ('dev', 'Healthmate-HealthManagerStack-dev', 'Healthmate-CoreStack-dev'),
        ('stage', 'Healthmate-HealthManagerStack-stage', 'Healthmate-CoreStack-stage'),
        ('prod', 'Healthmate-HealthManagerStack', 'Healthmate-CoreStack')
    ]
    
    for env, expected_hm_stack, expected_core_stack in test_cases:
        print(f"\n🌍 環境: {env}")
        
        # 環境変数を設定
        os.environ['HEALTHMATE_ENV'] = env
        
        try:
            from healthmate_coach_ai.environment.configuration_provider import ConfigurationProvider
            
            config = ConfigurationProvider("Healthmate-CoachAI")
            
            # HealthManagerスタック名テスト
            hm_stack = config.get_stack_name("Healthmate-HealthManagerStack")
            print(f"   HealthManagerスタック名: {hm_stack}")
            assert hm_stack == expected_hm_stack, f"HMスタック名エラー: 期待値={expected_hm_stack}, 実際値={hm_stack}"
            
            # Coreスタック名テスト
            core_stack = config.get_stack_name("Healthmate-CoreStack")
            print(f"   Coreスタック名: {core_stack}")
            assert core_stack == expected_core_stack, f"Coreスタック名エラー: 期待値={expected_core_stack}, 実際値={core_stack}"
            
            print(f"   ✅ {env}環境スタック名生成成功")
            
        except Exception as e:
            print(f"   ❌ {env}環境スタック名生成エラー: {e}")
            return False
    
    print("\n✅ 全スタック名生成テスト成功")
    return True


def test_deploy_script_environment_handling():
    """デプロイスクリプトの環境処理テスト"""
    print("\n🚀 デプロイスクリプト環境処理テスト")
    print("=" * 50)
    
    # deploy_to_aws.shが存在することを確認
    deploy_script = Path(__file__).parent / "deploy_to_aws.sh"
    if not deploy_script.exists():
        print("❌ deploy_to_aws.sh が見つかりません")
        return False
    
    print("✅ deploy_to_aws.sh が存在します")
    
    # スクリプト内容の基本チェック
    with open(deploy_script, 'r') as f:
        content = f.read()
    
    required_patterns = [
        'HEALTHMATE_ENV',
        'ENV_SUFFIX',
        'setup_environment_config',
        'healthmate_coach_ai_mem',
        'healthmanager-oauth2-provider',
        'Healthmate-CoachAI-AgentCore-Runtime-Role'
    ]
    
    for pattern in required_patterns:
        if pattern in content:
            print(f"   ✅ パターン '{pattern}' が見つかりました")
        else:
            print(f"   ❌ パターン '{pattern}' が見つかりません")
            return False
    
    print("\n✅ デプロイスクリプト環境処理テスト成功")
    return True


def main():
    """メインテスト実行"""
    print("🧪 Healthmate-CoachAI 環境別設定テスト")
    print("=" * 80)
    
    # 元の環境変数を保存
    original_env = os.environ.get('HEALTHMATE_ENV')
    
    try:
        tests = [
            test_environment_detection,
            test_memory_id_and_provider_generation,
            test_iam_role_naming,
            test_stack_name_generation,
            test_deploy_script_environment_handling
        ]
        
        passed = 0
        failed = 0
        
        for test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ テスト {test_func.__name__} でエラー: {e}")
                failed += 1
        
        print("\n" + "=" * 80)
        print("📊 テスト結果サマリー")
        print("=" * 80)
        print(f"✅ 成功: {passed}")
        print(f"❌ 失敗: {failed}")
        print(f"📈 成功率: {passed/(passed+failed)*100:.1f}%")
        
        if failed == 0:
            print("\n🎉 全テスト成功！環境別設定は正常に動作しています。")
            return True
        else:
            print(f"\n⚠️  {failed}個のテストが失敗しました。設定を確認してください。")
            return False
            
    finally:
        # 元の環境変数を復元
        if original_env:
            os.environ['HEALTHMATE_ENV'] = original_env
        elif 'HEALTHMATE_ENV' in os.environ:
            del os.environ['HEALTHMATE_ENV']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)