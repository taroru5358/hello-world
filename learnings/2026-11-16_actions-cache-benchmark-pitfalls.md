# Actions キャッシュ計測で踏んだ落とし穴

## 1. グローバル gitignore で package-lock.json が除外されていた

- 症状: CI で `Cannot find module './package-lock.json'`
- 原因: `~/.gitignore_global` に `package-lock.json` がある。`git add -A` で黙って除外された
- 対策: プロジェクトの `.gitignore` に `!package-lock.json`。`git check-ignore -v <file>` で原因の ignore ファイルを特定できる

## 2. macOS で作った lockfile では Linux の npm ci が失敗する

- 症状: ubuntu-latest で `npm ci` が optional dependency（`@emnapi/*` などネイティブバインディング系）の不足で失敗
- 対策: `docker run --rm -v "$PWD":/app -w /app node:24 npm install` で Linux 上で lockfile を生成

## 3. actions/cache の cache-hit は miss 時に空文字になることがある

- `'false'` を期待して比較するとずれる。`steps.x.outcome == 'success' && (steps.x.outputs.cache-hit == 'true' && 'true' || 'false') || ''` で正規化した

## 4. setup-node v5 以降は packageManager があると自動キャッシュ

- キャッシュなしを測るには `package-manager-cache: false` が必要

## 5. workflow_dispatch は default branch に workflow が必要

- 一度 main に入れば、`gh workflow run --ref <branch>` で branch 上の変更を試せる（今回 #38 の事前検証に使用）
