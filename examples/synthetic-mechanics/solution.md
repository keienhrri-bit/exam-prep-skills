# 标准解答与评分点

> 主会话在转录进行的同时写好。每问最后一行 `**答**：…` 由 `check_answers.py` 用 SymPy 核对。

## 第 1 问（4 分）

::: sol
A 在斜面上受重力、支持力和滑动摩擦力。下滑时摩擦力沿斜面向上，大小 $f = \mu mg\cos\theta$。对 A 从顶端到底端用动能定理：

$$mgL\sin\theta - \mu mg\cos\theta\cdot L = \tfrac12 m v_0^2$$

$$v_0 = \sqrt{2gL(\sin\theta - \mu\cos\theta)} = \sqrt{2\times10\times2.0\times(0.6-0.25\times0.8)}\ \mathrm{m/s}$$

**答**：$v_0 = 4\ \mathrm{m/s}$
:::

::: pts
动能定理（或牛顿第二定律加运动学）列式 2 分；摩擦力大小 $\mu mg\cos\theta$ 1 分；结果 1 分。
:::

## 第 2 问（5 分）

::: sol
以向右为正。弹性正碰，动量守恒、动能守恒：

$$m v_0 = m v_A + 2m v_B,\qquad \tfrac12 m v_0^2 = \tfrac12 m v_A^2 + \tfrac12 (2m) v_B^2$$

联立（舍去 $v_A = v_0$ 的未碰解）得

$$v_A = \frac{m-2m}{m+2m}v_0 = -\frac{v_0}{3},\qquad v_B = \frac{2m}{m+2m}v_0 = \frac{2v_0}{3}$$

**答**：$v_A = -\tfrac{4}{3}\ \mathrm{m/s}$（向左，返回斜面），$v_B = \tfrac{8}{3}\ \mathrm{m/s}$（向右）
:::

::: pts
动量守恒式 2 分；动能守恒式 2 分（只写结论公式、不列守恒式，正常尺度不给这 2 分）；两个结果连同方向 1 分。
:::

## 第 3 问（6 分）

::: sol
A 以 $|v_A| = \tfrac43\ \mathrm{m/s}$ 经圆弧冲上斜面。上滑时 A 相对斜面向上运动，滑动摩擦力沿斜面**向下**，与重力沿斜面的分力同向：

$$a = g(\sin\theta + \mu\cos\theta) = 10\times(0.6 + 0.25\times0.8)\ \mathrm{m/s^2} = 8\ \mathrm{m/s^2}$$

$$s = \frac{v_A^2}{2a} = \frac{(4/3)^2}{2\times 8}\ \mathrm{m}$$

**答**：$s = \tfrac{1}{9}\ \mathrm{m} \approx 0.11\ \mathrm{m}$
:::

::: pts
受力分析：上滑时摩擦力沿斜面向下 2 分；加速度 $a = g(\sin\theta+\mu\cos\theta)$ 2 分；$s = v_A^2/(2a)$ 列式 1 分、结果 1 分。
:::

::: mem
- 滑动摩擦力的方向由**相对运动**决定：下滑时沿斜面向上，上滑时沿斜面向下。上滑、下滑的加速度分别是 $g(\sin\theta+\mu\cos\theta)$ 和 $g(\sin\theta-\mu\cos\theta)$。
- 质量 $m_1$ 以 $v_0$ 弹性正碰静止的 $m_2$：$v_1 = \frac{m_1-m_2}{m_1+m_2}v_0$，$v_2 = \frac{2m_1}{m_1+m_2}v_0$。考试中先写两个守恒式，再写结果。
:::
