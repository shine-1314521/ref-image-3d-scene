# -*- coding: utf-8 -*-
"""
视觉对等验收（ref-image-3d-scene / Stage 9 硬门禁）

用途：把「像不像参考图」变成可复跑的 pass/fail，而不是靠一句主观评价。
v1 的教训：AABB 占比门禁五项全 PASS，画面却完全不像。
v2 的教训：脚本里写死了「钞票绿 / 护手红 / 桌面区」，换个场景两项恒为 0%，
            脚本照样打印 PASS —— 通用资产变成了单场景一次性脚本。
v3（本版）：语义区域、特征色谓词、容差全部外置到 parity.json。

用法：
    python parity-check.py                                  # ref.jpg vs preview-final.png + ./parity.json
    python parity-check.py ref.jpg other.png                # 指定成品图
    python parity-check.py ref.jpg other.png --html 09-final.html
    python parity-check.py ref.jpg other.png --config mine.json

退出码：0 = 全 PASS；1 = 有项 FAIL；2 = 配置缺失导致 G3 未执行（不算通过）。
"""
import json
import os
import re
import statistics
import sys
import warnings

from PIL import Image

warnings.filterwarnings("ignore", category=DeprecationWarning)

REF = sys.argv[1] if len(sys.argv) > 1 else "ref.jpg"
OUT = sys.argv[2] if len(sys.argv) > 2 else "preview-final.png"
HTML = "09-final.html"
CONFIG = "parity.json"

USAGE = (
    "用法：python parity-check.py [参考图] [成品图] [--html 页面] [--config 配置]\n"
    "  默认：ref.jpg  preview-final.png  --html 09-final.html  --config parity.json\n"
    "  退出码：0 = 全 PASS；1 = 有项 FAIL；2 = 无法执行（缺图 / 缺配置）\n"
)

for flag, attr in (("--html", "HTML"), ("--config", "CONFIG")):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 >= len(sys.argv):
            sys.stderr.write("错误：%s 后面缺少参数值\n\n%s" % (flag, USAGE))
            sys.exit(2)
        val = sys.argv[i + 1]
        if attr == "HTML":
            HTML = val
        else:
            CONFIG = val

DEFAULTS = {
    "regions": [],
    "global": {"lumTol": 22.0, "overMax": 1.5, "deadMax": 2.0, "curveMin": 12},
    "curveKeys": ["quadraticCurveTo", "bezierCurveTo", "absarc", "LatheGeometry",
                  "TubeGeometry", "TorusGeometry", "ExtrudeGeometry"],
}

# predicate 会被 eval，白名单只放三通道表达式的必需字符
PRED_CHARS = set("rgb0123456789. ><=*+-()&|!")


def load_config(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)
    for k, v in DEFAULTS["global"].items():
        cfg["global"].setdefault(k, v)
    return cfg


def compile_predicate(expr):
    """把 JS 风格的 && / || / ! 转成 Python 后编译。
    配置里写成 JS 风格，是为了让前端代码和门禁配置能共用同一套谓词写法。"""
    bad = set(expr) - PRED_CHARS
    if bad:
        raise ValueError("predicate 含非法字符 %r: %s" % ("".join(sorted(bad)), expr))
    py = expr.replace("&&", " and ").replace("||", " or ")
    py = re.sub(r"!(?!=)", " not ", py)          # 单个 ! 才是 not，!= 保留
    # 不用 bool() 包装：比较链本身就返回布尔值，也免得 __builtins__ 被清空后找不到 bool
    return eval("lambda r, g, b: (%s)" % py, {"__builtins__": {}})


def load(path):
    if not os.path.exists(path):
        sys.stderr.write("错误：找不到图片 %s\n\n%s" % (path, USAGE))
        sys.exit(2)
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:                      # 损坏文件 / 不支持的格式
        sys.stderr.write("错误：无法读取图片 %s（%s）\n" % (path, e))
        sys.exit(2)


