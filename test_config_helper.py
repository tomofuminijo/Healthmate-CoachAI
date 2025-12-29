#!/usr/bin/env python3
"""
テスト用設定ヘルパー（環境別設定対応）

CloudFormationスタックから動的に設定を取得し、
テストファイルで共通利用できるようにします。

環境別設定対応:
- HEALTHMATE_ENV環境変数に基づく環境別スタック名の自動解決
- 環境別CloudFormationスタックからの設定取得
"""

import boto3
import json
import os
from botocore.exceptions import ClientError


class TestConfig:
    """テスト用設定管理クラス"""
    
    def __init__(self):
        self._config = None
    
    def _get_stack_names(self) -> tuple:
        """CloudFormationスタック名を取得（環境別対応）"""
        # HEALTHMATE_ENV環境変数の取得（デフォルト: dev）
        environment = os.environ.get('HEALTHMATE_ENV', 'dev')
        
        # 有効な環境値の検証
        if environment not in ['dev', 'stage', 'prod']:
            print(f"❌ 無効な環境値: {environment}")
            print("   有効な値: dev, stage, prod")
            print("   デフォルトのdev環境を使用します")
            environment = 'dev'
        
        # 環境別サフィックスの設定
        env_suffix = f"-{environment}"
        
        # 環境別スタック名の生成
        core_stack = f'Healthmate-CoreStack{env_suffix}'
        healthmanager_stack = f'Healthmate-HealthManagerStack{env_suffix}'
        
        return core_stack, healthmanager_stack
    
    def _get_region(self) -> str:
        # AWS_REGION 環境変数から取得、デフォルトは、us-west-2リージョンを使用
        return os.environ.get('AWS_REGION', 'us-west-2')
    
    def _fetch_cloudformation_config(self) -> dict:
        """CloudFormationスタックから設定を取得"""
        try:
            core_stack, healthmanager_stack = self._get_stack_names()
            region = self._get_region()
            
            # 環境情報を表示
            environment = os.environ.get('HEALTHMATE_ENV', 'dev')
            print(f"CloudFormation設定取得中:")
            print(f"  環境: {environment}")
            print(f"  Cognito設定: {core_stack}")
            print(f"  Gateway設定: {healthmanager_stack}")
            print(f"  リージョン: {region}")
            
            cfn = boto3.client('cloudformation', region_name=region)
            
            # Healthmate-Coreスタックから認証設定を取得
            core_response = cfn.describe_stacks(StackName=core_stack)
            if not core_response['Stacks']:
                raise Exception(f"CloudFormationスタック '{core_stack}' が見つかりません")
            
            core_outputs = {}
            for output in core_response['Stacks'][0].get('Outputs', []):
                core_outputs[output['OutputKey']] = output['OutputValue']
            
            # Healthmate-HealthManagerスタックからGateway設定を取得
            healthmanager_response = cfn.describe_stacks(StackName=healthmanager_stack)
            if not healthmanager_response['Stacks']:
                raise Exception(f"CloudFormationスタック '{healthmanager_stack}' が見つかりません")
            
            healthmanager_outputs = {}
            for output in healthmanager_response['Stacks'][0].get('Outputs', []):
                healthmanager_outputs[output['OutputKey']] = output['OutputValue']
            
            print(f"Healthmate-Core出力: {list(core_outputs.keys())}")
            print(f"Healthmate-HealthManager出力: {list(healthmanager_outputs.keys())}")
            
            # 必要な出力が存在するかチェック
            required_core_outputs = ['UserPoolId', 'UserPoolClientId']
            missing_core_outputs = [key for key in required_core_outputs if key not in core_outputs]
            if missing_core_outputs:
                raise Exception(f"Healthmate-Coreスタックに必要な出力が見つかりません: {missing_core_outputs}")
            
            required_healthmanager_outputs = ['GatewayId']
            missing_healthmanager_outputs = [key for key in required_healthmanager_outputs if key not in healthmanager_outputs]
            if missing_healthmanager_outputs:
                raise Exception(f"Healthmate-HealthManagerスタックに必要な出力が見つかりません: {missing_healthmanager_outputs}")
            
            # Cognito設定（Client Secretは使用しない）
            config = {
                'region': region,
                'user_pool_id': core_outputs['UserPoolId'],
                'client_id': core_outputs['UserPoolClientId'],
                'gateway_id': healthmanager_outputs['GatewayId']
            }
            
            print("✅ CloudFormation設定取得完了")
            return config
            
        except Exception as e:
            print(f"❌ CloudFormation設定取得エラー: {e}")
            raise
    
    def get_all_config(self) -> dict:
        """すべての設定を取得（キャッシュ付き）"""
        if self._config is None:
            self._config = self._fetch_cloudformation_config()
        return self._config
    
    def get_cognito_config(self) -> dict:
        """Cognito設定のみを取得"""
        config = self.get_all_config()
        return {
            'region': config['region'],
            'user_pool_id': config['user_pool_id'],
            'client_id': config['client_id']
        }
    
    def get_gateway_config(self) -> dict:
        """Gateway設定のみを取得"""
        config = self.get_all_config()
        return {
            'region': config['region'],
            'gateway_id': config['gateway_id']
        }


# グローバルインスタンス
test_config = TestConfig()


if __name__ == "__main__":
    """設定テスト用のメイン関数（環境別対応）"""
    try:
        print("🔧 テスト設定を確認中...")
        
        # 環境情報を表示
        environment = os.environ.get('HEALTHMATE_ENV', 'dev')
        print(f"🌍 環境: {environment}")
        
        config = test_config.get_all_config()
        
        print("\n📋 取得した設定:")
        print(f"   環境: {environment}")
        print(f"   リージョン: {config['region']}")
        print(f"   User Pool ID (Healthmate-Core): {config['user_pool_id']}")
        print(f"   Client ID (Healthmate-Core): {config['client_id']}")
        print(f"   Gateway ID (Healthmate-HealthManager): {config['gateway_id']}")
        print("   ✅ Client Secretは使用しません（パブリッククライアント）")
        
        print("\n✅ 設定取得テスト完了")
        
    except Exception as e:
        print(f"\n❌ 設定取得テストエラー: {e}")
        import traceback
        traceback.print_exc()