# 无头截图验收：让「看图」这件事可重复

> R8 要求每张交付都跑视觉门禁，而视觉门禁的输入是一张截图。
> 截图本身会静默失败——**得到一张纯背景色图片，没有任何报错**。
> 本文件解决「怎么稳定地截到图、怎么确认截到的是真画面」。

---

## 1. 三个必须同时满足的条件

| 条件 | 错误做法 | 后果 |
|---|---|---|
| 浏览器模式 | `--headless`（旧模式） | WebGL 帧出不来，写出 12 KB 的纯背景色图 |
| 页面协议 | `file://` | ES module 被 CORS 拦截，`importmap` 失效，画面全空 |
| 结果判据 | 只看「文件存在」 | 空图也是文件，门禁在假画面上跑出 PASS |

正确组合：`--headless=new` + 本地 HTTP + 文件大小与像素双重判空。

---

## 2. 最小可用命令

在场景目录起静态服务器（后台任务，只绑 127.0.0.1）：

```bash
cd <scene-dir> && python -m http.server 8123 --bind 127.0.0.1
```

截图（Git Bash / Windows 路径写法；截图路径用**绝对路径**，相对路径偶发不落盘）：

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new --disable-gpu-sandbox --no-sandbox \
  --use-gl=angle --use-angle=swiftshader \
  --window-size=1280,720 --virtual-time-budget=12000 \
  --screenshot="D:\\<scene-dir>\\preview-final.png" \
  "http://127.0.0.1:8123/09-final.html?hud=0"
```

| 参数 | 作用 | 备注 |
|---|---|---|
| `--headless=new` | 新无头模式，真跑合成器 | **不可省**；旧模式无 WebGL 帧 |
| `--use-angle=swiftshader` | 软件光栅，无 GPU 也能出图 | 慢（约 4–8s/张），但结果确定 |
| `--virtual-time-budget=12000` | 虚拟时间，等后处理链跑完 | 低于 8000 常截到半成品（描边已画、bloom 未合） |
| `--window-size=1280,720` | 画布尺寸 | 与 `parity.json` 的区域框归一化坐标无关，但影响构图占比 |

---

## 3. 判空：两道闸门，缺一不可

```bash
f=preview-final.png
[ -f "$f" ] || { echo "FAIL 未产出"; exit 1; }
sz=$(stat -c%s "$f")
[ "$sz" -gt 100000 ] || { echo "FAIL 疑似空帧 ${sz}B"; exit 1; }
```

```python
# 第二道：主色占比过高 = 整屏同一个颜色 = 没渲染出来
from PIL import Image
import collections
im = Image.open(path).convert('RGB')
px = list(im.getdata())
top_rgb, top_n = collections.Counter(px).most_common(1)[0]
if top_n / len(px) > 0.70:
    raise SystemExit(f'FAIL 主色 {top_rgb} 占 {top_n/len(px):.0%}，疑似空帧')
```

**经验阈值**：正常画面主色占比 15%–45%；单个颜色超过 70% 基本就是空帧。
纯背景色空图会达到 99%，一眼可辨，但必须先算再判，不能靠眼睛瞄文件大小。

---

## 4. 验收钩子（URL 参数）

每个场景都应提供一组无头验收用的开关，让同一份代码能被自动截成不同状态：

| 参数 | 作用 | 用途 |
|---|---|---|
| `?hud=0` | 关掉量化测帧 HUD | 正式截图用，避免数字叠在画面上 |
| `?probe` | 页面打印 `measureFrame` 结果 | 构图占比门禁的输入（见 `threejs-recipes.md` §8） |
| `?cam=az,polar,dist` | 指定机位 | 极位穷举（见 `camera-and-assembly.md` §6.6） |
| `?open=1` | 打开所有可交互物件 | 验证开启状态的几何不穿模 |
| `?tour=1` | 关掉自动环绕与呼吸 | 出图稳定，避免两次截图构图不同 |
| `?hover=N` | 强制第 N 个物件高亮 | 验证悬停态的描边/发光 |

**`?cam=` 的方位角是「世界角」，不是相对初始机位**。
写测试用例前先用探针 dump 一次实际坐标，否则测的是随机方向：

```js
// 临时探针：把相机坐标写进 title，用 --dump-dom 读出来
document.title = 'POS ' + camera.position.toArray().map(v => v.toFixed(2)).join(',');
```

```bash
"…/chrome.exe" --headless=new --window-size=1280,720 --virtual-time-budget=10000 \
  --dump-dom "http://127.0.0.1:8123/09-final.html?hud=0&cam=-2.92,1.20,3.00" \
  | grep -o "<title>[^<]*</title>"
```

---

## 5. 批量多机位

```bash
for spec in "-3.72,1.46,4.90|min-max-max" "-2.12,1.46,4.90|max-max-max" \
            "-2.92,0.62,4.90|mid-min-max" "-2.92,1.46,1.90|mid-max-min"; do
  cam="${spec%%|*}"; tag="${spec##*|}"
  "…/chrome.exe" --headless=new --disable-gpu-sandbox --no-sandbox \
    --use-gl=angle --use-angle=swiftshader --window-size=1280,720 \
    --virtual-time-budget=12000 \
    --screenshot="D:\\<scene-dir>\\shots\\cam-$tag.png" \
    "http://127.0.0.1:8123/09-final.html?hud=0&cam=$cam" 2>/dev/null
  echo "$tag: $(stat -c%s shots/cam-$tag.png 2>/dev/null) bytes"
done
```

文件名带上机位参数，事后能对上图，不用回忆哪张是什么角度。

---

## 6. 故障排查

| 症状 | 根因 | 处方 |
|---|---|---|
| 截图只有十几 KB，整屏背景色 | 用了旧 `--headless` | 换 `--headless=new` |
| 页面空白，控制台报 CORS / module 加载失败 | `file://` 协议 | 起本地 http，用 `127.0.0.1` 访问 |
| 截图大小正常但画面停在半成品 | `virtual-time-budget` 太短 | 提到 12000–16000 |
| 偶发 `GPU state invalid`，文件未写出 | 软件光栅偶发失败 | 重跑一次即可；连续失败再查场景是否过大 |
| 两次截图构图不一致 | 自动环绕/呼吸在跑 | 加 `?tour=1`，或截图前把 `autoRotate` 关掉 |
| `page.goto` 类工具报超时 | 首次编译 shader 慢 | 无头 Chrome 直出比自动化框架更快，优先用它 |
| 中文注释乱码 | 终端编码 | 命令里不要带中文；文件名用 ASCII |

**不要在失败时改成「肉眼看一下截图」**：空图看起来也像「暗色场景」，
这正是本轮浪费最多时间的地方——先跑判空，再看图。

---

## 7. 截图之后立刻做什么

1. 跑 `parity-check.py`（画面门禁），贴原始输出表。
2. 跑构图占比探针（`?probe`），核对主体 cx/cy/w。
3. 极端机位逐张目视，只查三件事：有没有大面积单色、有没有暴露物体内壁、主体是否被切断。
4. 有一项不过就停，不要继续往下做「更多效果」——在坏画面上加分等于给错的基线加滤镜。
