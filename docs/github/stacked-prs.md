# GitHub スタック PR 入門

最終更新: 2026-11-12

## スタック PR とは

大きな変更を、依存関係のある小さな PR に分割する方法。
下のブランチの変更を前提に、上のブランチを積み上げる。

```
frontend      → PR #3 (base: api)
api           → PR #2 (base: auth)
auth          → PR #1 (base: main)   ← bottom
─────────────
main (trunk)
```

- **bottom**: trunk に最も近いブランチ
- **top**: trunk から最も遠いブランチ
- 各 PR の base は「1 つ下のブランチ」になる
- レビュアーには、その層の差分だけが見える

2026-10-06 に一般提供（GA）された。
GitHub.com の全プランで利用でき、GitHub Enterprise Server は今後のリリースで対応予定。
同一リポジトリ内のブランチ連鎖のみ対応し、フォークをまたぐスタックは作れない。

## インストール

GitHub CLI の公式拡張を使う。

```bash
gh --version          # 2.90 以上を推奨
git --version         # 2.36 以上
gh auth login
gh extension install github/gh-stack
gh stack --version
```

更新:

```bash
gh extension upgrade stack
```

AI エージェント向けのスキルも配布されている（任意）。

```bash
gh skill install github/gh-stack
```

## クイックスタート

```bash
# 1. スタックの最初のブランチを作る
gh stack init auth

# 2. 1 層目を実装してコミット
git add .
git commit -m "認証レイヤーを追加"

# 3. 2 層目を積む
gh stack add api

# 4. 2 層目を実装してコミット
git add .
git commit -m "API エンドポイントを追加"

# 5. 3 層目を積む
gh stack add frontend
git add .
git commit -m "画面を追加"

# 6. 全ブランチを push して PR を作る
gh stack submit

# 7. 状態確認
gh stack view
gh stack view --short
gh stack view --json
```

`gh stack submit` は以下をまとめて行う。

- 全ブランチを atomic に push
- ブランチごとに PR を作成
- 各 PR の base を 1 つ下のブランチに設定
- GitHub 上で PR 同士を Stack としてリンク

## 日常の操作

### 層の間を移動する

```bash
gh stack up          # 1 層上へ
gh stack up 2        # 2 層上へ
gh stack down        # 1 層下へ
gh stack top         # 最上層へ
gh stack bottom      # 最下層へ
gh stack trunk       # main へ
gh stack switch      # 対話的に選択
```

### 下の層を直したとき

下の層を変更したら、上の層を rebase して追従させる。

```bash
gh stack bottom
# 修正してコミット
gh stack rebase --upstack
gh stack push
```

### main の変更に追従する

```bash
gh stack sync
```

`sync` は次をまとめて行う。

1. `origin` から fetch
2. リモートのスタック状態とローカルを照合
3. trunk を fast-forward
4. 各層を順に rebase
5. push（rebase した場合は `--force-with-lease`）
6. PR の状態を同期
7. マージ済みブランチの削除を提案（`--prune` で自動削除）

コンフリクトした場合は中断されるので、`gh stack rebase` で個別に解消する。

### スタックを組み替える

```bash
gh stack modify
```

対話 UI で、層の削除（Drop）、折りたたみ（Fold）、挿入（Insert）、並べ替え（Reorder）、名前変更（Rename）ができる。
変更後は `gh stack submit` で GitHub 側に反映する。

## PR の作り方（手動でも可）

`gh stack` を使わない場合は、base を手で連鎖させる。

```bash
git switch -c auth main
# 実装・コミット
git push -u origin auth
gh pr create --base main --head auth --title "認証レイヤー"

git switch -c api auth
# 実装・コミット
git push -u origin api
gh pr create --base auth --head api --title "API エンドポイント"

git switch -c frontend api
# 実装・コミット
git push -u origin frontend
gh pr create --base api --head frontend --title "画面"
```

後からスタックとしてリンクするだけなら `gh stack link` が使える。

```bash
gh stack link auth api frontend
gh stack link 10 20 30
```

## マージ

```bash
# 現在のスタックを対話的にマージ
gh stack merge

# 確認なしで一括マージ
gh stack merge --yes

# PR #42 まで（下位を含む）をマージ
gh stack merge 42
```

マージは bottom から順にしかできない。
途中の PR だけを単独でマージすることはできない。

### マージキューと併用する

base ブランチ（通常は main）がマージキュー必須の場合、`gh stack merge` は直接マージせず、スタック全体をキューに入れる。

```bash
gh stack merge --yes
```

- キューがマージ方法を決めるため、`--squash` などの指定は無視される
- スタックは正しい順序でキューに入る
- 1 つの PR がキューから外れると、上位の PR も連動して外れる
- グループ上限を超えそうな場合は、自動的に複数グループに分割される

## 制約

- 同一リポジトリ内のブランチのみ。フォークをまたげない
- 線形履歴が前提。merge commit が混ざった履歴は扱いにくい
- GitHub Desktop はスタック作成に対応していない
- サーバー側の `Rebase stack` は署名なしのコミットを作る。署名必須のリポジトリでは `gh stack rebase` を使う
- `gh stack modify` は working tree が clean で、rebase 中でなく、キューに入っている PR が無いことが前提

## トラブルシューティング

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `gh stack` が無い | 拡張未インストール | `gh extension install github/gh-stack` |
| スタックが認識されない | ローカルメタデータが無い | `gh stack checkout <PR番号>` で取り込む |
| rebase がコンフリクトした | 下の層と衝突 | 手で解消 → `git add` → `gh stack rebase --continue` |
| PR の base がずれた | 手動で PR を編集した | `gh stack submit` で再設定 |
| マージできない | 下位の PR が未マージ | bottom から順にマージする |
| スタックをやめたい | — | `gh stack unstack`（GitHub 側も解除） / `--local` でローカルのみ |

## 参考

- スタック PR の概要: https://docs.github.com/en/pull-requests/get-started/about-stacked-prs
- クイックスタート: https://docs.github.com/en/pull-requests/get-started/stacked-prs-quickstart
- CLI リファレンス: https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands
- gh-stack: https://github.com/github/gh-stack
