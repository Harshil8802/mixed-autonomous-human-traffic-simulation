"""Generate report-ready SVG evidence for the final shock-recovery study.

The plotting code intentionally uses only the Python standard library. This
keeps the complete experiment and figure workflow runnable in a clean Python
3 installation while still producing vector graphics for the report.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Iterable

from traffic_sim import BrakingDisturbance, SimulationConfig, run_simulation


DEFAULT_SUMMARY = Path("results/shock-recovery-summary.csv")
DEFAULT_OUTPUT_DIR = Path("results/figures")
COLORS = {
    (1, "reactive"): "#2563eb",
    (1, "anticipatory"): "#7c3aed",
    (2, "reactive"): "#059669",
    (2, "anticipatory"): "#dc2626",
}


class Svg:
    """Small helper for deterministic, dependency-free SVG figures."""

    def __init__(self, width: int, height: int, title: str):
        self.width = width
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">',
            f"<title>{escape(title)}</title>",
            '<rect width="100%" height="100%" fill="white"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#172033}'
            '.axis{stroke:#334155;stroke-width:1}.grid{stroke:#e2e8f0;stroke-width:1}'
            '.label{font-size:12px}.small{font-size:10px}.title{font-size:18px;font-weight:700}'
            '.panel{font-size:14px;font-weight:700}</style>',
        ]

    def add(self, value: str) -> None:
        self.parts.append(value)

    def text(self, x: float, y: float, value: str, css: str = "label", **attrs) -> None:
        extra = " ".join(f'{name.replace("_", "-")}="{escape(str(val))}"' for name, val in attrs.items())
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="{css}" {extra}>{escape(value)}</text>')

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join([*self.parts, "</svg>\n"]), encoding="utf-8")


def _number(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "").strip()
    return None if value in ("", "None", "N/A") else float(value)


def read_summary(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist; run python -m experiments.shock_recovery first"
        )
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "lanes",
        "density",
        "requested_av_share",
        "av_policy",
        "maximum_stopped_fraction_after_braking_mean",
        "recovery_time_steps_mean",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError("shock-recovery summary is empty or missing required columns")
    return rows


def _axes(svg: Svg, x: int, y: int, width: int, height: int, *, x_label: str, y_label: str) -> None:
    svg.add(f'<line class="axis" x1="{x}" y1="{y + height}" x2="{x + width}" y2="{y + height}"/>')
    svg.add(f'<line class="axis" x1="{x}" y1="{y}" x2="{x}" y2="{y + height}"/>')
    svg.text(x + width / 2, y + height + 38, x_label, text_anchor="middle")
    svg.text(x - 42, y + height / 2, y_label, text_anchor="middle", transform=f"rotate(-90 {x - 42} {y + height / 2})")


def create_summary_figure(rows: Iterable[dict[str, str]], output: Path, *, density: float = 0.30) -> None:
    """Plot disruption severity and recovery time across the final conditions."""
    selected = [row for row in rows if abs(float(row["density"]) - density) < 1e-9]
    if not selected:
        raise ValueError(f"no rows found for density {density}")

    panels = [
        ("maximum_stopped_fraction_after_braking_mean", "Maximum stopped fraction", True),
        ("recovery_time_steps_mean", "Recovery time (steps)", False),
    ]
    svg = Svg(1120, 530, "Shock-recovery comparison")
    svg.text(560, 32, f"Shock response at occupancy density {density:.2f}", "title", text_anchor="middle")
    legend_y = 58
    for index, ((lanes, policy), color) in enumerate(COLORS.items()):
        lx = 215 + index * 190
        svg.add(f'<line x1="{lx}" y1="{legend_y}" x2="{lx + 24}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
        svg.text(lx + 30, legend_y + 4, f"{lanes} lane, {policy}", "small")

    for panel_index, (metric, label, fraction) in enumerate(panels):
        x0 = 85 + panel_index * 550
        y0, width, height = 95, 450, 350
        values = [_number(row, metric) for row in selected]
        numeric = [value for value in values if value is not None]
        ymax = 1.0 if fraction else max(10.0, max(numeric, default=1.0) * 1.12)
        _axes(svg, x0, y0, width, height, x_label="AV share", y_label=label)
        svg.text(x0, y0 - 14, label, "panel")

        for tick in range(6):
            value = ymax * tick / 5
            py = y0 + height - height * tick / 5
            svg.add(f'<line class="grid" x1="{x0}" y1="{py:.1f}" x2="{x0 + width}" y2="{py:.1f}"/>')
            text = f"{value:.0%}" if fraction else f"{value:.0f}"
            svg.text(x0 - 8, py + 4, text, "small", text_anchor="end")
        for tick in range(5):
            share = tick / 4
            px = x0 + width * share
            svg.text(px, y0 + height + 18, f"{share:.0%}", "small", text_anchor="middle")

        grouped: dict[tuple[int, str], list[tuple[float, float]]] = defaultdict(list)
        for row in selected:
            value = _number(row, metric)
            if value is not None:
                grouped[(int(row["lanes"]), row["av_policy"])].append(
                    (float(row["requested_av_share"]), value)
                )
        for key, points in grouped.items():
            points.sort()
            color = COLORS[key]
            mapped = [
                (x0 + width * share, y0 + height - height * value / ymax)
                for share, value in points
            ]
            svg.add('<polyline fill="none" stroke="{}" stroke-width="2.5" points="{}"/>'.format(
                color, " ".join(f"{x:.1f},{y:.1f}" for x, y in mapped)
            ))
            source_points = sorted(
                (
                    float(row["requested_av_share"]),
                    row,
                )
                for row in selected
                if (int(row["lanes"]), row["av_policy"]) == key
                and _number(row, metric) is not None
            )
            interval_keys = {
                "maximum_stopped_fraction_after_braking_mean": (
                    "maximum_stopped_fraction_after_braking_ci95_low",
                    "maximum_stopped_fraction_after_braking_ci95_high",
                ),
                "recovery_time_steps_mean": (
                    "recovery_time_steps_ci95_low",
                    "recovery_time_steps_ci95_high",
                ),
            }.get(metric)
            for (px, py), (_, source_row) in zip(mapped, source_points):
                if interval_keys:
                    low = _number(source_row, interval_keys[0])
                    high = _number(source_row, interval_keys[1])
                    if low is not None and high is not None:
                        low_y = y0 + height - height * low / ymax
                        high_y = y0 + height - height * high / ymax
                        svg.add(
                            f'<line x1="{px:.1f}" y1="{high_y:.1f}" '
                            f'x2="{px:.1f}" y2="{low_y:.1f}" '
                            f'stroke="{color}" stroke-width="1.2"/>'
                        )
                svg.add(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{color}"/>')
    svg.save(output)


def _representative_run(lanes: int, policy: str, *, seed: int, steps: int) -> dict:
    road_length = 200
    density = 0.30
    config = SimulationConfig(
        road_length=road_length,
        num_vehicles=round(road_length * lanes * density),
        max_speed=5,
        human_slow_probability=0.2,
        av_share=0.5,
        av_policy=policy,
        lanes=lanes,
        seed=seed,
    )
    disturbance = BrakingDisturbance(vehicle_id=0, start_step=60, duration=8, speed_cap=0)
    return run_simulation(
        config,
        warmup=200,
        steps=steps,
        disturbance=disturbance,
        record_trajectories=True,
    )


def create_recovery_curves(output: Path, *, seed: int = 1, steps: int = 180) -> None:
    """Plot representative network speed for each lane/controller combination."""
    runs = {(lanes, policy): _representative_run(lanes, policy, seed=seed, steps=steps)
            for lanes in (1, 2) for policy in ("reactive", "anticipatory")}
    svg = Svg(1000, 540, "Representative braking response")
    svg.text(500, 34, "Representative braking response (50% AV, density 0.30)", "title", text_anchor="middle")
    x0, y0, width, height = 80, 75, 850, 340
    _axes(svg, x0, y0, width, height, x_label="Measurement step", y_label="Network mean speed")
    for tick in range(7):
        value = tick
        py = y0 + height - height * value / 6
        svg.add(f'<line class="grid" x1="{x0}" y1="{py:.1f}" x2="{x0 + width}" y2="{py:.1f}"/>')
        svg.text(x0 - 8, py + 4, str(value), "small", text_anchor="end")
    shade_x = x0 + width * (60 - 1) / (steps - 1)
    shade_w = width * 8 / (steps - 1)
    svg.add(f'<rect x="{shade_x:.1f}" y="{y0}" width="{shade_w:.1f}" height="{height}" fill="#fbbf24" opacity="0.20"/>')
    svg.text(shade_x + shade_w / 2, y0 + 14, "braking", "small", text_anchor="middle")
    for index, (key, result) in enumerate(runs.items()):
        color = COLORS[key]
        points = []
        for row in result["per_step"]:
            px = x0 + width * (row["step"] - 1) / (steps - 1)
            py = y0 + height - height * row["mean_speed"] / 6
            points.append(f"{px:.1f},{py:.1f}")
        svg.add(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(points)}"/>')
        lx = 155 + index * 200
        svg.add(f'<line x1="{lx}" y1="490" x2="{lx + 24}" y2="490" stroke="{color}" stroke-width="3"/>')
        svg.text(lx + 30, 494, f"{key[0]} lane, {key[1]}", "small")
    svg.save(output)


def create_spacetime_figure(output: Path, *, seed: int = 1, steps: int = 180) -> None:
    """Plot vehicle trajectories for comparable one- and two-lane scenarios."""
    runs = {
        1: _representative_run(1, "anticipatory", seed=seed, steps=steps),
        2: _representative_run(2, "anticipatory", seed=seed, steps=steps),
    }
    panels = [(1, 0, "One lane"), (2, 0, "Two lanes: lane 1"), (2, 1, "Two lanes: lane 2")]
    svg = Svg(1200, 470, "Space-time traffic trajectories")
    svg.text(600, 30, "Vehicle trajectories after controlled braking", "title", text_anchor="middle")
    svg.text(600, 49, "50% anticipatory AV, density 0.30; red path is the disturbed vehicle", "small", text_anchor="middle")
    for panel_index, (lanes, lane, label) in enumerate(panels):
        x0 = 60 + panel_index * 390
        y0, width, height = 78, 340, 315
        _axes(svg, x0, y0, width, height, x_label="Step", y_label="Road position")
        svg.text(x0, y0 - 12, label, "panel")
        rows = [row for row in runs[lanes]["trajectories"] if row["lane"] == lane]
        point_paths = {"human": [], "av": [], "disturbed": []}
        for row in rows:
            px = x0 + width * (row["step"] - 1) / (steps - 1)
            py = y0 + height - height * row["position"] / 199
            category = (
                "disturbed"
                if row["vehicle_id"] == 0
                else row["vehicle_type"]
            )
            point_paths[category].append(f"M{px:.1f},{py:.1f}h0.01")
        styles = {
            "human": ("#64748b", "0.38", "1.3"),
            "av": ("#2563eb", "0.38", "1.3"),
            "disturbed": ("#dc2626", "0.90", "2.2"),
        }
        for category, commands in point_paths.items():
            color, opacity, stroke_width = styles[category]
            svg.add(
                f'<path d="{"".join(commands)}" fill="none" stroke="{color}" '
                f'stroke-width="{stroke_width}" stroke-linecap="round" '
                f'opacity="{opacity}"/>'
            )
        for tick, value in enumerate((0, 50, 100, 150, 200)):
            py = y0 + height - height * tick / 4
            svg.text(x0 - 7, py + 3, str(value), "small", text_anchor="end")
    svg.save(output)


def generate_all(summary_path: Path, output_dir: Path, *, seed: int = 1) -> list[Path]:
    rows = read_summary(summary_path)
    outputs = [
        output_dir / "shock-summary.svg",
        output_dir / "shock-recovery-curves.svg",
        output_dir / "spacetime-comparison.svg",
    ]
    create_summary_figure(rows, outputs[0])
    create_recovery_curves(outputs[1], seed=seed)
    create_spacetime_figure(outputs[2], seed=seed)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    outputs = generate_all(args.summary, args.output_dir, seed=args.seed)
    for output in outputs:
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
