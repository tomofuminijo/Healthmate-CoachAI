"""
Environment Configuration Module for Healthmate-CoachAI

This module provides environment-specific configuration management for the CoachAI agent.
"""

from .environment_manager import EnvironmentManager, EnvironmentError, InvalidEnvironmentError, ConfigurationError
from .configuration_provider import ConfigurationProvider
from .log_controller import LogController, safe_logging_setup

__all__ = [
    'EnvironmentManager',
    'EnvironmentError', 
    'InvalidEnvironmentError',
    'ConfigurationError',
    'ConfigurationProvider',
    'LogController',
    'safe_logging_setup'
]