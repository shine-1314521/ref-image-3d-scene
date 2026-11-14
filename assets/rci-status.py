# -*- coding: utf-8 -*-
"""
RCI 状态检查（ref-image-3d-scene / Stage 9 硬门禁的机械入口）

为什么需要它：RCI 表「交付时不得有 TODO」这条规则写在文档里，
但没有任何东西会去读那张表。实测结果就是——18 条 RCI 全程停在 TODO，
交付照常发生，规则形同虚设。规则必须有可执行入口（R15）。

用法：
    python rci-status.py 00-spec.md
    python rci-status.py 00-spec.md --quiet     # 只输出汇总行

退出码：0 = 无 TODO 无 FAIL（WAIVED 需人工确认理由）；
        1 = 存在 TODO 或 FAIL；2 = 找不到任何 RCI 行（表没写或格式变了）。
"""
import re
import sys

ID_RE = re.compile(r"^(R\d+|CR-?\d+)$", re.I)
STATUSES = ("PASS", "FAIL", "WAIVED", "TODO", "BLOCKED")


def parse(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s.startswith("|"):
                continue
            parts = [p.strip() for p in s.strip("|").split("|")]
            if len(parts) < 2:
                continue
            if not ID_RE.match(parts[0]):
                continue
            status = None
            for cell in reversed(parts[1:]):
                head = cell.upper().split("（")[0].split("(")[0].strip()
                if head in STATUSES:
                    status = head
                    break
            rows.append((parts[0], status or "UNKNOWN", parts[2] if len(parts) > 2 else "", lineno))
    return rows


def main():
    if len(sys.argv) < 2:
        print("用法: python rci-status.py 00-spec.md [--quiet]")
        return 2
    path = sys.argv[1]
    quiet = "--quiet" in sys.argv

    rows = parse(path)
    if not rows:
        print("FAIL —— %s 里没有任何 RCI 行（形如 | R01 | G 构图 | … |）" % path)
        print("      表没写，或列格式变了；两种都不算通过。")
        return 2

    buckets = {}
    for rid, status, name, ln in rows:
        buckets.setdefault(status, []).append((rid, name, ln))

    total = len(rows)
    print("RCI 表：%s   共 %d 条" % (path, total))
    print("  " + "  ".join("%s %d" % (k, len(v)) for k, v in sorted(buckets.items())))

    for key in ("FAIL", "TODO", "BLOCKED", "UNKNOWN"):
        if key in buckets:
            print("%s：" % key)
            for rid, name, ln in buckets[key]:
                print("    %-6s %s  (line %d)" % (rid, name[:44], ln))

    if "WAIVED" in buckets and not quiet:
        print("WAIVED（需在交付话术里逐条给理由与代价）：")
        for rid, name, _ in buckets["WAIVED"]:
            print("    %-6s %s" % (rid, name[:44]))

    bad = sum(len(buckets.get(k, [])) for k in ("FAIL", "TODO", "BLOCKED", "UNKNOWN"))
    if bad:
        print("结论：FAIL —— %d 条未收口（TODO/FAIL/BLOCKED），不得交付" % bad)
        return 1
    print("结论：PASS —— 无 TODO、无 FAIL%s" % (
        "；WAIVED %d 条须在话术里说明" % len(buckets["WAIVED"]) if "WAIVED" in buckets else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
