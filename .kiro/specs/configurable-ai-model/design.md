# Design Document

## Overview

Healthmate-CoachAIエージェントのモデル設定を環境変数化する機能です。現在ハードコードされているモデル識別子を環境変数 `HEALTHMATE_AI_MODEL` から取得するように変更します。

## Architecture

### Current Implementation

```python
# 現在の実装（ハードコード）
return Agent(
    model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    tools=[list_health_tools, health_manager_mcp],
    session_manager=session_manager,
    system_prompt=system_prompt
)
```

### Proposed Implementation

```python
# 提案する実装（環境変数から取得）
model_id = os.environ.get('HEALTHMATE_AI_MODEL')
if not model_id:
    raise Exception("環境変数 HEALTHMATE_AI_MODEL が設定されていません")

return Agent(
    model=model_id,
    tools=[list_health_tools, health_manager_mcp],
    session_manager=session_manager,
    system_prompt=system_prompt
)
```

## Components and Interfaces

### Modified Function

**Function**: `_create_health_coach_agent_with_memory`

**Location**: `healthmate_coach_ai/agent.py`

**Changes**:
1. 環境変数 `HEALTHMATE_AI_MODEL` を読み取る
2. 環境変数が未設定の場合は例外を発生させる
3. 取得したモデル識別子を `Agent` コンストラクタに渡す

### Environment Variable

**Name**: `HEALTHMATE_AI_MODEL`

**Type**: String

**Format**: モデル識別子（例："global.anthropic.claude-sonnet-4-5-20250929-v1:0"）

**Required**: Yes

**Example Values**:
- `global.anthropic.claude-sonnet-4-5-20250929-v1:0`
- `global.anthropic.claude-3-5-sonnet-20241022-v2:0`
- その他のBedrockでサポートされるモデル識別子

## Data Models

環境変数の読み取りのみで、新しいデータモデルは不要です。

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Environment variable reading

*For any* execution of the agent initialization, if the environment variable `HEALTHMATE_AI_MODEL` is set, then the agent should use that exact model identifier.

**Validates: Requirements 1.1**

### Property 2: Error on missing configuration

*For any* execution of the agent initialization, if the environment variable `HEALTHMATE_AI_MODEL` is not set, then the system should raise an exception and not create an agent.

**Validates: Requirements 1.2**

## Error Handling

### Missing Environment Variable

**Condition**: `HEALTHMATE_AI_MODEL` が設定されていない

**Action**: 
- `Exception` を発生させる
- エラーメッセージ: "環境変数 HEALTHMATE_AI_MODEL が設定されていません"
- エージェントの初期化を中止

### Invalid Model Identifier

**Condition**: 無効なモデル識別子が指定された場合

**Action**:
- Strands Agent SDKが自動的にエラーを発生させる
- エラーは呼び出し元に伝播される

## Testing Strategy

### Unit Tests

単体テストでは以下をテストします：

1. **環境変数が設定されている場合**: 正しいモデル識別子が使用されることを確認
2. **環境変数が未設定の場合**: 例外が発生することを確認

### Property-Based Tests

プロパティベーステストでは以下をテストします：

1. **Property 1**: 任意の有効なモデル識別子文字列に対して、環境変数に設定した値がAgentに渡されることを確認
2. **Property 2**: 環境変数が未設定の状態で、必ず例外が発生することを確認

### Integration Tests

統合テストでは以下をテストします：

1. 実際の環境変数を設定してエージェントが正常に動作することを確認
2. 異なるモデル識別子で動作することを確認