def luminance_stats(im):
    px = list(im.getdata())
    lum = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px]
    n = len(lum)
    return {
        "mean": statistics.mean(lum),
        "over": sum(1 for v in lum if v > 250) / n * 100,
        "dead": sum(1 for v in lum if v < 8) / n * 100,
    }


def pixel_fraction(im, pred, box):
    w, h = im.size
    crop = im.crop((int(box[0] * w), int(box[1] * h),
                    int(box[2] * w), int(box[3] * h)))
    px = list(crop.getdata())
    if not px:
        return 0.0
    return sum(1 for r, g, b in px if pred(r, g, b)) / len(px) * 100


def curve_geometry_count(path, keys):
    try:
        s = open(path, encoding="utf-8").read()
    except OSError:
        return -1
    return sum(s.count(k) for k in keys)


def main():
    cfg = load_config(CONFIG)
    ref = load(REF)
    out = load(OUT)          # 不再按固定像素裁切：截图尺寸由调用方保证一致

    rows = []
    gs = (cfg or DEFAULTS)["global"]
    keys = (cfg or DEFAULTS)["curveKeys"]

    rs, os_ = luminance_stats(ref), luminance_stats(out)
    rows.append(("整体平均亮度", "%.1f" % rs["mean"], "%.1f" % os_["mean"],
                 abs(os_["mean"] - rs["mean"]) <= gs["lumTol"], "±%.0f" % gs["lumTol"]))
    rows.append(("过曝像素 >250", "%.2f%%" % rs["over"], "%.2f%%" % os_["over"],
                 os_["over"] <= gs["overMax"], "≤%s%%" % gs["overMax"]))
    rows.append(("死黑像素 <8", "%.2f%%" % rs["dead"], "%.2f%%" % os_["dead"],
                 os_["dead"] <= gs["deadMax"], "≤%s%%" % gs["deadMax"]))

    # —— 语义区域（G3）：配置驱动，不再写死场景语义 ——
    g3_ran = 0
    if cfg and cfg["regions"]:
        for region in cfg["regions"]:
            for feat in region["features"]:
                pred = compile_predicate(feat["predicate"])
                a = pixel_fraction(ref, pred, region["box"])
                b = pixel_fraction(out, pred, region["box"])
                tol = float(feat.get("tol", 9.0))
                rows.append(("%s %s" % (region["name"], feat["name"]),
                             "%.1f%%" % a, "%.1f%%" % b, abs(b - a) <= tol, "±%.0fpt" % tol))
                g3_ran += 1

    curves = curve_geometry_count(HTML, keys)
    rows.append(("曲线几何构造次数", "-", str(curves),
                 curves >= gs["curveMin"], "≥%s" % gs["curveMin"]))

    print("REF = %s   OUT = %s   HTML = %s   CFG = %s" % (REF, OUT, HTML, CONFIG))
    print("%-26s %10s %10s %6s  %s" % ("指标", "参考图", "成品", "判定", "阈值"))
    print("-" * 72)
    ok = True
    for name, a, b, passed, tol in rows:
        ok &= passed
        print("%-26s %10s %10s %6s  %s" % (name, a, b, "PASS" if passed else "FAIL", tol))
    print("-" * 72)

    if not cfg:
        print("警告：未找到 %s，G3（语义区域占比）未执行 —— 只跑了全局项。" % CONFIG)
        print("     通用阈值不能代替场景语义，请按 Stage 0 的语义色板补配置后重跑。")
        print("结论：INCOMPLETE —— G3 未执行，不能宣告视觉对等通过")
        return 2
    if g3_ran == 0:
        print("警告：%s 里没有 regions 或 features，G3 未执行。" % CONFIG)
        print("结论：INCOMPLETE —— G3 未执行，不能宣告视觉对等通过")
        return 2

    print("结论：%s" % ("PASS —— 视觉对等门禁通过" if ok else "FAIL —— 存在未达标项"))
    print()
    print("说明：本表只判「内容与色调」是否对等，不替代逐顶点投影的构图占比门禁，")
    print("      也不替代结构六查。三张表必须同时通过。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
