# ref-image-3d-scene

把一个 2D 参考图变成能跑的 Three.js 动漫风 3D 场景网页 —— 十个阶段、六道闸门、一套可复跑的验收脚本。

A staged workflow for rebuilding a 2D reference image as a runnable cel-shaded Three.js scene, with executable acceptance gates instead of "looks about right".

---

## 它解决什么问题

让 AI 照着参考图做 3D 页面，第一次结果通常不难看，但很容易停在三个地方：

1. **「像」但站不住** —— 正面看没问题，转个角度发现吊灯悬空、桌腿没接上地板、背面是空墙。
2. **「做完了」但其实没看见** —— 五个占比指标全 PASS，主体像素占比 0%。验收表自己骗自己。
3. **「调了很多轮还是不对」** —— 因为一开始的朝向就错了。钳口朝着背面的时候，你调它的每一个控制点都落在错的平面上。

这个 skill 的核心不是「怎么把 3D 做得更好看」，而是**怎么让每一步的结论可以被验证**。

## 三件事跟常规做法不一样

### 一、先写规格书，再写代码

Stage 0 产出 `00-spec.md`，里面是一张 **RCI 表**（Reference Correction Item）：每条修正项都要有可测量的判据和对应的 CONFIG 字段。

```
| ID  | 修正项        | 判据                        | CONFIG 映射          | 状态 |
| R01 | 机位与主体比例 | 主体高度占画面 42–48%        | camera.* / subject.y | TODO |
| R02 | 主色板        | 三主色 ΔE ≤ 12              | palette.*            | TODO |
```

规则里写了「不得有 TODO」，但写了没人读等于没写 —— 所以带了个可执行的检查器：

```bash
python assets/rci-status.py 00-spec.md    # 有 TODO 就退出码 1
```

### 二、验收脚本参数化，换场景不会失效

`assets/parity-check.py` 的语义色板和门限全部外置在 `parity.json`，脚本本身不认识任何具体场景。这一点是踩过坑之后改的：早先版本把「钞票绿占比」「护手红占比」写死在代码里，换个场景两项恒为 0% 却照样打印 PASS。

```bash
python assets/parity-check.py ref.jpg preview-final.png --html 09-final.html
```

输出平均亮度、过曝、死黑、各区域特征色占比、曲线几何构造次数的 PASS/FAIL 表，任一 FAIL 退出码 1。没有配置文件时**明确声明「G3 未执行」并以退出码 2 结束**，不会假装通过。

### 三、无头截图有专门的排错流程

这是整个流程里最耗时间的一环，失败还是静默的：

- `--headless` 旧模式在部分环境下 WebGL 帧出不来，写出 12KB 的纯背景色图，看起来像「渲染 bug」
- `file://` 协议下 ES module 被 CORS 拦截，页面停在 loading
- 相机穿墙时画面是一大块纯黑，跟「光照没调好」长得一样

`references/headless-verify.md` 给了判定树：先看文件大小，再看主色占比，再看相机坐标，最后才怀疑渲染。

## 六道闸门

按违反代价排序，前三条违反即产出报废：

| 闸门 | 检查什么 | 为什么不能省 |
|---|---|---|
| G0 朝向 | 带方向的结构（开口、缝、正面特征）是否朝向观察者 | 朝向错时，后续所有轮廓调参都在错的平面上 |
| G1 几何语言 | 曲线构造次数 ≥12，圆角/旋转体/挤出而非几何体拼接 | 「都是几何图形拼接」是最常见的失败形态 |
| G2 语义色板 | 每个物体用语义色而非直接写色值，ΔE 与参考图对齐 | 换色时不至于全局搜索替换 |
| G3 主体可见性 | 主体与前景特征色在指定区域内的占比 | 五项全 PASS 但主体 0% 的假验收 |
| G4 亮度分布 | 平均亮度、过曝率、死黑率 | 整体偏灰或过曝是最容易「自己看不出来」的 |
| G5 结构 | 六查：接地、连接、悬空、穿插、支撑、闭合 | 转一圈就露馅的那类问题 |

