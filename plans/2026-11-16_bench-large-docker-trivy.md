# キャッシュベンチマーク拡張: 大規模アプリ・Docker ビルド・Trivy スキャン

- 作成日: 2026-11-16
- 作成者モデル: Claude Opus 5.5 (claude-opus-5-5)
- 前提: `plans/2026-11-16_actions-cache-benchmark.md`（小規模アプリでは差がばらつきに埋もれた）

## 目的

キャッシュ対象ごとに「キャッシュあり／なし」の時間を計測し、どのキャッシュがどれだけ効くかを示す。
アプリ規模（小・大）による違いも比較する。

## 計測するキャッシュ

| キャッシュ | なし | あり |
|---|---|---|
| npm 依存 | `npm ci`（`package-manager-cache: false`） | `node_modules` を `actions/cache` で復元し `npm ci` を省略 |
| ESLint / tsc / Vitest | 毎回フル | `node_modules/.cache`・`.vite` に同梱して復元。ESLint は `--cache-strategy content`（checkout で mtime が変わるため） |
| Playwright ブラウザ | `playwright install --with-deps` | `~/.cache/ms-playwright` を復元し `install-deps` のみ |
| Docker ビルド | BuildKit キャッシュなし | `cache-from`/`cache-to: type=gha,mode=max`（scope は run ごと） |
| Trivy 脆弱性 DB | 毎回ダウンロード | `.cache/trivy` を `actions/cache` で復元（trivy-action 内蔵キャッシュは日付キーで run 間共有されるため `cache: false` にし、同じ仕組みを run スコープで自前実装） |

variant は従来どおり `none` / `setup-node` / `full`。キャッシュ別の効果は `none` と `full` の工程別時間（復元・保存時間を含めて）で比較する。

## 大規模アプリ（`bench/web-app-large/`）

- 実在ライブラリで依存を増やす（MUI、icons、emotion、react-router、TanStack Query、zod、date-fns、lodash-es、axios、react-hook-form、recharts、i18next、motion、Storybook、msw、prettier、coverage-v8 など）
- ソースは `scripts/generate.mjs` で CI 上に生成（feature × 300: schema / logic / test / MUI コンポーネント）。生成物はコミットしない
- warm 計測では 1 ファイルだけ変更してから実行（変更なしはキャッシュに有利すぎるため、実運用の差分 CI に寄せる）
- lockfile は Linux（node:24 コンテナ）で生成

## Docker / Trivy

- 各アプリに multi-stage Dockerfile（node:24-slim で build → nginx alpine で配信）
- `docker/setup-buildx-action` + `docker/build-push-action`（`load: true`）
- `aquasecurity/trivy-action` でイメージをスキャン（`scanners: vuln`、`exit-code: 0`。時間計測が目的で脆弱性で落とさない）
- cleanup で run の prefix に加え BuildKit の gha キャッシュ（scope に run 情報を含める）も削除

## ワークフロー

- matrix: app [small, large] × variant × iterations。prime は app × [setup-node, full]
- job 名: `<app>-<variant>-<phase>-<iteration>`
- timeout 30 分

## レポート

- アプリ規模ごとのカード・積み上げグラフ
- 「キャッシュ別の効果」表: キャッシュ対象ごとに なし / あり（復元・保存込み）/ 差
- 工程に Docker ビルド・Trivy スキャン・ソース生成を追加

## リスクと対策

- Trivy DB ダウンロードのレート制限で none が失敗 → 失敗 job は集計から除外し、表に結果を出す。頻発するなら並列度を下げる
- BuildKit の blob キャッシュは内容ハッシュのキーで run 間共有されうる → scope を run ごとにし、cleanup で削除。実際のキー形式は初回 run で確認して反映
- キャッシュ容量（大規模 node_modules + BuildKit）→ 10 GB 内、run 終了時に削除

## 完了条件

- 全 job 成功、HTML artifact 生成、表示確認、About 更新、個人ID・クレデンシャル 0 件
