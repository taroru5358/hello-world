# GitHub マージキュー入門

最終更新: 2026-11-12

## マージキューとは

複数の PR を main にマージするとき、PR 単体の CI が通っていても、他の PR と組み合わせると壊れることがある。
マージキューは、マージ直前の状態（最新の main + キュー内の先行 PR）で CI をやり直し、通ったものだけをまとめてマージする仕組み。

```
PR #1 ─┐
PR #2 ─┼─→ キュー（FIFO）─→ main + #1 で CI ─→ main + #1 + #2 で CI ─→ マージ
PR #3 ─┘
```

「Require branches to be up to date before merging」の代替になる。
開発者は PR ブランチを最新 main に rebase し直す必要がなく、キューが最新状態での検証を代行する。

## 利用要件（最初に確認する）

2026-11-12 時点の要件:

- **Organization 所有のリポジトリであること**
  - public リポジトリ: 無料プラン可
  - private リポジトリ: Organization + GitHub Enterprise Cloud
- 個人アカウント所有のリポジトリでは、public でもマージキューを有効化できない
- 対象ブランチに branch protection または ruleset を設定できる権限（admin）があること
- ワイルドカード（`*`）を含むブランチパターンでは有効化できない
- 必須ステータスチェックを設定する場合、CI が `merge_group` イベントに対応していること

個人アカウントで ruleset API を叩くと、次の 422 で拒否される。
パラメータの誤りではなく、機能自体が提供されていない。

```
Validation Failed
errors: ["Invalid rule 'merge_queue': "]
```

確認コマンド:

```bash
gh api repos/OWNER/REPO --jq '.owner.type'
# Organization なら "Organization"、個人なら "User"
```

`User` の場合は、無料の Organization を作ってリポジトリを移すのが現実的な回避策になる。
user → organization のアカウント変換は 2026-01-12 に廃止されているため、新規 Organization の作成とリポジトリの transfer が必要。

## 有効化（Web UI）

推奨は ruleset で設定する方法。

```
Repository > Settings > Rules > Rulesets > New ruleset > New branch ruleset
  Ruleset name: main merge queue
  Enforcement status: Active
  Target branches: Include default branch
  Rules:
    [x] Require merge queue
        Merge method: Squash
        Build concurrency: 5
        Only merge non-failing pull requests: ON
        Status check timeout: 60 minutes
        Maximum pull requests to merge: 5
        Minimum pull requests to merge: 1
        Wait time: 0 minutes
    [x] Require status checks to pass
        Required checks: demo-ci
  > Create
```

`Require merge queue` だけでは「キュー経由でマージする」ことしか強制しない。
CI を必須にするには、同じ ruleset で `Require status checks to pass` も有効にする。

## 有効化（gh api / ruleset JSON）

Organization 所有リポジトリで実行する。

```bash
cat > merge-queue-ruleset.json <<'JSON'
{
  "name": "main merge queue",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "merge_queue",
      "parameters": {
        "merge_method": "SQUASH",
        "grouping_strategy": "ALLGREEN",
        "max_entries_to_build": 5,
        "max_entries_to_merge": 5,
        "min_entries_to_merge": 1,
        "min_entries_to_merge_wait_minutes": 0,
        "check_response_timeout_minutes": 60
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "required_status_checks": [
          { "context": "demo-ci" }
        ],
        "strict_required_status_checks_policy": false
      }
    }
  ]
}
JSON

gh api repos/OWNER/REPO/rulesets -X POST --input merge-queue-ruleset.json
```

作成後の確認:

```bash
gh ruleset list --repo OWNER/REPO
gh ruleset view <RULESET_ID> --repo OWNER/REPO
```

既存 ruleset に後から追加する場合は、取得した JSON の `rules` 配列に `merge_queue` を足して PUT する。

```bash
gh api repos/OWNER/REPO/rulesets/<ID> > ruleset.json
# ruleset.json を編集
gh api repos/OWNER/REPO/rulesets/<ID> -X PUT --input ruleset.json
```

### パラメータの意味

| パラメータ | 意味 |
| --- | --- |
| `merge_method` | `MERGE` / `SQUASH` / `REBASE` |
| `grouping_strategy` | `ALLGREEN`: グループ内の各 PR が必須チェックを通ること。`HEADGREEN`: グループ先頭（全変更を含むコミット）だけ通ればよい |
| `max_entries_to_build` | 同時に `merge_group` の CI を走らせる最大数。大きくすると速いが CI 消費も増える |
| `max_entries_to_merge` | 1 グループでまとめてマージする最大 PR 数 |
| `min_entries_to_merge` | 1 グループにまとめる最小 PR 数 |
| `min_entries_to_merge_wait_minutes` | 最小数に達するまで待つ時間。過ぎたら少なくてもマージ |
| `check_response_timeout_minutes` | 必須チェックの応答を待つ上限。超えたら失敗扱い |

