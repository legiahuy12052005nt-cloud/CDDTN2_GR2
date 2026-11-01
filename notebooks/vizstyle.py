"""Kiểu biểu đồ dùng chung cho notebook và báo cáo PDF (matplotlib).

Bảng màu: thứ tự màu phân loại cố định (đã kiểm tra an toàn mù màu);
cặp phân cực xanh ↔ đỏ, điểm giữa xám cho 3 nhãn cảm xúc.
"""
import matplotlib as mpl
import matplotlib.pyplot as plt

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
VIOLET, RED = "#6250d6", "#e34948"
GRAY = "#9a9993"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
SENT_COLORS = {"neg": RED, "neu": GRAY, "pos": BLUE}
SENT_LABELS = {"neg": "Tiêu cực", "neu": "Trung tính", "pos": "Tích cực"}


def apply():
    mpl.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.frameon": False, "legend.fontsize": 8,
        "lines.linewidth": 2, "figure.dpi": 110, "savefig.dpi": 200,
        "savefig.bbox": "tight", "figure.facecolor": "white",
    })


def save(fig, path):
    fig.savefig(path)
    plt.close(fig)


def thousands(x, _=None):
    return f"{x:,.0f}".replace(",", ".")
