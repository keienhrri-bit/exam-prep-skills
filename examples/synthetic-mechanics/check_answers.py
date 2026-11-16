# /// script
# requires-python = ">=3.10"
# dependencies = ["sympy>=1.12"]
# ///
"""用 SymPy 独立重算合成题的三个答案，再确认 solution.md 的 **答** 行写的是同样的数。

用法：uv run check_answers.py      全部一致时退出码 0
"""
import re
import sys
from pathlib import Path

import sympy as sp

HERE = Path(__file__).resolve().parent

m, g, L, mu, v0, vA, vB = sp.symbols("m g L mu v0 v_A v_B", real=True)
sin_t, cos_t = sp.Rational(3, 5), sp.Rational(4, 5)
vals = {g: 10, L: 2, mu: sp.Rational(1, 4)}

# 第 1 问：动能定理
eq1 = sp.Eq(m * g * L * sin_t - mu * m * g * cos_t * L, sp.Rational(1, 2) * m * v0**2)
v0_val = [s for s in sp.solve(eq1.subs(vals), v0) if s > 0][0]

# 第 2 问：动量守恒 + 动能守恒，去掉 vA = v0 的未碰解
sols = sp.solve([sp.Eq(m * v0_val, m * vA + 2 * m * vB),
                 sp.Eq(m * v0_val**2, m * vA**2 + 2 * m * vB**2)], [vA, vB], dict=True)
after = [s for s in sols if s[vA] != v0_val][0]

# 第 3 问：上滑时摩擦力沿斜面向下
a_up = (g * (sin_t + mu * cos_t)).subs(vals)
s_val = sp.nsimplify(after[vA] ** 2 / (2 * a_up))

computed = {"第 1 问 v0": v0_val, "第 2 问 vA": after[vA], "第 2 问 vB": after[vB], "第 3 问 s": s_val}
expected = {"第 1 问 v0": 4, "第 2 问 vA": sp.Rational(-4, 3), "第 2 问 vB": sp.Rational(8, 3), "第 3 问 s": sp.Rational(1, 9)}
# solution.md 的 **答** 行里必须原样出现的写法
written = {"第 1 问 v0": r"v_0 = 4\ \mathrm{m/s}", "第 2 问 vA": r"v_A = -\tfrac{4}{3}",
           "第 2 问 vB": r"v_B = \tfrac{8}{3}", "第 3 问 s": r"s = \tfrac{1}{9}\ \mathrm{m}"}

answers = "\n".join(re.findall(r"^\*\*答\*\*：.*$", (HERE / "solution.md").read_text(encoding="utf-8"), re.M))
ok = True
for k in expected:
    same = sp.simplify(computed[k] - expected[k]) == 0
    shown = written[k] in answers
    ok &= same and shown
    print(f"{k}: SymPy={computed[k]}  期望={expected[k]}  {'一致' if same else '不一致'}；**答** 行{'有' if shown else '没有'}这个写法")
print("全部一致" if ok else "有不一致，回头重推")
sys.exit(0 if ok else 1)