最初は `max_entries_to_build: 5`、`min_entries_to_merge: 1`、`min_entries_to_merge_wait_minutes: 0` で様子を見るのが簡単。

## CI 側の必須対応: `merge_group`

マージキューは `merge_group` イベントで CI を起動する。
`pull_request` だけでは、キューに入った PR の必須チェックが永遠に「待ち」になり、マージされない。

```yaml
on:
  pull_request:
  merge_group:

jobs:
  demo-ci:
    name: demo-ci
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "event=${{ github.event_name }}"
```

ポイント:

- **ワークフローファイルが main に存在している必要がある**。`merge_group` は main とキューの PR を合成した一時ブランチで動くため、PR ブランチにしかワークフローがないと起動しない
- 必須チェックの `context` はジョブ名と一致させる。上の例なら `demo-ci`
- `actions/checkout` は `merge_group` でもそのまま使える
- 第三步 CI を使う場合は `gh-readonly-queue/{base_branch}` で始まる一時ブランチへの push をトリガーにする

`merge_group` 対応を入れるだけでは何も起きない（キューが無いとイベントが発生しない）。
先に CI を main に入れ、その後にキューを有効化する順序が安全。

## 使い方

### PR をキューに入れる

Web UI:

```
PR ページ > Merge when ready > Confirm merge when ready
```

CLI:

```bash
# 必須チェックが通過済みならキューに入る
gh pr merge 123

# チェック待ちの場合は auto-merge を有効化する
gh pr merge 123 --auto
```

`--merge-queue` という専用フラグは無い。
対象ブランチがキュー必須の場合、`gh pr merge` の挙動が自動でキュー投入に切り替わる。

`--auto` を使うには、リポジトリ設定で auto-merge が許可されている必要がある。

```
Settings > General > Allow auto-merge
```

### キューから外す

PR ページの `Remove from queue` から外す。`gh` CLI には dequeue コマンドが無い。
キュー一覧は `Branches` ページ、または対象ブランチの `Merge queue` 表示で確認する。

### 管理者がキューを迂回する

```bash
gh pr merge 123 --admin
```

## キュー内の挙動

- FIFO。到着順に処理される
- 一時ブランチ `gh-readonly-queue/main/pr-123`（UI では `main/pr-123`）が作られ、`merge_group` の `checks_requested` が飛ぶ
- 成功すると、その時点までの PR がまとめて main に入る
- 失敗した PR はキューから外され、後続の PR だけでグループを作り直す
- キューの先頭に割り込む（Jump to top）と、進行中の全 PR が再ビルドされる。多用すると遅くなる
- キュー待ち中に PR を push すると、その PR はグループから外れて再検証になる
- 必須チェックの失敗、タイムアウト、コンフリクト、branch protection 違反が除外理由になる。理由は PR のタイムラインに出る

## 落とし穴

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| キューに入るが永遠に待つ | CI が `merge_group` に対応していない | ワークフローに `merge_group` を追加し、main にマージしておく |
| 必須チェックが見つからない | `context` 名の不一致 | ジョブ名と ruleset の `context` を完全一致させる |
| 422 `Invalid rule 'merge_queue'` | 個人アカウント所有のリポジトリ | Organization 所有リポジトリに移す |
| `gh pr merge` が auto-merge エラー | リポジトリで auto-merge が無効 | Settings > General > Allow auto-merge を有効化 |
| キューが詰まる | 必須チェックのタイムアウトが長い、同時ビルド数が少ない | `check_response_timeout_minutes` と `max_entries_to_build` を調整 |
| マージが遅い | `min_entries_to_merge` が大きい | 1 にして、まとめマージが必要になってから増やす |

## このリポジトリでの確認結果

`taroru5358/hello-world` は個人アカウント（`owner.type == "User"`）所有の public リポジトリのため、マージキューは有効化できない。
2026-11-12 に ruleset API へ `merge_queue` を送信し、次の 422 を確認した。

```
Validation Failed
errors: ["Invalid rule 'merge_queue': "]
```

代わりに、同じリポジトリでスタック PR を試すことはできる。
マージキューを実際に動かす場合は、無料の Organization を作成し、このリポジトリを transfer するか、Organization 配下に検証用リポジトリを作る。

このリポジトリには、そのまま使える CI（`.github/workflows/demo-ci.yml`）と、ruleset を適用するスクリプト（`scripts/setup-merge-queue.sh`）を置いてある。
