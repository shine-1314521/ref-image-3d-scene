# 故障字典

用法：先按「症状」查，再看「归因阶段」决定是改参数还是回退重做。
一张图里的问题往往只有**一个**根因，别同时改三处——那样你会失去归因能力。

---

## 一、画面整体

| 症状 | 根因 | 处方 | 归因 |
|---|---|---|---|
| 整体发灰、发白、对比弱 | ① 调色在 sRGB 空间做 ② gradientMap 标了 sRGB 被二次线性化 ③ ambient 过高 | 按此顺序查：删手写 gamma → `gradientMap.colorSpace = NoColorSpace` → `ambient` 降到 0.2 以下 | 3/5 |
| 整体偏暗 | ① 色阶最低阶 <0.12 ② 主光强度不够 ③ 缺 OutputPass | 提 `ramp[0]` 到 0.18；`sunIntensity` +30%；补 `OutputPass` | 3/5 |
| 过曝，大片纯白 | ① `exposure` >1.2 ② Bloom threshold 太低 ③ 地面材质色接近 1.0 | `exposure` 回 1.0；threshold 0.85；材质色上限 0.85 | 4/5 |
| 颜色发绿/发紫，说不清 | 重复做了色彩空间转换（renderer 一次 + pass 里一次） | 只保留 `renderer.outputColorSpace` 与 `OutputPass`，其余全删 | 5 |
| 加了后处理反而更丑 | 用后处理掩盖光照问题 | 关掉 `post.enabled` 对照；若直出更干净，回 Stage 4 补光 | 4 |

## 二、描边

| 症状 | 根因 | 处方 | 归因 |
|---|---|---|---|
| 描边像黑框，至少 10px | 宽度按世界单位给的（原稿 `0.02` 即此坑） | 改像素换算 `px * 2*tan(fov/2)/height`，默认 1.8px | 3 |
| 立方体角、锥体接缝处描边裂口 | 硬边几何顶点法线不连续 | 描边几何：`deleteAttribute('uv')` → `mergeVertices` → `computeVertexNormals` | 3 |
| 远处描边和近处一样粗 | 外扩量没乘视距 | `mv.xyz += n * uWidth * dist * fade` | 3 |
| 描边忽有忽无，旋转时闪 | `frustumCulled` 用主体包围盒判定，被误剔除 | 描边 mesh 设 `frustumCulled = false` | 3 |
| 描边在花瓣/旗帜上消失 | BackSide 在双面薄片上翻面 | 薄片改用 `OutlinePass`，或双面材质 + 顶点外扩 | 3 |
| 描边被 Bloom 糊成光晕 | 描边色太亮 | `outline.color` 亮度压到 0.15 以下（深紫 `#241a33`） | 3/5 |

## 三、材质与光照

| 症状 | 根因 | 处方 | 归因 |
|---|---|---|---|
| 色阶看不出台阶，像平滑渐变 | ① gradientMap 用了 `LinearFilter` ② `steps` 过多 ③ 环境光太强填平了明暗 | 三件一起查：NearestFilter、steps 降到 3–4、ambient <0.2 | 3 |
| 阴影是软糊的一团 | 阴影贴图类型/尺寸 | `shadow.type = 'Basic'`（最硬最卡通）或 PCF + `mapSize 2048` + 缩小 `cameraSize` | 4 |
| 阴影边缘有锯齿条纹（shadow acne） | bias 不足 | `bias -0.0006`、`normalBias 0.02`；再不行提 `mapSize` | 4 |
| 阴影和物体分离（peter-panning） | `normalBias` 过大 | 降到 0.01，改用 `bias` 微调 | 4 |
| 阴影是纯黑，很脏 | 没有补光 | 加 `HemisphereLight`（天空色冷、地面色暖、强度 0.5），**不要**给阴影单独上色 | 4 |
| 出现塑料高光 | 场景混入 `MeshStandardMaterial` 或环境贴图 | 全场景统一 `MeshToonMaterial` | 3 |
| 主体亮得发白，丢色阶 | 材质色接近 1.0 | 材质基色 ≤0.85，靠光提亮而不是靠色 | 3/4 |

## 四、天空与雾

| 症状 | 根因 | 处方 | 归因 |
|---|---|---|---|
| 天空一片平滑渐变，没层次 | 只有 2 段或 softness 过大 | `bands` 加到 2 项（3 段），`softness` 降到 0.03 | 4 |
| 天空出现同心圆/色带断层 | 8 位色深 + 平滑渐变 | 加 `noise` 0.008 抖动；或把渐变改成分段 | 4 |
| 天空被雾糊白 | 用了 `MeshBasicMaterial`/标准材质做天空 | 改 `ShaderMaterial`（默认无雾）+ `fog: false` | 4 |
| 远景边缘像剪纸 | 雾太淡或雾色不匹配 | `density` ×1.5；`fog.color` 必须取 `skyBottom` | 4 |
| 雾把主体也压灰了 | `density` >0.05 | 降到 0.02，或改线性雾 `near/far` 精确控制 | 4 |

## 五、后处理

| 症状 | 根因 | 处方 | 归因 |
|---|---|---|---|
| 全屏发光 | `threshold` <0.7 | 提到 0.85；发光物单独提亮 | 5 |
| 暗角压死四角 | `vignette.amount` >0.45 | 降到 0.28，`softness` 0.55 | 5 |
| 加后处理后变暗 | 少了 `OutputPass` | 补上，且必须放最后 | 5 |
| Bloom 只亮不糊 | `radius` 太小 | 0.3 → 0.45 | 5 |
| 调色像手机滤镜 | `tintMix` >0.4 或 `saturation` >1.3 | 回到 0.28 / 1.12 | 5 |

