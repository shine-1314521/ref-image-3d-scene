# CONFIG 字段参考

所有可调视觉参数的唯一事实来源。**正文出现同名字面值时，一律改为读 CONFIG。**
下表的默认值是「中性起点」：能看、不惊艳，目的是让后续每次调整都有基线可比。

命名约定：颜色一律 `#rrggbb` 字符串（代码里经 `new THREE.Color()` 自动转入线性工作空间）；
方向一律归一化前的 `[x, y, z]` 数组（y 向上）；角度用弧度；尺寸用世界单位。

---

## meta

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `title` | string | `'Untitled Scene'` | 页面标题与 HUD 标识，不影响渲染 |

## camera

| 字段 | 类型 | 默认 | 范围建议 | 影响 |
|---|---|---|---|---|
| `fov` | number | `45` | 35–60（人眼感 40–50，广角 60–75） | 透视强度。改它会连带改变构图，须回 Stage 2 复核 |
| `near` / `far` | number | `0.1` / `800` | far ≥ 天空球半径 ×1.5 | 裁剪面。far 太大伤深度精度，太小切掉远景 |
| `position` | [x,y,z] | `[8, 5, 12]` | 距主体 3–6 倍主体高 | 机位。这是构图主旋钮 |
| `target` | [x,y,z] | `[0, 2, 0]` | — | 看点。与 position 共同决定地平线高度 |
| `minDistance` / `maxDistance` | number | `6` / `40` | — | 缩放范围。min 太大会挡住近景，太小会穿模 |
| `maxPolarAngle` | number | `1.45` | ≤ 1.55（约 89°） | 俯仰上限，防止相机钻到地面以下 |
| `damping` | number | `0.08` | 0.06–0.1 | 惯性。>0.15 会飘，<0.05 会顿 |
| `parallax.amount` | number | `0.12` | 0–0.25 | 指针视差幅度（世界单位）。0 即关闭 |
| `parallax.ease` | number | `0.06` | 0.03–0.12 | 跟随速度。越大越紧跟，过大会晕 |

## palette

七色够用，多余交给光照生成。每个色在 Stage 0 已定用途，不要在这里换用途。

| 字段 | 默认 | 用途 |
|---|---|---|
| `skyTop` | `'#2b3d6b'` | 天空顶部（最暗/最冷） |
| `skyMid` | `'#6f8fc4'` | 天空中段，决定整体色相 |
| `skyBottom` | `'#e8c9a8'` | 天空底部 + **雾色取这个** |
| `sun` | `'#ffe8c0'` | 太阳本体与轮廓光 |
| `mainLight` | `'#ffd9a0'` | 主光颜色（暖） |
| `fillSky` | `'#9db8e8'` | 半球光天空色（冷），负责「阴影偏冷」 |
| `fillGround` | `'#5b4a3a'` | 半球光地面色（暖褐），负责反弹光 |
| `shadowTint` | `'#8fb2ff'` | 调色阶段的阴影染色，偏蓝紫 |
| `accent` | `'#ff6b6b'` | 点缀色（旗、灯、花），画面唯一高饱和 |

改色板的铁律：**先改 `mainLight` 与 `skyBottom`，其余跟着走**。一次换三个以上颜色，等于重做 Stage 0。

## toon

| 字段 | 类型 | 默认 | 范围 | 说明 |
|---|---|---|---|---|
| `steps` | number | `4` | 3–5 | 色阶数。3 最卡通，5 接近半写实。必须等于 `ramp.length` |
| `ramp` | number[] | `[0.18, 0.40, 0.66, 1.0]` | 每项 0.1–1.0，递增 | 各阶亮度系数。最低阶决定暗部亮度，**别低于 0.12**，否则死黑 |
| `outline.enabled` | boolean | `true` | — | 总开关。移动端低端机可关 |
| `outline.px` | number | `1.8` | 1.2–2.5 | 描边宽度，**单位是像素**（1080p 基准），不是世界单位 |
| `outline.color` | hex | `'#241a33'` | 亮度 ≤0.2 | 深紫比纯黑柔和；太亮会被 Bloom 糊散 |
| `outline.fadeStart` / `fadeEnd` | number | `20` / `80` | — | 视距（世界单位）超过 fadeStart 开始变细，到 fadeEnd 归零 |

