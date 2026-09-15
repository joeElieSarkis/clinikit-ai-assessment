"""Render the saved evaluation as a portable report and exportable figures."""
from html import escape
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, GREEN, RUST, PAPER = "#223c36", "#39705e", "#b85f3e", "#f7f5ef"


def figure_file(fig, path):
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight", facecolor=PAPER)
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)
    text = path.with_suffix(".svg").read_text(encoding="utf-8")
    return text[text.index("<svg"):]


def figures(result, directory):
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.edgecolor": "#a7b3a9", "text.color": INK,
                         "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                         "axes.facecolor": PAPER, "figure.facecolor": PAPER, "svg.fonttype": "none", "svg.hashsalt": "clinikit-attendance"})
    charts = {}
    curves, metrics = result["curves"], result["test"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.5), layout="constrained")
    axes[0].step(curves["recall"], curves["precision"], where="post", color=GREEN, lw=2)
    axes[0].axhline(metrics["prevalence"], color=RUST, ls="--", lw=1.2, label=f"No-skill reference ({metrics['prevalence']:.1%})")
    axes[0].scatter(metrics["recall"], metrics["precision"], s=55, color=RUST, zorder=5, label="Frozen operating point")
    axes[0].set(title="Precision and recall", xlabel="Recall · share of no-shows found", ylabel="Precision · share flagged who missed", xlim=(0, 1), ylim=(0, 1.04))
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    axes[1].plot(curves["fpr"], curves["tpr"], color=GREEN, lw=2)
    axes[1].plot([0, 1], [0, 1], color=RUST, ls="--", lw=1.2)
    axes[1].set(title=f"ROC curve · AUC {metrics['roc_auc']:.3f}", xlabel="False-positive rate", ylabel="True-positive rate", xlim=(0, 1), ylim=(0, 1.04))
    charts["ranking"] = figure_file(fig, directory / "ranking")
    fig, ax = plt.subplots(figsize=(6.8, 4.2), layout="constrained")
    importance = list(reversed(result["importance"]))
    labels = [row["feature"].replace("_", " ") for row in importance]
    ax.barh(labels, [row["mean"] for row in importance], xerr=[row["std"] for row in importance], color=GREEN, height=.55, error_kw={"ecolor": "#82968b", "capsize": 2})
    ax.axvline(0, color=INK, lw=.8)
    ax.set(xlabel="Decrease in validation average precision after shuffling")
    charts["importance"] = figure_file(fig, directory / "feature-importance")
    fig, ax = plt.subplots(figsize=(5.5, 3.5), layout="constrained")
    ax.plot([0, 1], [0, 1], ls="--", lw=1.2, color=RUST, label="Perfect agreement")
    ax.plot(curves["calibration_predicted"], curves["calibration_observed"], "o-", color=GREEN, label="Six equal-count test bins")
    ax.set(xlabel="Mean predicted no-show probability", ylabel="Observed no-show rate", xlim=(0, 1), ylim=(0, 1))
    ax.legend(frameon=False, fontsize=8)
    charts["calibration"] = figure_file(fig, directory / "calibration")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.5), layout="constrained")
    for ax, field, title in zip(axes, ["previous_no_shows", "appointment_type"], ["Previous missed appointments", "Appointment type"]):
        rows = result["audit"]["training_rates"][field]
        positions = np.arange(len(rows))
        ax.barh(positions, [row["rate"] * 100 for row in rows], color=GREEN, height=.5)
        ax.set_yticks(positions, [row["label"] for row in rows])
        ax.invert_yaxis()
        for index, row in enumerate(rows):
            ax.text(row["rate"] * 100 + 1, index, f"{row['rate']:.0%}  (n={row['n']})", va="center", fontsize=8)
        ax.set(title=title, xlabel="Observed no-show rate (%)", xlim=(0, min(115, max(row["rate"] for row in rows) * 100 + 25)))
    charts["exploration"] = figure_file(fig, directory / "training-patterns")
    return charts


def render_report(result, output, html_path):
    charts = figures(result, output / "figures")
    template = (Path(__file__).parent / "report.html").read_text(encoding="utf-8")
    replacements = {"RESULTS": json.dumps(result, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c"),
                    "MODEL": escape(result["selected_model"]), "TOTAL": f"{result['audit']['rows']:,}",
                    "PREVALENCE": f"{result['audit']['prevalence']:.1%}", "AP": f"{result['test']['average_precision']:.3f}",
                    "AUC": f"{result['test']['roc_auc']:.3f}", "DATE": result["generated_at"][:10],
                    "THRESHOLD": f"{result['threshold']:.0%}", "CHART_RANKING": charts["ranking"],
                    "CHART_IMPORTANCE": charts["importance"], "CHART_CALIBRATION": charts["calibration"],
                    "CHART_EXPLORATION": charts["exploration"]}
    for key, value in replacements.items():
        template = template.replace("{{" + key + "}}", value)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(template, encoding="utf-8")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = json.loads((root / "ml/results/results.json").read_text(encoding="utf-8"))
    render_report(result, root / "ml/results", root / "frontend/public/attendance/index.html")
