# AgentCore Memory統合 - 要件定義

## 概要

HealthCoachAIエージェントにAmazon Bedrock AgentCore Memoryを正しく統合し、会話の継続性とセッション管理を実現する。

## 用語集

- **AgentCore Memory**: Amazon Bedrock AgentCoreの永続メモリサービス
- **STM (Short-Term Memory)**: 短期メモリ（会話イベント）
- **LTM (Long-Term Memory)**: 長期メモリ（セマンティック検索）
- **Session Manager**: Strandsエージェント用のセッション管理クラス
- **Actor ID**: ユーザーを識別する一意のID（JWTのsubフィールド）
- **Session ID**: 会話セッションを識別する一意のID

## 要件

### 要件1

**ユーザーストーリー:** HealthCoachAIの開発者として、AgentCore Memoryを正しく統合したいので、会話の継続性が保たれるようにしたい。

#### 受入基準

1. WHEN Strandsエージェントが初期化される THEN AgentCoreMemorySessionManagerが適切に設定される
2. WHEN メモリリソースが作成される THEN STM_ONLYモードで動作する
3. WHEN エージェントがデプロイされる THEN .bedrock_agentcore.yamlにメモリ設定が含まれる
4. WHEN 依存関係がインストールされる THEN bedrock-agentcore[strands-agents]パッケージが含まれる
5. WHEN メモリ統合が完了する THEN 既存のMCPツール機能が維持される

### 要件2

**ユーザーストーリー:** ユーザーとして、同じセッションで複数のメッセージを送信したいので、AIが前の会話内容を覚えているようにしたい。

#### 受入基準

1. WHEN ユーザーが「私の名前はジョニーです」と言う THEN エージェントがその情報をメモリに保存する
2. WHEN 同じセッションで「私の名前は何ですか？」と質問する THEN エージェントが「ジョニー」と答える
3. WHEN 異なるセッションIDで会話する THEN 前のセッションの情報は参照されない
4. WHEN 同じユーザーIDで新しいセッションを開始する THEN ユーザー固有の情報は保持される
5. WHEN セッションが長時間続く THEN メモリの自動期限切れまで会話履歴が保持される

### 要件3

**ユーザーストーリー:** システム管理者として、メモリリソースを管理したいので、適切なCLIコマンドでメモリを作成・監視できるようにしたい。

#### 受入基準

1. WHEN agentcore memory createコマンドを実行する THEN 新しいメモリリソースが作成される
2. WHEN メモリリソースが作成される THEN ACTIVEステータスになるまで待機する
3. WHEN agentcore memory listコマンドを実行する THEN 既存のメモリリソースが表示される
4. WHEN メモリIDが設定される THEN 環境変数または設定ファイルで管理される
5. WHEN メモリリソースが不要になる THEN agentcore memory deleteで削除できる

### 要件4

**ユーザーストーリー:** 開発者として、メモリ統合をテストしたいので、ローカルとデプロイ環境の両方で動作確認できるようにしたい。

#### 受入基準

1. WHEN manual_test_agent.pyを実行する THEN ローカル環境でメモリ機能をテストできる
2. WHEN manual_test_deployed_agent.pyを実行する THEN デプロイ環境でセッション継続性をテストできる
3. WHEN テストスクリプトを実行する THEN 同じセッションIDで複数回の会話をテストできる
4. WHEN メモリが正常に動作する THEN 会話履歴の取得と保存が確認できる
5. WHEN エラーが発生する THEN 適切なエラーメッセージとログが出力される

### 要件5

**ユーザーストーリー:** HealthmateUIの開発者として、フロントエンドからのセッションIDが正しく処理されるようにしたいので、エージェント側でセッション管理が統合されるようにしたい。

#### 受入基準

1. WHEN フロントエンドからセッションIDが送信される THEN エージェントがそのIDを使用してメモリセッションを作成する
2. WHEN JWTトークンからユーザーIDが抽出される THEN そのIDをactor_idとして使用する
3. WHEN セッションIDが33文字以上である THEN AgentCore Runtimeの要件を満たす
4. WHEN ペイロードにセッション情報が含まれる THEN 適切にパースして使用される
5. WHEN メモリエラーが発生する THEN フォールバック動作で会話を継続する