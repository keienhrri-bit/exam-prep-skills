"""合成示例报告的图：每问正常、宽松两种得分。"""
from charts import *  # noqa: F403  （build_report.py 会把 charts.py 所在目录加进 sys.path）


def score():
    rows = [
        ("第 1 问（满分 4）", 4, ACC, "　正常、宽松都是 4"),  # noqa: F405
        ("第 2 问 正常（满分 5）", 3, ACC, "　宽松 5"),  # noqa: F405
        ("第 3 问 正常（满分 6）", 1, BAD, "　宽松 2"),  # noqa: F405
    ]
    return "<figure>" + bars(rows, vmax=6, ticks=[0, 2, 4, 6], label_w=170) + \
        "<figcaption>每问的正常尺度得分；第 3 问在第一步的受力方向上丢了 5 分。</figcaption></figure>"  # noqa: F405


FIGS = {"score": score}
