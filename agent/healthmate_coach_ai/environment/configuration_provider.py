"""
Configuration Provider - 環境固有設定の提供

CloudFormation Stack名の環境別生成に特化したシステム
依存するサービスはCloudFormation OutputsとExportsから必要な情報を取得する
"""

import os
from .environment_manager import EnvironmentManager


class ConfigurationProvider:
    """環境固有設定の提供"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.environment = EnvironmentManager.get_environment()
    
    def get_stack_name(self, base_stack_name: str) -> str:
        """CloudFormation Stack名の環境別生成
        
        Args:
            base_stack_name: ベースとなるStack名（例: "Healthmate-CoachAIStack"）
            
        Returns:
            環境別Stack名（例: "Healthmate-CoachAIStack-dev"、prod環境では"Healthmate-CoachAIStack"）
        """
        if self.environment == "prod":
            return base_stack_name
        return f"{base_stack_name}-{self.environment}"
    
    def get_aws_region(self) -> str:
        """AWS リージョンの取得
        
        Returns:
            AWS リージョン（環境変数AWS_REGIONまたはデフォルトのus-west-2）
        """
        return os.environ.get("AWS_REGION", "us-west-2")
    
    def get_environment_suffix(self) -> str:
        """環境サフィックスの取得
        
        Returns:
            環境サフィックス（prod環境では空文字、他環境では-{env}）
        """
        if self.environment == "prod":
            return ""
        return f"-{self.environment}"