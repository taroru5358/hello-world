# マージキュー & スタック PR ハンズオン

最終更新: 2026-11-12

このリポジトリで実際に試した手順と、追加で試せる演習をまとめる。

## このリポジトリで実施済みのこと

| 項目 | 状態 | 場所 |
| --- | --- | --- |
| マージキュー対応 CI | 追加済み | `.github/workflows/demo-ci.yml` |
| マージキュー入門 | 追加済み | `docs/github/merge-queue.md` |
| スタック PR 入門 | 追加済み | `docs/github/stacked-prs.md` |
| マージキュー ruleset | **未設定（設定不可）** | 個人アカウント所有のため |
| スタック PR | 作成済み | PR #32〜#34 の 3 層（Stack #35） |

## 前提

```bash
gh --version
gh auth status
gh extension install github/gh-stack
```

`gh stack` が入っていない場合は先に拡張をインストールする。

```bash
gh extension install github/gh-stack
```

## パート 1: スタック PR を作る

このリポジトリでは、ドキュメントを 3 層に分けてスタックを作った。

```
docs/hands-on   → PR（この文書）      ← top
docs/stacked-prs → PR（スタックPR入門）
docs/merge-queue → PR（マージキュー入門） ← bottom
─────────────────
main
```

再現する場合の手順:

```bash
# main を最新にする
git switch main
git pull --ff-only origin main

# 1 層目
gh stack init docs/merge-queue
# ファイルを追加してコミット
git add docs/github/merge-queue.md scripts/setup-merge-queue.sh
git commit -m "マージキュー入門を追加"

# 2 層目
gh stack add docs/stacked-prs
git add docs/github/stacked-prs.md
git commit -m "スタックPR入門を追加"

# 3 層目
gh stack add docs/hands-on
git add docs/github/hands-on.md
git commit -m "ハンズオンを追加"

# まとめて push して PR を作成
gh stack submit --auto --open

# 確認
gh stack view
```

`gh stack submit` の後に GitHub の PR ページを開くと、PR ヘッダーにスタック全体が表示される。
各 PR の base が 1 つ下のブランチになっていることを確認する。

```bash
gh pr view <PR番号> --json baseRefName,headRefName,title
```

### 演習 1: 層を追加する

```bash
gh stack top
gh stack add docs/troubleshooting
# ファイルを追加してコミット
git add docs/github/troubleshooting.md
git commit -m "トラブルシューティングを追加"
gh stack submit --auto --open
```

4 層目の PR が、3 層目を base にして作られる。

### 演習 2: 下の層を直す

```bash
gh stack bottom
# 1 層目のファイルを修正してコミット
git add docs/github/merge-queue.md
git commit -m "マージキューの説明を修正"
gh stack rebase --upstack
gh stack push
```

上の層が自動で rebase され、PR の差分が更新される。

### 演習 3: スタックをマージする

```bash
gh stack merge
```

対話 UI でマージ対象とマージ方法を選ぶ。
bottom から順にマージされる。
main がマージキュー必須の場合は、直接マージではなくキュー投入になる。

## パート 2: マージキューを有効にする

### 注意: 個人アカウントでは設定できない

このリポジトリは `taroru5358` という個人アカウント所有（`owner.type == "User"`）のため、マージキューは有効化できない。
2026-11-12 に ruleset API へ送信して、次の 422 を確認済み。

```
Validation Failed
errors: ["Invalid rule 'merge_queue': "]
```

マージキューは **Organization 所有リポジトリ** が対象。
public なら無料プランで使える。

### Organization を用意する

1. https://github.com/organizations/plan を開く
2. Free プランを選ぶ
3. Organization 名を決めて作成する
4. リポジトリを移す
   - 既存リポジトリ: `Settings > General > Danger zone > Transfer ownership`
   - または Organization 配下に新しいリポジトリを作って push する

transfer するとリモート URL が変わるので、ローカル側を更新する。

```bash
git remote set-url origin https://github.com/ORG/hello-world.git
```

### ruleset を適用する

このリポジトリのスクリプトを使う。

```bash
./scripts/setup-merge-queue.sh ORG/hello-world demo-ci
```

スクリプトは以下を行う。

- `owner.type` が `Organization` か確認
- `main merge queue` という ruleset を作成（既にあれば更新）
- `demo-ci` を必須チェックに設定
- マージ方法は squash、グループ戦略は ALLGREEN

手動で UI から設定する場合:

```
Settings > Rules > Rulesets > New ruleset > New branch ruleset
  Target branches: Include default branch
  [x] Require merge queue
  [x] Require status checks to pass
      demo-ci
  Enforcement: Active
```

### CI の順序に注意

マージキューは `merge_group` イベントで CI を起動する。
`merge_group` のワークフローは main 上に存在する必要がある。

1. 先に `.github/workflows/demo-ci.yml` を main にマージする
2. その後で ruleset を有効にする

逆にすると、キューに入った PR の必須チェックが報告されず、タイムアウトまで待たされる。

### PR をキューに入れる

```bash
# 必須チェックが通過済みならキューに入る
gh pr merge <PR番号>

# チェック待ちなら auto-merge を有効化
gh pr merge <PR番号> --auto
```

`--auto` を使うには、リポジトリ設定で auto-merge を許可しておく。

```
Settings > General > Allow auto-merge
```

### キューに入ったときの確認ポイント

- PR のタイムラインに「Added to merge queue」が出る
- `Actions` に `merge_group` で起動した `Demo CI` が現れる
- 一時ブランチ `gh-readonly-queue/main/pr-<番号>` が作られる（UI では `main/pr-<番号>`）
- チェック通過後、PR が main にマージされる
- 失敗した場合は PR がキューから外れ、理由がタイムラインに出る

### 演習 4: キューから外す

PR ページの `Remove from queue` を押す。
`gh` CLI には dequeue コマンドが無いので、Web UI で操作する。

### 演習 5: キューの挙動を見る

1. 小さな PR を 2 つ作る
2. 両方の必須チェックを通す
3. 1 つ目をキューに入れる
4. 2 つ目をキューに入れる
5. `Actions` で `merge_group` の実行を確認する

2 つ目は「main + 1 つ目 + 2 つ目」の状態で CI が走る。
1 つ目が失敗すると、2 つ目だけのグループで再実行される。

## このリポジトリの既知の失敗

`CodeQL Analysis` は、リポジトリ側で default setup が有効なのに advanced configuration のワークフローも存在するため失敗する。
マージキューとスタック PR の検証には影響しない。
必須チェックには `demo-ci` だけを指定している。

## トラブルシューティング

| 症状 | 確認すること |
| --- | --- |
| ruleset 作成が 422 | `gh api repos/OWNER/REPO --jq .owner.type` が `Organization` か |
| キューで永遠に待つ | ワークフローに `merge_group` があるか、main にマージ済みか |
| 必須チェックが見つからない | ジョブ名と `context` が一致しているか |
| `gh pr merge` が auto-merge エラー | Settings > General > Allow auto-merge |
| スタック PR の base がおかしい | `gh stack submit` を再実行 |
| rebase がコンフリクト | 解消 → `git add` → `gh stack rebase --continue` |

## 後片付け

スタックのローカル管理だけを外す:

```bash
gh stack unstack --local
```

GitHub 上のスタックも解除する:

```bash
gh stack unstack
```

マージキューを止める:

```bash
# ruleset ID を確認
gh ruleset list --repo ORG/REPO
# ruleset を削除
gh api repos/ORG/REPO/rulesets/<ID> -X DELETE
```