描边像素 → 世界单位的换算（写在代码里，不要手算）：

```
worldWidth ≈ px * 2 * tan(fov/2) / viewportHeight
```

1080p、fov 45 时约 `0.00077 / 单位距离`（即 `2·tan(fov/2)/视口高度`）。原稿的 `0.02` 在这个尺度下约 26px，是黑框不是描边。

## light

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `sunDir` | [x,y,z] | `[-0.55, 0.42, -0.72]` | 主光方向（指向光源）。y 越小越接近黄昏侧光 |
| `sunIntensity` | number | `2.6` | 主光强度。r155+ 为物理光照单位，2–3 是常见区间 |
| `ambient` | number | `0.15` | 环境光。>0.4 会洗掉色阶，赛璐璐最怕这个 |
| `hemi.sky` | hex | `'#9db8e8'` | 半球光天空色，决定「阴影偏冷」是否成立 |
| `hemi.ground` | hex | `'#5b4a3a'` | 半球光地面色 |
| `hemi.intensity` | number | `0.55` | 0.3–0.8。它是补光主力，不要靠 ambient 提亮 |
| `shadow.enabled` | boolean | `true` | 阴影总开关 |
| `shadow.mapSize` | number | `2048` | 1024（移动）/ 2048（桌面）/ 4096（大场景） |
| `shadow.cameraSize` | number | `24` | 阴影相机半宽。贴合场景，过大导致锯齿 |
| `shadow.bias` / `normalBias` | number | `-0.0006` / `0.02` | 治阴影痤疮（条纹）与漏光（peter-panning） |
| `shadow.type` | string | `'PCF'` | `'Basic'` 最硬（最卡通）、`'PCF'` 默认、`'VSM'` 最柔 |

## sky

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `radius` | number | `400` | 天空球半径，须 < `camera.far` |
| `bands` | number[] | `[0.42, 0.62]` | 分段位置（0 底部→1 顶部）。两项 = 三段色 |
| `softness` | number | `0.04` | 分段过渡宽度。0.01 硬边（更卡通），0.1 接近渐变（失风格） |
| `sunDisc.enabled` | boolean | `true` | 是否画太阳圆盘 |
| `sunDisc.size` | number | `0.06` | 视角半径（弧度），越大太阳越大 |
| `sunDisc.gain` | number | `1.4` | 太阳亮度增益，>2 会触发 Bloom 溢出 |
| `noise` | number | `0.008` | 天空极轻噪点，破带状色阶（0 关闭） |

## fog

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enabled` | boolean | `true` | 关掉后远景硬边，除非参考图本来就是无限远平面 |
| `color` | hex | `'#e8c9a8'` | **取 `palette.skyBottom`**，不要取中段色 |
| `density` | number | `0.018` | 0.008（清淡）/ 0.018（标准）/ 0.04（浓雾）。>0.05 主体开始发灰 |

## post

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enabled` | boolean | `true` | 总开关。关掉后走 `renderer.render` 直出（调参时用它对照） |
| `toneMapping` | string | `'none'` | `'none'` 保色阶纯度；`'aces'` 保高光但会降饱和；`'linear'` 折中 |
| `exposure` | number | `1.0` | 仅 toneMapping ≠ none 时生效，>1.2 易过曝 |
| `bloom.strength` | number | `0.55` | 0.4–0.8。>1 全屏泛白 |
| `bloom.radius` | number | `0.4` | 0.3–0.5。越大越糊 |
| `bloom.threshold` | number | `0.85` | 0.8–0.9。**低于 0.7 整屏发光**，这是最常见的翻车点 |
| `grade.saturation` | number | `1.12` | 1.0–1.25。>1.4 溢出成霓虹 |
| `grade.contrast` | number | `1.06` | 绕线性中灰 0.18 做对比，1.0–1.15 |
| `grade.shadowTint` | hex | `'#8fb2ff'` | 暗部染色，冷色。与 `palette.shadowTint` 同源 |
| `grade.highlightTint` | hex | `'#ffd9a8'` | 亮部染色，暖色 |
| `grade.tintMix` | number | `0.28` | 染色强度，0–0.5。>0.4 变「滤镜味」 |
| `grade.lift` | number | `0.0` | 整体提亮（线性），用于救死黑，0–0.02 |
| `vignette.amount` | number | `0.28` | 0–0.5。>0.45 压死四角 |
| `vignette.softness` | number | `0.55` | 越大过渡越缓 |

