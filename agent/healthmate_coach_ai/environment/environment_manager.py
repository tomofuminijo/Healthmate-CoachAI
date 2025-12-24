"""
Environment Manager - 環境設定の統合管理

HEALTHMATE_ENV環境変数に基づいて環境設定を管理するシステム
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EnvironmentManager:
    """環境設定の統合管理"""
    
    VALID_ENVIRONMENTS = ["dev", "stage", "prod"]
    DEFAULT_ENVIRONMENT = "dev"
    
    @classmethod
    def get_environment(cls) -> str:
        """現在の環境を取得"""
        env = os.environ.get("HEALTHMATE_ENV", cls.DEFAULT_ENVIRONMENT)
        if env not in cls.VALID_ENVIRONMENTS:
            logger.error(f"Invalid environment: {env}, defaulting to {cls.DEFAULT_ENVIRONMENT}")
            return cls.DEFAULT_ENVIRONMENT
        logger.info(f"Environment detected: {env}")
        return env
    
    @classmethod
    def validate_environment(cls, env: str) -> bool:
        """環境値の検証"""
        return env in cls.VALID_ENVIRONMENTS
    
    @classmethod
    def is_production(cls) -> bool:
        """本番環境かどうか"""
        return cls.get_environment() == "prod"
    
    @classmethod
    def is_development(cls) -> bool:
        """開発環境かどうか"""
        return cls.get_environment() == "dev"
    
    @classmethod
    def is_staging(cls) -> bool:
        """ステージング環境かどうか"""
        return cls.get_environment() == "stage"


class EnvironmentError(Exception):
    """環境設定関連のエラー"""
    pass


class InvalidEnvironmentError(EnvironmentError):
    """無効な環境値エラー"""
    def __init__(self, environment: str):
        self.environment = environment
        super().__init__(f"Invalid environment: {environment}")


class ConfigurationError(EnvironmentError):
    """設定エラー"""
    pass


def handle_environment_error(func):
    """環境エラーハンドリングデコレータ"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except InvalidEnvironmentError as e:
            logger.error(f"Environment error: {e}")
            # デフォルト環境にフォールバック
            return EnvironmentManager.DEFAULT_ENVIRONMENT
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in environment management: {e}")
            raise EnvironmentError(f"Environment management failed: {e}")
    return wrapper