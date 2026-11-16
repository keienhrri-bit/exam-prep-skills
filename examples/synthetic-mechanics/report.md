<div class="cover">
<div class="kicker">合成示例 · 力学计算题 · 斜面与弹性碰撞</div>

# 斜面—碰撞综合题<br>答卷分析

<div class="meta">合成练习卷一道计算题，满分 15 分。答卷照片由转录者转成文字稿，看不清的一处已和本人确认；判分按正常、宽松两种尺度各算一遍，另有一次独立复判。</div>
</div>

<div class="tiles">
<div class="tile"><div class="big">8<small> / 15</small></div><div class="lab">正常尺度</div></div>
<div class="tile"><div class="big">11<small> / 15</small></div><div class="lab">宽松尺度</div></div>
<div class="tile"><div class="big">2<small> 处</small></div><div class="lab">错误：一处方向，一处漏写依据</div></div>
<div class="tile"><div class="big">5<small> 分</small></div><div class="lab">第 3 问摩擦力方向一处丢的分</div></div>
</div>

## 〇　先说结论

1. **第 1 问全对。** 动能定理列式完整，数值正确。
2. **第 2 问结果对，但少了一个守恒式。** 直接套了弹性碰撞的结论公式，正常尺度丢 2 分。考场上先写动量守恒和动能守恒两个式子，再写结果。
3. **第 3 问错在第一步：上滑时摩擦力的方向。** 上滑时摩擦力沿斜面向下，加速度是 $g(\sin\theta+\mu\cos\theta)$，答卷用了下滑时的加速度，后面的计算全被带偏。这一处丢 5 分，是本卷最大的失分。

<!--FIG:score-->

## 一　逐问判分

| 问 | 满分 | 正常 | 宽松 | 错在哪一步 |
|---|---|---|---|---|
| 1 | 4 | 4 | 4 | 无 |
| 2 | 5 | 3 | 5 | 没列动能守恒式 |
| 3 | 6 | 1 | 2 | 第 1 步受力方向错 |
| 合计 | 15 | 8 | 11 | |

两种尺度差 3 分，全部来自“过程写得不全”和“错了之后的连带计算”。按正常尺度看，真正的知识缺口只有第 3 问那一处。

## 二　第 3 问：错在哪一步

<div class="ch"><span class="no">3</span><span class="tt">A 沿斜面上滑的最大距离</span><span class="sc"><b>1</b> / 6</span></div>

::: you
A 沿斜面上滑，受重力沿斜面的分力和摩擦力，$a = g(\sin\theta - \mu\cos\theta) = 4\ \mathrm{m/s^2}$，$s = \dfrac{v_A^2}{2a} = \dfrac{2}{9}\ \mathrm{m}$
:::

::: err
第一步的受力方向。滑动摩擦力和**相对运动**方向相反：A 往上滑，摩擦力就沿斜面向下，和重力的分力同向，两者相加。答卷写的 $g(\sin\theta-\mu\cos\theta)$ 是下滑时的加速度，第 1 问刚用过，这里照搬了过来。
:::

::: sol
上滑时 $a = g(\sin\theta + \mu\cos\theta) = 10\times(0.6+0.25\times0.8) = 8\ \mathrm{m/s^2}$，

$$s = \frac{v_A^2}{2a} = \frac{(4/3)^2}{2\times 8} = \frac{1}{9}\ \mathrm{m} \approx 0.11\ \mathrm{m}$$
:::

::: pts
受力分析 2 分；加速度 2 分；$s=v_A^2/(2a)$ 列式 1 分、结果 1 分。
:::

::: mem
- 上滑 $a = g(\sin\theta+\mu\cos\theta)$，下滑 $a = g(\sin\theta-\mu\cos\theta)$。同一个斜面，上滑比下滑减速得快。
- 自查办法：$\mu \to 0$ 时两个式子都应退回 $g\sin\theta$；$\mu$ 变大时，上滑的 $a$ 应该变大。
:::

## 三　第 2 问：结果对，过程少一步

<div class="ch"><span class="no">2</span><span class="tt">碰撞后 A、B 的速度</span><span class="sc"><b>3</b> / 5</span></div>

::: you
动量守恒 $mv_0 = mv_A + 2mv_B$；弹性碰撞，由公式 $v_A = \frac{m-2m}{m+2m}v_0 = -\frac43\ \mathrm{m/s}$，$v_B = \frac{8}{3}\ \mathrm{m/s}$
:::

::: err
没写动能守恒式。结论公式是由两个守恒式联立出来的，评分点给的是守恒式本身，直接写结论公式拿不到这 2 分。
:::

::: tip
弹性碰撞固定写三行：动量守恒、动能守恒、结果连同方向。结论公式可以用来心算核对，不要代替前两行。
:::

## 四　下一步

| | 做什么 | 用时 |
|---|---|---|
| **推荐** | 重做第 3 问，再做一道“先上滑后下滑”的变式，两段加速度分开写 | 约 20 分钟 |
| 另一种 | 把本周做过的斜面题里所有摩擦力方向过一遍，只标方向、不算数 | 约 30 分钟 |

选哪一种由你定。
