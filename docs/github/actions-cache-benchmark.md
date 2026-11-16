# GitHub Actions キャッシュ有無による Web テスト実行時間の比較

Web アプリのテストを GitHub Actions で回すとき、キャッシュをフル活用した場合と使わない場合で実行時間がどれだけ変わるかを実測する仕組み。
結果は HTML レポートとして Actions Artifact に保存する。

## 構成

| パス | 役割 |
|---|---|
| `bench/web-app/` | 計測対象の Web アプリ（React + Vite、ESLint / TypeScript / Vitest / Playwright） |
| `.github/workflows/cache-benchmark.yml` | 手動実行の入口。prime → measure → report → cleanup |
| `.github/workflows/cache-benchmark-run.yml` | 1 回分の計測（reusable workflow） |
| `scripts/bench/make_report.py` | GitHub API の job / step 時刻から HTML を生成（標準ライブラリのみ） |

## 比較する構成

| variant | キャッシュ |
|---|---|
| `none` | なし（`setup-node` の自動キャッシュも `package-manager-cache: false` で無効化） |
| `setup-node` | `setup-node` の `cache: npm`（`~/.npm` のみ） |
| `full` | `node_modules`（ESLint・tsc・Vitest のキャッシュ込み）、`~/.npm`、Playwright ブラウザ |

## 実行方法

```bash
gh workflow run cache-benchmark.yml --ref main -f iterations=3
gh run watch "$(gh run list --workflow cache-benchmark.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

実行が終わると、run のページの Artifacts に `cache-benchmark-report.html` ができる（zip ではなく HTML 単体。閲覧には GitHub へのログインが必要、保持 90 日）。
Job Summary にも結果の表とレポートへのリンクが出る。

## 計測の設計

- `prime`（cold）: `setup-node` と `full` をキャッシュなしの状態で 1 回ずつ実行し、キャッシュを作る
- `measure`（warm）: 3 variant × `iterations` 回を並列に実行する
- `full` のキャッシュキーには `run_id` と `run_attempt` を含め、run ごとに独立させる。`cleanup` が run の終わりに削除する
- 時間は GitHub API（`/actions/runs/{id}/attempts/{n}/jobs`）の step 開始・終了時刻から求める（秒単位）

## セキュリティ

- 使うトークンは `GITHUB_TOKEN` のみ。job ごとに `permissions` を最小化（report は `actions: read`、cleanup は `actions: write`）
- `actions/checkout` は `persist-credentials: false`
- Action は commit SHA で固定
- step output は `env` 経由で shell に渡し、`${{ }}` を直接スクリプトへ埋め込まない
- レポートに含めるのは時間、キャッシュの hit/miss、job ログへのリンクだけ