## 六、动态与交互

| 症状 | 根因 | 处方 | 归因 |
|---|---|---|---|
| 风摆像整体抖动 | 缺相位差，且根部没锁 | 每个物体随机相位 + `smoothstep(0, h, y)` 高度权重 | 6 |
| 风摆时有时无 | `onBeforeCompile` 缺 `customProgramCacheKey` | 加上 `material.customProgramCacheKey = () => 'wind'` | 6 |
| 粒子糊成一片白光 | 颜色过亮 / alpha 边缘太硬 | 亮度降到 0.8，`size` 减小，贴图边缘做羽化 | 6 |
| 相机拖拽时画面抖 | 视差直接改 `camera.position`，与 OrbitControls 打架 | 视差作用在「世界组」而非相机 | 7 |
| 相机钻进地面 | 没限 `maxPolarAngle` | 设 1.45（约 83°） | 7 |
| 手机页面跟着滚 | 缺 `touch-action: none` | canvas 加该样式 | 7 |

**装配与相机类**（完整算法见 `camera-and-assembly.md`）：

| 症状 | 根因 | 处方 | 归因 |
|---|---|---|---|
| 主体像闭合实体，缝/开口完全看不见 | 朝向背对相机 | 单轴 A/B 反转 `rotation.y`，两组截图按写死的判据比 | 2 |
| 特征偏到一侧或朝下 | `rotation.z` 过头 | 收回到 ±0.15 内 | 2 |
| 加了高光/暗带，画面还是平的 | 贴片 z < 挤出体 `depth/2`，埋在实体内部 | `z = depth/2 + 0.004` | 3 |
| 附肢只剩一道描边折痕，像凹坑 | 根部落在宿主曲面以内 | 先算该高度宿主半径（含 z 缩放），根部外移 | 2 |
| 角色转身后手臂/钳子脱离接触物 | 子件写了世界坐标 | 改挂角色 Group，子件用组内坐标 | 2 |
| 相机穿出墙外，看到墙背面或一片纯色 | `maxDistance × sin(方位限位) > 墙距` | 限位按墙距反解，或加射线收缩 | 7 |
| 拖到极限时相机像「被墙吸住」 | 用硬 clamp 改 x/z，方位被悄悄改 | 改沿 `target→camera` 射线收缩，保持极角 | 7 |
| 方位锁死在一个角度，怎么拖都不动 | `min/maxAzimuthAngle` 写成 ±π，折回后相等 | 全周模式写 `±Infinity` | 7 |
| 远处能俯看就穿天花板，锁死又不自由 | 极角下限是固定值 | 按 `acos((ceilY - target.y) / L)` 动态算 | 7 |

## 七、性能与工程

| 症状 | 根因 | 处方 | 归因 |
|---|---|---|---|
| 缩放窗口画面拉伸 | 只改了 `setSize`，漏了 `camera.aspect` + `updateProjectionMatrix` | 三处同步 | 8 |
| 4K 屏掉一半帧 | 未限 `pixelRatio` | 上限 2 / 移动 1.5 | 8 |
| 切标签页回来画面瞬移 | `getDelta()` 累积了大值 | `Math.min(dt, 0.05)` 夹住 | 8 |
| 内存持续增长 | 每帧 `new Vector3 / new Color` | 提到循环外复用；几何与材质共享 | 8 |
| 双击打开白屏 | 断网，CDN 不可达 | 本地 `vendor/` 化，或提示需联网 | 8 |
| 控制台刷 `THREE.WebGLRenderer: Context Lost` | 移动端后台切换 | 监听 `webglcontextlost` 并显示兜底文案 | 8 |

---

## 八、版本差异（踩过就记下来）

| 项 | r150 及以前 | r152+ / r160 | 处理 |
|---|---|---|---|
| 输出色彩空间 | `outputEncoding = sRGBEncoding` | `outputColorSpace = SRGBColorSpace` | 用新的，旧的会报警告 |
| 后处理输出 | 手动 gamma / GammaCorrectionShader | `OutputPass` | 用 `OutputPass`，只此一次 |
| 光照单位 | `useLegacyLights = true`（强度常 >1 才亮） | 物理光照（默认 false） | 迁移时强度整体除以 π 左右，重新校准 |
| 伽马校正 | `texture.encoding` | `texture.colorSpace` | 新 API |
| UMD 构建 | `build/three.min.js` 可用 | r160 起移除 | 只能走 importmap / 打包 |

## 九、归因速判

拿不准是哪个阶段的问题时，问四个问题：

1. **关掉后处理还难看吗？** 难看 → 问题在 3/4，不在 5。
2. **换成纯灰材质还难看吗？** 难看 → 问题在 2（构图），不在 3。
3. **关掉雾和天空，主体本身成立吗？** 不成立 → 问题在 2（比例/机位）。
4. **转一圈看还成立吗？** 不成立 → 问题在装配或机位（2/7），不在材质。
   悬空、脱离接触、看到墙背面，全是这一问抓出来的。

四问都答「还行」但整体仍不像参考图 → 回 Stage 0 重提取色板，不是继续调参。