## anim

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `wind.strength` | number | `0.12` | 世界单位。>0.3 像台风 |
| `wind.speed` | number | `1.1` | 摆动频率 |
| `wind.freq` | number | `1.8` | 沿高度的相位密度。越大越「碎」 |
| `particles.mode` | string | `'petal'` | `'petal'` / `'firefly'` / `'snow'` |
| `particles.count` | number | `260` | 桌面 ≤400 / 移动 ≤150 |
| `particles.size` | number | `0.35` | 世界单位，代 `sizeAttenuation` 生效 |
| `particles.opacity` | number | `0.85` | >0.95 会被 Bloom 糊成光斑 |
| `particles.fall` | number | `0.9` | 下落速度（单位/秒） |
| `particles.drift` | number | `0.5` | 侧向漂移幅度 |
| `particles.bounds` | number | `26` | 分布立方体边长，覆盖镜头可见范围即可 |
| `autoRotate.enabled` | boolean | `true` | 空闲自动环绕 |
| `autoRotate.speed` | number | `0.18` | 0.1–0.3，>0.4 会晕 |
| `autoRotate.idleDelay` | number | `3.0` | 用户停手多少秒后恢复（秒） |

## perf

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `pixelRatioCap` | number | `2` | 桌面上限。4K 屏不设上限会掉一半帧 |
| `mobilePixelRatioCap` | number | `1.5` | 移动端上限 |
| `shadowOnMobile` | boolean | `true` | 关掉后画面塌一层，但能救帧率 |
| `outlineOnMobile` | boolean | `true` | 关掉后风格大损，仅低端机建议关 |
| `bloomOnMobile` | boolean | `false` | 移动端默认关，Bloom 是全屏 pass，最贵 |
| `adaptive.enabled` | boolean | `true` | 自动降级总开关 |
| `adaptive.minFps` | number | `45` | 低于此值触发降级 |
| `adaptive.window` | number | `2.0` | 采样窗口（秒） |

**降级顺序**（不可乱序，先降视觉损失小的）：
`pixelRatio → bloom → shadow → outline`。每次只降一级，降完观察 2s 再判断。

## debug

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `hud` | boolean | `false` | 显示量化测帧面板（主体占比 / 地平线 / FPS）。**Stage 2 必须开，Stage 9 必须关** |

---

## 参数耦合速查

改一个之前，先看它跟谁联动：

| 改它 | 会连带影响 | 处理 |
|---|---|---|
| `camera.fov` | 构图、描边屏幕宽度、透视 | 改完回 Stage 2 复核，并重算描边像素 |
| `camera.position` 距离 | 主体占比、描边粗细、雾浓度观感 | 不要和 fov 同时改 |
| `fog.density` | 整体亮度与对比 | 改雾时先锁光照 |
| `post.bloom.threshold` | 与 `grade.contrast` 互相掩盖 | 先定 threshold，再调 contrast |
| `toon.ramp[0]` | 暗部亮度、阴影「脏不脏」 | 与 `hemi.intensity` 同向调，别反向 |
| `perf.pixelRatioCap` | 描边实际像素宽度 | 降 DPR 后 `outline.px` 需同比补偿 |
