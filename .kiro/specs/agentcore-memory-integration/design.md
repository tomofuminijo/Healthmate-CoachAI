# AgentCore Memory統合 - 設計書

## 概要

HealthCoachAIエージェントにAmazon Bedrock AgentCore Memoryを統合し、Strandsエージェントフレームワークを使用した適切なセッション管理と会話継続性を実現する。

## アーキテクチャ

### 現在のアーキテクチャ
```
HealthmateUI → AgentCore Runtime → HealthCoachAI (Strands Agent)
                                      ↓
                                  Manual Session Context (Global Variables)
```

### 新しいアーキテクチャ
```
HealthmateUI → AgentCore Runtime → HealthCoachAI (Strands Agent)
                                      ↓
                                  AgentCore Memory (STM)
                                      ↓
                                  AgentCoreMemorySessionManager
```

## コンポーネントと インターフェース

### 1. メモリリソース管理
- **AgentCore Memory Resource**: AWS上の永続メモリリソース
- **Memory Mode**: STM_ONLY（短期メモリのみ）
- **Event Expiry**: 30日間の自動期限切れ

### 2. Strandsエージェント統合
- **AgentCoreMemorySessionManager**: Strands用のセッション管理クラス
- **AgentCoreMemoryConfig**: メモリ設定クラス
- **Session Manager Integration**: Strandsエージェントとの統合

### 3. セッション管理
- **Session ID**: フロントエンドから提供される33文字以上の識別子
- **Actor ID**: JWTトークンのsubフィールドから抽出されるユーザーID
- **Memory Session**: AgentCore Memoryでのセッション管理

## データモデル

### AgentCoreMemoryConfig
```python
@dataclass
class AgentCoreMemoryConfig:
    memory_id: str          # メモリリソースID
    session_id: str         # セッション識別子（33文字以上）
    actor_id: str          # ユーザー識別子（JWT sub）
    region_name: str       # AWSリージョン
```

### Memory Session Context
```python
class MemorySessionContext:
    memory_session_manager: AgentCoreMemorySessionManager
    config: AgentCoreMemoryConfig
    is_active: bool
```

### Payload Structure
```python
class AgentCorePayload:
    prompt: str
    jwt_token: str
    timezone: str
    language: str
    session_id: str        # フロントエンドから提供
    session_state: Dict[str, Any]
```

## 正確性プロパティ

*プロパティとは、システムのすべての有効な実行において真であるべき特性や動作のことです。プロパティは、人間が読める仕様と機械で検証可能な正確性保証の橋渡しをします。*

### プロパティ1: メモリセッション管理の一貫性
*任意の* 有効なセッションIDとactor_IDの組み合わせに対して、AgentCoreMemorySessionManagerが作成され、同じ設定で初期化される場合、セッション管理が一貫して動作する
**検証対象: 要件 1.1**

### プロパティ2: セッション分離の保証
*任意の* 2つの異なるセッションIDに対して、一方のセッションで保存された情報が他方のセッションで参照されることはない
**検証対象: 要件 2.3**

### プロパティ3: ユーザー情報の永続性
*任意の* 同じactor_IDを持つセッションに対して、ユーザー固有の情報は新しいセッションでも保持される
**検証対象: 要件 2.4**

### プロパティ4: MCP機能の保持
*任意の* メモリ統合後のエージェントに対して、既存のMCPツール（list_health_tools、health_manager_mcp）が正常に動作する
**検証対象: 要件 1.5**

### プロパティ5: セッションID要件の遵守
*任意の* 生成されるセッションIDに対して、その長さは33文字以上でなければならない
**検証対象: 要件 5.3**

### プロパティ6: JWT処理の一貫性
*任意の* 有効なJWTトークンに対して、subフィールドが正しく抽出されてactor_idとして使用される
**検証対象: 要件 5.2**

### プロパティ7: ペイロード処理の堅牢性
*任意の* セッション情報を含むペイロードに対して、セッション情報が正しくパースされて使用される
**検証対象: 要件 5.4**

### プロパティ8: エラー時のフォールバック動作
*任意の* メモリエラーが発生した場合に対して、エージェントはフォールバック動作で会話を継続する
**検証対象: 要件 5.5**

### プロパティ9: メモリ操作の正確性
*任意の* 会話データに対して、メモリへの保存と取得が正確に行われる
**検証対象: 要件 4.4**

### プロパティ10: エラーハンドリングの適切性
*任意の* エラー状況に対して、適切なエラーメッセージとログが出力される
**検証対象: 要件 4.5**

## エラーハンドリング

### 1. メモリリソースエラー
- **Memory Not Found**: メモリIDが無効な場合のフォールバック
- **Memory Not Active**: メモリリソースがACTIVE状態でない場合の待機
- **Permission Denied**: IAM権限不足の場合のエラー処理

### 2. セッション管理エラー
- **Invalid Session ID**: セッションIDが無効な場合のデフォルト生成
- **Session Creation Failed**: セッション作成失敗時のリトライ機構
- **Memory Session Error**: メモリセッションエラー時のフォールバック

### 3. JWT処理エラー
- **JWT Decode Error**: JWTデコード失敗時のデフォルトactor_id使用
- **Missing Sub Field**: subフィールドがない場合の匿名ユーザー処理
- **Token Expired**: トークン期限切れ時のエラー処理

## テスト戦略

### 単体テスト
- AgentCoreMemoryConfigの設定検証
- セッションID生成とバリデーション
- JWT処理とactor_ID抽出
- エラーハンドリングの動作確認

### プロパティベーステスト
- **プロパティテストライブラリ**: pytest + hypothesis
- **最小実行回数**: 100回の反復実行
- **テスト対象**: 上記の正確性プロパティ
- **テストタグ**: 各プロパティテストに対応する設計書プロパティ番号を明記

### 統合テスト
- ローカル環境でのメモリ機能テスト（manual_test_agent.py）
- デプロイ環境でのセッション継続性テスト（manual_test_deployed_agent.py）
- フロントエンドとの統合テスト

### エンドツーエンドテスト
- 実際のユーザーシナリオでの会話継続性テスト
- 複数セッションでのデータ分離テスト
- 長時間セッションでのメモリ保持テスト

## 実装計画

### フェーズ1: 依存関係とメモリリソース
1. requirements.txtの更新（bedrock-agentcore[strands-agents]追加）
2. AgentCore Memoryリソースの作成
3. .bedrock_agentcore.yamlの設定更新

### フェーズ2: エージェントコード統合
1. AgentCoreMemorySessionManagerの統合
2. 既存のグローバル変数ベースのセッション管理の置き換え
3. エラーハンドリングの実装

### フェーズ3: テストとデプロイ
1. テストスクリプトの更新
2. ローカル環境でのテスト
3. デプロイとデプロイ環境でのテスト

### フェーズ4: 検証と最適化
1. セッション継続性の検証
2. パフォーマンス最適化
3. エラー処理の改善