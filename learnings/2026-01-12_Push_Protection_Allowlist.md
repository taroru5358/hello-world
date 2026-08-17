# Secret Scanning Push Protection - ホワイトリスト許可プロセス

## 概要

GHAS検証用のダミーシークレットをGitHubへpushする際に、Secret Scanning push protectionがブロックした。本ドキュメントは、この許可プロセスと、コードレベルでの設定の可能性をまとめたもの。

## 発生した状況

### ブロック内容
```
- Stripe Test API Secret Key
  locations: .env.example:15, config.py:24

- Slack API Token
  locations: .env.example:32, config.py:31
```

### 理由
- ダミーシークレットが実際の形式（`sk_test_*`, `xoxb-*`）と完全一致
- Secret Scanning パターンマッチが形式で検出
- Push protection がデフォルト有効（パブリックリポジトリ）

## 許可プロセス

### 方法 1: GitHub UI での個別許可（実施済み✅）

各ブロックされたシークレットに対して、GitHub が提供するリンクを訪問：

```
https://github.com/160294w/hello-world/security/secret-scanning/unblock-secret/<SECRET_ID>
```

画面上で以下を選択：
- "Allow and push" ボタンをクリック
- このシークレット形式をリポジトリで許可

### 利点
- GUI で明示的に許可判定を行う
- 監査ログに記録される
- リポジトリ管理者による厳密なコントロール

### 欠点
- UI操作が必要（スクリプト化できない）
- 同じ形式の複数のシークレットは別々に許可が必要

## 試みた方法 2: `.github/secret_scanning.yml`（未対応）

GHAS設定ファイルとして以下を作成：

```yaml
version: 1
patterns:
  - pattern: 'sk_test_4eC39HqLyjWDarhtT657G78z'
    comment: 'Dummy Stripe test key for GHAS validation'
```

### 結果
❌ **この方法は機能しなかった**

理由：
- `secret_scanning.yml` は公式な設定ファイルではない
- Secret Scanning push protection は UIベースの許可システムのみ対応
- コード内での許可パターン定義は現在サポートされていない

## GitHub公式の推奨方法

### 組織レベルでの許可設定

組織の Secret scanning settings で、特定のパターンをホワイトリスト登録：

```
Organization > Settings > Code security and analysis > Secret scanning
```

ただしこれも UI ベースであり、コード化はできない。

## ベストプラクティス

### 1. 本番環境では
- シークレットを コードに含めない
- 環境変数または secrets manager を使用
- `.env` は `.gitignore` に追加

### 2. GHAS検証・教育目的では
- ダミーシークレットを明らかにダミーと識別できる形式で
  * "EXAMPLE" サフィックス
  * "0000..." プリフィックス
  * "test_" prefix（Stripe等）

### 3. Push protection ブロック対応
- GitHub UI でのホワイトリスト許可が標準方法
- 許可判定は人間が行う（自動許可は推奨されない）
- 許可履歴は audit log に記録

## 技術的考察

### なぜコード化できないのか

Secret Scanning push protection の設計思想：

1. **セキュリティ第一**
   - コード化されたホワイトリストは改ざんの可能性
   - 人間による判定が必要

2. **使用ユースケース**
   - 本来的に「許可すべきでない」シークレットの方が大多数
   - 許可が例外的 → 厳密性を保つため UI 限定

3. **防御深度**
   - 複数の防衛層を構築
   - コード側で許可 + GitHub 側でも検証

## まとめ

### 今回の許可プロセス
1. Push がブロック
2. GitHub UI リンクにアクセス
3. 管理者が内容を確認 → 許可
4. 同じシークレット形式は以降 push 可能

### 記録すべき点
✅ ブロック理由が明確に提示される
✅ 許可判定が人間（管理者）に委ねられる
✅ 監査ログに記録される
✅ セキュリティと利便性のバランス

### セキュリティ評価
**十分に安全** - GHAS検証目的であれば
- ダミーシークレットは実際に使用不可
- 許可判定は慎重に行われる
- このブロック機能が正常に動作している証拠
