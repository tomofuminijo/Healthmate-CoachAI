"""
Log Controller - 環境別ログ制御

環境に応じたログレベル制御と構造化ログを提供するシステム
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any
from .environment_manager import EnvironmentManager


class LogController:
    """環境別ログ制御"""
    
    LOG_LEVELS = {
        "dev": logging.DEBUG,
        "stage": logging.INFO,
        "prod": logging.WARNING
    }
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.environment = EnvironmentManager.get_environment()
        self.setup_logging()
    
    def setup_logging(self):
        """ログ設定の初期化"""
        log_level = self.LOG_LEVELS.get(self.environment, logging.INFO)
        
        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # 既存のハンドラーをクリア
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 新しいハンドラーを追加
        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        
        if self.environment == "dev":
            # 開発環境：人間が読みやすい形式
            formatter = DevFormatter(self.service_name, self.environment)
        else:
            # stage/prod環境：JSON形式
            formatter = JSONFormatter(self.service_name, self.environment)
        
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        
        # ログレベル変更をログに記録
        logging.info(f"Log level set to {logging.getLevelName(log_level)} for environment {self.environment}")
    
    def get_logger(self, name: str) -> logging.Logger:
        """サービス固有ロガーの取得"""
        logger = logging.getLogger(name)
        # サービス名と環境をコンテキストに追加
        logger = logging.LoggerAdapter(logger, {
            'service': self.service_name,
            'environment': self.environment
        })
        return logger


class DevFormatter(logging.Formatter):
    """開発環境用のログフォーマッター"""
    
    def __init__(self, service_name: str, environment: str):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
    
    def format(self, record: logging.LogRecord) -> str:
        # サービス名と環境をレコードに追加
        record.service = self.service_name
        record.environment = self.environment
        
        # 基本フォーマット
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(service)s:%(environment)s] - %(message)s'
        )
        return formatter.format(record)


class JSONFormatter(logging.Formatter):
    """JSON形式のログフォーマッター"""
    
    def __init__(self, service_name: str, environment: str):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service': self.service_name,
            'environment': self.environment,
            'message': record.getMessage(),
            'logger': record.name
        }
        
        # 例外情報がある場合は追加
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # 追加のコンテキスト情報
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        
        return json.dumps(log_entry, ensure_ascii=False)


class LoggingError(Exception):
    """ログ関連のエラー"""
    pass


def safe_logging_setup(service_name: str) -> LogController:
    """安全なログ設定"""
    try:
        return LogController(service_name)
    except Exception as e:
        # フォールバック：基本的なログ設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to setup advanced logging: {e}")
        logger.info("Using fallback logging configuration")
        return None