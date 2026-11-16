#!/usr/bin/env python3
"""cache-benchmark.yml の結果から HTML レポートを作る（標準ライブラリのみ）。

入力:
  --jobs  GitHub API の jobs を 1 行 1 JSON にしたファイル
  --meta  各計測 job が出力したメタ情報 JSON のディレクトリ
出力:
  --out      単一 HTML（外部リソースなし）
  --summary  GITHUB_STEP_SUMMARY 用 Markdown

トークンなどの秘密情報は入力にも出力にも含めない。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path

VARIANTS = ["none", "setup-node", "full"]
VARIANT_LABEL = {
    "none": "キャッシュなし",
    "setup-node": "setup-node の cache: npm だけ",
    "full": "フル活用",
}
VARIANT_DESC = {
    "none": "毎回まっさらな状態から npm パッケージとブラウザをダウンロードする。setup-node の自動キャッシュも明示的に無効化。",
    "setup-node": "よく見かける最小構成。npm のダウンロードキャッシュ（~/.npm）だけを復元し、npm ci 自体は毎回実行する。",
    "full": "node_modules を丸ごと復元して npm ci を省略。Playwright のブラウザ本体、ESLint・TypeScript・Vitest のキャッシュも復元する。",
}

# (key, 表示名, 色) — 色は明暗どちらでも判別できるよう彩度・明度を揃えたもの
PHASES = [
    ("prepare", "準備（job 起動・checkout・Node）", "#8c96a8"),
    ("restore", "キャッシュ復元", "#2f9e8f"),
    ("deps", "依存インストール", "#d9822b"),
    ("browsers", "ブラウザ準備", "#c4504a"),
    ("lint", "Lint", "#6a5acd"),
    ("typecheck", "型チェック", "#3d7dd8"),
    ("unit", "Unit test", "#4caf50"),
    ("build", "Build", "#b8860b"),
    ("e2e", "E2E", "#c2185b"),
    ("save", "キャッシュ保存", "#00838f"),
    ("other", "その他", "#b0b0b0"),
]
PHASE_LABEL = {k: label for k, label, _ in PHASES}


def phase_of(step: str) -> str:
    if step.startswith(("Post Restore cache", "Post Setup Node")):
        return "save"
    if step.startswith("Restore cache"):
        return "restore"
    if (
        step in ("Set up job", "Checkout")
        or step.startswith("Setup Node")
        or step == "Resolve Playwright version"
    ):
        return "prepare"
    return {
        "Install dependencies": "deps",
        "Install Playwright browsers": "browsers",
        "Lint": "lint",
        "Typecheck": "typecheck",
        "Unit test": "unit",
        "Build": "build",
        "E2E": "e2e",
    }.get(step, "other")


def ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def secs(a: str | None, b: str | None) -> float | None:
    x, y = ts(a), ts(b)
    return (y - x).total_seconds() if x and y else None


def median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def fmt(s: float | None) -> str:
    if s is None:
        return "—"
    s = round(s)
    return f"{s // 60}分{s % 60:02d}秒" if s >= 60 else f"{s}秒"


def load(jobs_path: Path, meta_dir: Path) -> list[dict]:
    metas = {}
    for p in sorted(meta_dir.glob("*.json")) if meta_dir.exists() else []:
        m = json.loads(p.read_text())
        metas[m["job"]] = m
    rows = []
    for line in jobs_path.read_text().splitlines():
        if not line.strip():
            continue
        j = json.loads(line)
        key = j["name"].split(" / ")[-1]
        m = metas.get(key)
        if not m:
            continue  # report / cleanup などの集計対象外 job
        phases = {k: 0.0 for k, _, _ in PHASES}
        for st in j.get("steps", []):
            d = secs(st.get("started_at"), st.get("completed_at"))
            if d is not None and st.get("conclusion") != "skipped":
                phases[phase_of(st["name"])] += d
        rows.append(
            {
                **m,
                "conclusion": j.get("conclusion"),
                "url": j.get("html_url", ""),
                "total": secs(j.get("started_at"), j.get("completed_at")),
                "phases": phases,
            }
        )
    rows.sort(
        key=lambda r: (
            VARIANTS.index(r["variant"]),
            r["phase"] != "cold",
            r["iteration"],
        )
    )
    return rows


def aggregate(rows: list[dict]) -> dict:
    agg = {}
    for v in VARIANTS:
        for ph in ("cold", "warm"):
            rs = [
                r
                for r in rows
                if r["variant"] == v
                and r["phase"] == ph
                and r["conclusion"] == "success"
            ]
            if not rs:
                continue
            agg[(v, ph)] = {
                "n": len(rs),
                "total": median([r["total"] for r in rs if r["total"] is not None]),
                "min": min(r["total"] for r in rs),
                "max": max(r["total"] for r in rs),
                "phases": {
                    k: median([r["phases"][k] for r in rs]) or 0.0 for k, _, _ in PHASES
                },
            }
    return agg


def bar_chart(agg: dict) -> str:
    """工程別の積み上げ横棒グラフ（SVG）。"""
    bars = []
    for v in VARIANTS:
        for ph in ("warm", "cold"):
            if (v, ph) in agg:
                label = VARIANT_LABEL[v] + ("（初回）" if ph == "cold" else "")
                bars.append((label, agg[(v, ph)], ph))
    if not bars:
        return "<p>計測データがありません。</p>"
    max_total = max(sum(a["phases"].values()) for _, a, _ in bars)
    left, width, bar_h, gap = 280, 540, 26, 18
    height = len(bars) * (bar_h + gap) + 30
    scale = width / max_total if max_total else 0
    out = [
        f'<svg viewBox="0 0 {left + width + 90} {height}" role="img" aria-labelledby="chart-title" class="chart">',
        '<title id="chart-title">variant ごとの工程別実行時間（中央値、秒）</title>',
    ]
    # 目盛り
    step = 30 if max_total > 120 else 10
    t = 0
    while t <= max_total:
        x = left + t * scale
        out.append(
            f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height - 22}" class="grid"/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{height - 6}" class="tick" text-anchor="middle">{t}s</text>'
        )
        t += step
    for i, (label, a, ph) in enumerate(bars):
        y = i * (bar_h + gap) + 6
        out.append(
            f'<text x="{left - 10}" y="{y + bar_h / 2 + 5}" text-anchor="end" class="{"lbl cold" if ph == "cold" else "lbl"}">{html.escape(label)}</text>'
        )
        x = left
        for k, name, color in PHASES:
            w = a["phases"][k] * scale
            if w <= 0:
                continue
            out.append(
                f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{color}"'
                f"{' opacity="0.55"' if ph == 'cold' else ''}><title>{html.escape(name)}: {a['phases'][k]:.0f}秒</title></rect>"
            )
            x += w
        out.append(
            f'<text x="{x + 6:.1f}" y="{y + bar_h / 2 + 5}" class="val">{fmt(sum(a["phases"].values()))}</text>'
        )
    out.append("</svg>")
    legend = "".join(
        f'<li><span class="sw" style="background:{c}"></span>{html.escape(n)}</li>'
        for _, n, c in PHASES
    )
    return "\n".join(out) + f'<ul class="legend">{legend}</ul>'


def hit_badge(v: str) -> str:
    if v == "true":
        return '<span class="badge hit">hit</span>'
    if v == "false":
        return '<span class="badge miss">miss</span>'
    return '<span class="badge na">—</span>'


def render(rows: list[dict], agg: dict, ctx: dict) -> str:
    none_w = agg.get(("none", "warm"), {}).get("total")
    cards = []
    for v in VARIANTS:
        a = agg.get((v, "warm"))
        if not a:
            continue
        diff = ""
        if none_w and v != "none":
            pct = (none_w - a["total"]) / none_w * 100
            diff = f'<p class="delta">キャッシュなしより <strong>{fmt(none_w - a["total"])}</strong> 短い（{pct:.0f}% 削減）</p>'
        cards.append(
            f'<div class="card v-{v}"><h3>{html.escape(VARIANT_LABEL[v])}</h3>'
            f'<p class="big">{fmt(a["total"])}</p>'
            f'<p class="sub">中央値（{a["n"]} 回、{fmt(a["min"])}〜{fmt(a["max"])}）</p>{diff}</div>'
        )

    phase_rows = []
    for k, name, color in PHASES:
        cells = []
        for v in VARIANTS:
            a = agg.get((v, "warm"))
            cells.append(f'<td class="num">{fmt(a["phases"][k]) if a else "—"}</td>')
        phase_rows.append(
            f'<tr><th scope="row"><span class="sw" style="background:{color}"></span>{html.escape(name)}</th>{"".join(cells)}</tr>'
        )

    job_rows = []
    for r in rows:
        h = r["cache_hit"]
        job_rows.append(
            "<tr>"
            f"<td>{html.escape(VARIANT_LABEL[r['variant']])}</td>"
            f"<td>{'初回（cold）' if r['phase'] == 'cold' else f'計測 {r["iteration"]}（warm）'}</td>"
            f'<td class="num">{fmt(r["total"])}</td>'
            f'<td class="num">{fmt(r["phases"]["deps"])}</td>'
            f'<td class="num">{fmt(r["phases"]["browsers"])}</td>'
            f"<td>{hit_badge(h.get('setup_node_npm', ''))}</td>"
            f"<td>{hit_badge(h.get('node_modules', ''))}</td>"
            f"<td>{hit_badge(h.get('npm', ''))}</td>"
            f"<td>{hit_badge(h.get('playwright', ''))}</td>"
            f"<td>{html.escape(r['conclusion'] or '')}</td>"
            f'<td><a href="{html.escape(r["url"])}">ログ</a></td>'
            "</tr>"
        )

    first = rows[0] if rows else {}
    variant_desc = "".join(
        f"<dt>{html.escape(VARIANT_LABEL[v])}（<code>{v}</code>）</dt><dd>{html.escape(VARIANT_DESC[v])}</dd>"
        for v in VARIANTS
    )
    run_url = f"{ctx['server']}/{ctx['repo']}/actions/runs/{ctx['run_id']}"
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>GitHub Actions キャッシュ有無による Web テスト実行時間の比較</title>
<style>
:root {{ color-scheme: light dark; --bg:#fbfbfd; --fg:#1d1f24; --muted:#5b6170; --card:#fff; --line:#dfe2e8; --accent:#2f6fde; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14161a; --fg:#e8eaef; --muted:#a3a9b6; --card:#1d2026; --line:#323642; --accent:#7aa7ff; }} }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font: 16px/1.75 system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif; }}
main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 80px; }}
h1 {{ font-size: 1.7rem; line-height:1.4; margin: 0 0 .3em; }}
h2 {{ font-size: 1.25rem; margin: 2.4em 0 .6em; padding-bottom:.3em; border-bottom: 1px solid var(--line); }}
.meta {{ color: var(--muted); font-size: .9rem; }}
.cards {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); gap: 14px; margin-top: 1em; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius: 12px; padding: 16px 18px; border-top: 5px solid var(--muted); }}
.card.v-full {{ border-top-color: #2f9e8f; }} .card.v-setup-node {{ border-top-color: #3d7dd8; }} .card.v-none {{ border-top-color: #c4504a; }}
.card h3 {{ margin:0; font-size: 1rem; }}
.big {{ font-size: 2.2rem; font-weight: 700; margin: .1em 0 0; font-variant-numeric: tabular-nums; }}
.sub, .delta {{ margin: 0; font-size: .88rem; color: var(--muted); }}
.delta strong {{ color: var(--fg); }}
.chart {{ width: 100%; height: auto; background: var(--card); border:1px solid var(--line); border-radius: 12px; padding: 10px; }}
.chart .grid {{ stroke: var(--line); }} .chart .tick, .chart .val {{ fill: var(--muted); font-size: 12px; }}
.chart .lbl {{ fill: var(--fg); font-size: 13px; }} .chart .lbl.cold {{ fill: var(--muted); }}
.legend {{ list-style:none; padding:0; display:flex; flex-wrap:wrap; gap: 6px 16px; font-size: .85rem; color: var(--muted); }}
.sw {{ display:inline-block; width: .9em; height: .9em; border-radius: 3px; margin-right: .4em; vertical-align: -1px; }}
.table-wrap {{ overflow-x:auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; background: var(--card); }}
th, td {{ border-bottom: 1px solid var(--line); padding: 6px 10px; text-align: left; white-space: nowrap; }}
thead th {{ font-weight: 600; color: var(--muted); }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.badge {{ font-size:.75rem; padding: 1px 8px; border-radius: 999px; }}
.badge.hit {{ background:#d4f4e4; color:#0d5c36; }} .badge.miss {{ background:#fde2d8; color:#8a2b0b; }} .badge.na {{ color: var(--muted); }}
dt {{ font-weight: 600; margin-top: .6em; }} dd {{ margin: 0 0 0 1em; }}
.note {{ background: var(--card); border-left: 4px solid var(--accent); padding: 10px 16px; border-radius: 6px; }}
a {{ color: var(--accent); }}
code {{ font-size: .9em; }}
@media print {{ .chart {{ border: none; }} }}
</style>
</head>
<body>
<main>
<h1>GitHub Actions のキャッシュで Web テストはどれだけ速くなるか</h1>
<p class="meta">計測日時 {html.escape(ctx["generated"])} ／ Node {html.escape(first.get("node_version", ""))} ／ Playwright {html.escape(first.get("playwright_version", ""))} ／ ランナー {html.escape(first.get("image", ""))} ／ 各構成 {html.escape(ctx["iterations"])} 回計測 ／ <a href="{html.escape(run_url)}">ワークフロー実行</a></p>

<section aria-labelledby="h-result">
<h2 id="h-result">結果（キャッシュが温まった状態の job 全体時間）</h2>
<div class="cards">{"".join(cards)}</div>
</section>

<section aria-labelledby="h-chart">
<h2 id="h-chart">どの工程に時間がかかっているか</h2>
<p>棒は工程ごとの所要時間（中央値）を積み上げたもの。「（初回）」の薄い棒は、キャッシュがまだ無い状態でキャッシュを作る側の実行です。</p>
{bar_chart(agg)}
</section>

<section aria-labelledby="h-phase">
<h2 id="h-phase">工程別の所要時間（warm・中央値）</h2>
<div class="table-wrap"><table>
<thead><tr><th scope="col">工程</th>{"".join(f'<th scope="col" class="num">{html.escape(VARIANT_LABEL[v])}</th>' for v in VARIANTS)}</tr></thead>
<tbody>{"".join(phase_rows)}</tbody>
</table></div>
</section>

<section aria-labelledby="h-variant">
<h2 id="h-variant">比較した 3 つの構成</h2>
<dl>{variant_desc}</dl>
<p>どの構成も同じ Web アプリ（React + Vite）に対して、Lint（ESLint）→ 型チェック（TypeScript）→ Unit test（Vitest）→ Build（Vite）→ E2E（Playwright / Chromium）を実行しています。</p>
</section>

<section aria-labelledby="h-jobs">
<h2 id="h-jobs">すべての実行</h2>
<div class="table-wrap"><table>
<thead><tr><th scope="col">構成</th><th scope="col">回</th><th scope="col" class="num">合計</th><th scope="col" class="num">依存</th><th scope="col" class="num">ブラウザ</th><th scope="col">setup-node npm</th><th scope="col">node_modules</th><th scope="col">~/.npm</th><th scope="col">Playwright</th><th scope="col">結果</th><th scope="col">ログ</th></tr></thead>
<tbody>{"".join(job_rows)}</tbody>
</table></div>
</section>

<section aria-labelledby="h-read">
<h2 id="h-read">読み方と注意点</h2>
<ul>
<li>時間は GitHub API が返す job・step の開始／終了時刻（秒単位）から計算しています。ランナーの個体差で数秒〜十数秒ぶれるため、複数回の中央値で比べています。</li>
<li>「フル活用」のキャッシュキーにはワークフロー実行 ID を含め、毎回作り直しています。前回の実行の残りに結果が左右されないようにするためです。実行後、この実行で作ったキャッシュは削除しています。</li>
<li>「setup-node の cache: npm だけ」のキャッシュは lockfile のハッシュがキーなので、過去の実行で作られたものが使われることがあります（実運用と同じ挙動）。</li>
<li>Playwright 公式は「ブラウザ本体のキャッシュは推奨しない（復元時間がダウンロードと同程度で、Linux の OS 依存パッケージはキャッシュできない）」としています。この計測でも、ブラウザ準備の差は依存インストールの差より小さいかを確認できます。</li>
<li>actions/setup-node は v5 から、package.json に <code>packageManager</code> があると自動でキャッシュを有効にします。「キャッシュなし」では <code>package-manager-cache: false</code> で明示的に切っています。</li>
</ul>
<div class="note">
<p><strong>2026 年 11 月時点の Actions キャッシュの仕様（公式ドキュメントより）</strong></p>
<ul>
<li>リポジトリあたり既定 10 GB。超えた分は課金で拡張できる。7 日間使われなかったエントリは削除される。</li>
<li>復元できるのは自ブランチと default branch（PR なら base branch）のキャッシュ。兄弟ブランチのキャッシュは使えない。</li>
<li>保存は 1 分あたり 200 件、復元は 1500 件まで。</li>
<li>使用した Action: actions/cache v6.1.0、actions/setup-node v7.1.0、actions/checkout v7.0.1、actions/upload-artifact v7.0.2（いずれも commit SHA で固定）。</li>
</ul>
</div>
<p>出典: <a href="https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching">GitHub Docs: Dependency caching reference</a> ／ <a href="https://github.com/actions/setup-node/releases/tag/v5.0.0">actions/setup-node v5.0.0</a> ／ <a href="https://playwright.dev/docs/ci">Playwright: Continuous Integration</a></p>
</section>
</main>
</body>
</html>
"""


def summary_md(agg: dict, ctx: dict) -> str:
    lines = [
        "## Cache Benchmark",
        "",
        "| 構成 | warm 中央値 | cold |",
        "|---|---:|---:|",
    ]
    for v in VARIANTS:
        w, c = agg.get((v, "warm")), agg.get((v, "cold"))
        lines.append(
            f"| {VARIANT_LABEL[v]} | {fmt(w['total'] if w else None)} | {fmt(c['total'] if c else None)} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=Path, required=True)
    ap.add_argument("--meta", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--summary", type=Path, required=True)
    a = ap.parse_args()
    rows = load(a.jobs, a.meta)
    agg = aggregate(rows)
    ctx = {
        "repo": os.environ.get("REPO", ""),
        "run_id": os.environ.get("RUN_ID", ""),
        "server": os.environ.get("SERVER_URL", "https://github.com"),
        "iterations": os.environ.get("ITERATIONS", "?"),
        "generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    }
    a.out.write_text(render(rows, agg, ctx), encoding="utf-8")
    a.summary.write_text(summary_md(agg, ctx), encoding="utf-8")
    print(f"jobs={len(rows)} variants={sorted({r['variant'] for r in rows})}")


if __name__ == "__main__":
    main()