## 装配与相机：四个调参救不回来的坑

`references/camera-and-assembly.md` 单独成文，因为这里面每个问题都不是「参数没调好」：

- **旋转体上的附肢**（鼻子、把手、旋钮）—— 必须先算 attachment 点的壳面位置和法向，再定朝向。凭「大概在表面」放，要么整根埋进壳体只剩一道描边折痕，要么悬空。
- **挤出体的贴片高光** —— 前表面在 `z = +depth/2`（`ExtrudeGeometry` 居中）。贴在 `z < depth/2` 的「高光」全在实体内部，从来没渲染出来过。
- **刚体旋转约束** —— 角色面向桌子才有「螯压在钱堆上」这个关系。绕 y 轴转身，螯就脱离桌面了。所以机位不是自由的，是被这个约束反推出来的。
- **相机可达域** —— 距离拉满 + 方位打满时，相机可能穿出墙外（`4.9 × sin(1.46) ≈ 4.85 > 前墙 3.65`）。硬 clamp 坐标会让相机贴墙滑动、方位被悄悄改掉；正确做法是沿 target→camera 射线求最近交点，把相机推近并保持极角。

## 安装

```bash
git clone https://github.com/<your-name>/ref-image-3d-scene.git \
  ~/.workbuddy/skills/ref-image-3d-scene
```

或者直接把目录复制到 skills 目录：

```
~/.workbuddy/skills/ref-image-3d-scene/
├── SKILL.md                     # 主规则：15 条硬规则 + 十阶段门禁
├── CHANGELOG.md
├── references/
│   ├── reference-spec.md        # Stage 0：怎么把参考图拆成可校验的规格书
│   ├── visual-parity.md         # 六道闸门 + 占比超标四步归因
│   ├── stage-gates.md           # 十个阶段各自的验收清单
│   ├── camera-and-assembly.md   # 装配约束与相机可达域
│   ├── headless-verify.md       # 无头截图排错
│   ├── threejs-recipes.md       # 几何族 / 描边 / 后处理配方
│   ├── config-reference.md      # CONFIG 字段说明
│   └── troubleshooting.md       # 症状 → 根因 → 改哪
└── assets/
    ├── parity-check.py          # 参数化验收脚本
    ├── parity.json              # 场景语义配置（可换）
    ├── rci-status.py            # RCI 表检查器
    ├── reference-spec-template.md
    └── starter.html             # Stage 2 起步骨架
```

## 快速上手

```
加载 ref-image-3d-scene，从 Stage 0 开始，参考图见附件
```

之后它会先产出 `00-spec.md`（含 RCI 表）和 `00-refs.md`（联网工程参考），再逐阶段推进。每个阶段结束时给出门禁自检结果和偏差说明。

## 前置要求

- Three.js 0.160+（`importmap` 方式引入）
- Python 3.8+ 与 Pillow（跑验收脚本）
- 一个能跑 WebGL 的浏览器；无头验证推荐 Chrome `--headless=new`

## 已知局限

- **单件挤出的形状在侧后方视角会退化**：比如螯的开口缝在另一侧时，背面看就是一个圆环。这是「用一件挤出体表达有开口的结构」的固有代价，需要分层建模才能根治。
- **验收脚本只覆盖像素级指标**，构图语义（比如「参考图中轴有一条走道」）仍然要人看。占比超标时先找构图差异，不要先砍物体尺寸 —— 这条是踩坑得来的。
- **无头截图验证基于 swiftshader 软件渲染**，真实 GPU 上的 bloom 强度与描边宽度可能有偏差，交付前建议人工看一眼。
- 目前只针对**单文件 / 单页**场景，不覆盖多场景切换或资源预加载流水线。

## 许可

MIT，见 [LICENSE](LICENSE)。
