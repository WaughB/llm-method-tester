"""Generate the README strategy-comparison charts (SVG, light + dark).

Data is measured from the committed reference run (results/reference-run.json
aggregates; see README results table). Cost is estimated from measured tokens
at $0.20 / M prompt and $0.60 / M completion tokens (typical hosted 8B-class
pricing) — the token counts are the measured fact, the dollars are the
labeled assumption.

Run:  uv run python docs/charts/generate_charts.py
"""

from pathlib import Path

OUT = Path(__file__).parent

# (strategy, judge score avg/5, latency s, prompt tok, completion tok)
DATA = [
    ("Baseline (control)", 0.23, 30.1, 76, 511),
    ("Vector RAG", 4.58, 2.2, 562, 76),
    ("Obsidian RAG", 4.56, 2.8, 1026, 87),
    ("PageIndex (reimpl)", 4.74, 16.4, 4623, 632),
    ("PageIndex (official)", 4.33, 15.5, 11040, 388),
]

PROMPT_PRICE_PER_M = 0.20
COMPLETION_PRICE_PER_M = 0.60


def cost_per_10k(prompt_tokens: int, completion_tokens: int) -> float:
    per_query = (
        prompt_tokens * PROMPT_PRICE_PER_M + completion_tokens * COMPLETION_PRICE_PER_M
    ) / 1_000_000
    return per_query * 10_000


THEMES = {
    "light": {
        "ink": "#0b0b0b",
        "sub": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "bar": "#2a78d6",
        "control": "#b5b3ac",
    },
    "dark": {
        "ink": "#ffffff",
        "sub": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "bar": "#3987e5",
        "control": "#5a5952",
    },
}

WIDTH = 760
LABEL_W = 170
BAR_MAX_W = 470
ROW_H = 40
BAR_H = 18
TOP = 54
FONT = "-apple-system, 'Segoe UI', Roboto, sans-serif"


def bar_chart(
    theme_name: str,
    title: str,
    unit: str,
    values: list[float],
    fmt,
    note: str = "",
) -> str:
    theme = THEMES[theme_name]
    max_value = max(values)
    height = TOP + ROW_H * len(DATA) + (26 if note else 12)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{title}">',
        f'<text x="0" y="18" font-family="{FONT}" font-size="15" font-weight="600" '
        f'fill="{theme["ink"]}">{title}</text>',
        f'<text x="0" y="36" font-family="{FONT}" font-size="12" '
        f'fill="{theme["sub"]}">{unit}</text>',
    ]
    for i, ((name, *_), value) in enumerate(zip(DATA, values, strict=True)):
        y = TOP + i * ROW_H
        bar_y = y + (ROW_H - BAR_H) / 2 - 4
        width = max(3.0, value / max_value * BAR_MAX_W)
        is_control = i == 0
        fill = theme["control"] if is_control else theme["bar"]
        parts.append(
            f'<text x="{LABEL_W - 10}" y="{bar_y + BAR_H - 4}" text-anchor="end" '
            f'font-family="{FONT}" font-size="13" fill="{theme["sub"]}">{name}</text>'
        )
        parts.append(
            f'<rect x="{LABEL_W}" y="{bar_y}" width="{width:.1f}" height="{BAR_H}" '
            f'rx="3" fill="{fill}"/>'
        )
        label = fmt(value)
        parts.append(
            f'<text x="{LABEL_W + width + 8:.1f}" y="{bar_y + BAR_H - 4}" '
            f'font-family="{FONT}" font-size="13" font-weight="600" '
            f'fill="{theme["ink"]}">{label}</text>'
        )
    if note:
        parts.append(
            f'<text x="0" y="{height - 8}" font-family="{FONT}" font-size="11" '
            f'fill="{theme["muted"]}">{note}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def write_pair(stem: str, title: str, unit: str, values: list[float], fmt, note: str = ""):
    for theme_name in THEMES:
        svg = bar_chart(theme_name, title, unit, values, fmt, note)
        (OUT / f"{stem}-{theme_name}.svg").write_text(svg, encoding="utf-8", newline="\n")
    print(f"wrote {stem}-light.svg / {stem}-dark.svg")


def main() -> None:
    write_pair(
        "judge-score",
        "Answer quality — blind LLM judge",
        "Mean judge score across all three models (0–5). Gray = no-retrieval control.",
        [row[1] for row in DATA],
        lambda v: f"{v:.2f}",
        note=(
            "Fictional corpus: the control proves retrieval, not memorization, "
            "drives every score above it."
        ),
    )
    write_pair(
        "latency",
        "Latency per question",
        (
            "Mean seconds per question across all three models "
            "(RTX 3080, includes all retrieval + generation calls)."
        ),
        [row[2] for row in DATA],
        lambda v: f"{v:.1f}s",
        note=(
            "Baseline is slow because ungrounded models generate the most tokens "
            "when they know the least."
        ),
    )
    write_pair(
        "cost",
        "Estimated cost per 10,000 queries",
        (
            "From measured tokens/query, at $0.20 / M prompt + $0.60 / M completion "
            "(typical hosted 8B pricing)."
        ),
        [cost_per_10k(row[3], row[4]) for row in DATA],
        lambda v: f"${v:.2f}",
        note=(
            "Token counts are measured; prices are the labeled assumption. "
            "Self-hosted, the same ratios apply as GPU time."
        ),
    )


if __name__ == "__main__":
    main()
