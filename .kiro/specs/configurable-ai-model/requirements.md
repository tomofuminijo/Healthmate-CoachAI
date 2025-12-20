# Requirements Document

## Introduction

Healthmate-CoachAIエージェントで使用するAIモデルを環境変数で設定可能にする機能です。現在はコード内にハードコードされているモデル名を、環境変数から取得するように変更します。

## Glossary

- **Agent**: Healthmate-CoachAIエージェント
- **Model_Identifier**: モデルを識別する文字列（例："global.anthropic.claude-sonnet-4-5-20250929-v1:0"）
- **Environment_Variable**: 環境変数による設定値

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want to configure the AI model through environment variables, so that I can change models without modifying code.

#### Acceptance Criteria

1. WHEN the environment variable HEALTHMATE_AI_MODEL is set, THE Agent SHALL use the specified model identifier
2. WHEN the environment variable HEALTHMATE_AI_MODEL is not set, THE Agent SHALL raise an error and stop execution
3. THE Agent SHALL read the environment variable during agent initialization