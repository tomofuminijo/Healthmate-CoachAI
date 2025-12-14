#!/usr/bin/env python3
"""
テスト用CloudFormation設定ヘルパー

CloudFormationスタックからCognito設定を動的に取得します。
"""

import os
import boto3
from typing import Optional
from botocore.exceptions import ClientError


class TestConfigHelper:
    """テスト用CloudFormation設定取得クラス"""
    
    def __init__(self):
        self._region: Optional[str] = None
        self._user_pool_id: Optional[str] = None
        self._client_id: Optional[str] = None
        self._client_secret: Optional[str] = None
        self._stack_outputs: Optional[dict] = None
    
    def _get_stack_name(self) -> str:
        """スタック名を環境変数またはデフォルト値から取得"""
        return os.environ.get('HEALTH_STACK_NAME', 'HealthManagerMCPStack')
    
    def _get_region(self) -> str:
        """AWSリージョンを取得"""
        if self._region is None:
            self._region = (
                os.environ.get('AWS_REGION') or 
                os.environ.get('AWS_DEFAULT_REGION') or
                boto3.Session().region_name or
                'us-west-2'
            )
        return self._region
    
    def _fetch_cloudformation_outputs(self) -> dict:
        """CloudFormationスタックの出力を取得（キャッシュ付き）"""
        if self._stack_outputs is not None:
            return self._stack_outputs
        
        try:
            stack_name = self._get_stack_name()
            region = self._get_region()
            
            cfn = boto3.client('cloudformation', region_name=region)
            response = cfn.describe_stacks(StackName=stack_name)
            
            if not response['Stacks']:
                raise Exception(f"CloudFormationスタック '{stack_name}' が見つかりません")
            
            outputs = {}
            for output in response['Stacks'][0].get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            self._stack_outputs = outputs
            return outputs
            
        except Exception as e:
            print(f"CloudFormation設定取得エラー（デフォルト値を使用）: {e}")
            # 環境変数からデフォルト値を取得
            self._stack_outputs = {
                'UserPoolId': os.environ.get('COGNITO_USER_POOL_ID', 'CONFIGURE_USER_POOL_ID'),
                'UserPoolClientId': os.environ.get('COGNITO_CLIENT_ID', 'CONFIGURE_CLIENT_ID'),
                'Region': self._get_region()
            }
            return self._stack_outputs
    
    def get_region(self) -> str:
        """リージョンを取得"""
        return self._get_region()
    
    def get_user_pool_id(self) -> str:
        """Cognito User Pool IDを取得"""
        if self._user_pool_id is None:
            outputs = self._fetch_cloudformation_outputs()
            self._user_pool_id = outputs.get('UserPoolId', os.environ.get('COGNITO_USER_POOL_ID', 'CONFIGURE_USER_POOL_ID'))
        return self._user_pool_id
    
    def get_client_id(self) -> str:
        """Cognito Client IDを取得"""
        if self._client_id is None:
            outputs = self._fetch_cloudformation_outputs()
            self._client_id = outputs.get('UserPoolClientId', os.environ.get('COGNITO_CLIENT_ID', 'CONFIGURE_CLIENT_ID'))
        return self._client_id
    
    def get_client_secret(self) -> str:
        """Cognito Client SecretをSDKで取得"""
        if self._client_secret is None:
            try:
                region = self.get_region()
                user_pool_id = self.get_user_pool_id()
                client_id = self.get_client_id()
                
                cognito = boto3.client('cognito-idp', region_name=region)
                response = cognito.describe_user_pool_client(
                    UserPoolId=user_pool_id,
                    ClientId=client_id
                )
                
                self._client_secret = response['UserPoolClient']['ClientSecret']
                
            except ClientError as e:
                print(f"Cognito Client Secret取得エラー: {e}")
                # 環境変数から取得を試行
                self._client_secret = os.environ.get('COGNITO_CLIENT_SECRET')
                if not self._client_secret:
                    raise Exception("Cognito Client Secretが取得できません。環境変数COGNITO_CLIENT_SECRETを設定するか、CloudFormationスタックを確認してください。")
            
        return self._client_secret
    
    def get_all_config(self) -> dict:
        """全ての設定を辞書で取得"""
        return {
            'region': self.get_region(),
            'user_pool_id': self.get_user_pool_id(),
            'client_id': self.get_client_id(),
            'client_secret': self.get_client_secret()
        }


# グローバルインスタンス
test_config = TestConfigHelper()