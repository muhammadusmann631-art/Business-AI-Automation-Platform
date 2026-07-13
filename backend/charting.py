"""Level 1 — chart/graph tool (matplotlib, headless Agg backend).

Deterministic: takes labels + numeric values and writes a real .png under
backend/charts/. Honours a user colour preference (e.g. "graphs blue").
"""

import re
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display / GUI — safe on a server
import matplotlib.pyplot as plt  # noqa: E402

CHARTS_DIR = Path(__file__).parent / "charts"

# Friendly colour names -> hex, so "graphs blue rakhna" just works.
_NAMED_COLORS = {
    "blue": "#3b82f6", "green": "#43e0a3", "red": "#ef4444", "orange": "#f97316",
    "purple": "#8b5cf6", "teal": "#14b8a6", "amber": "#f5b301", "pink": "#ec4899",
    "gray": "#6b7280", "grey": "#6b7280", "black": "#111827",
}


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "chart"


def _resolve_color(color: str) -> str:
    c = (color or "").strip().lower()
    if c in _NAMED_COLORS:
        return _NAMED_COLORS[c]
    if re.match(r"^#[0-9a-f]{6}$", c):
        return c
    return "#43e0a3"


def make_chart(
    title: str,
    labels: list,
    values: list[float],
    chart_type: str = "bar",
    color: str = "#43e0a3",
) -> dict:
    """Render a bar/line chart to a .png and return {path, filename}."""
    CHARTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{_slug(title)}-{timestamp}.png"
    path = CHARTS_DIR / filename
    hexcolor = _resolve_color(color)

    labels = [str(x) for x in labels]
    values = [float(v or 0) for v in values]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")
    if chart_type.lower() == "line":
        ax.plot(labels, values, marker="o", color=hexcolor, linewidth=2.2)
        ax.fill_between(range(len(values)), values, alpha=0.08, color=hexcolor)
    else:
        ax.bar(labels, values, color=hexcolor, edgecolor="none")

    ax.set_title(title, fontsize=13, fontweight="bold", color="#111827")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors="#374151", labelsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    if len(labels) > 6:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return {"path": str(path), "filename": filename}


if __name__ == "__main__":
    out = make_chart(
        "Last 3 Months Sales",
        ["April", "May", "June"],
        [21000, 26300, 45000],
        "bar",
        "blue",
    )
    print("wrote:", out)
