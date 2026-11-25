# -*- coding: utf-8 -*-
"""多路评卷冻结与隔离校验：三路文件存在、哈希留痕、跨路引用/趋同检测。
退出码：0=PASS(冻结成功), 2=FAIL(串味/趋同，需重跑), 1=输入错误
"""
import argparse, json, os, sys, re, hashlib, datetime

OK, FAIL, ERR = 0, 2, 1
ROUTE_IDS = {"W1", "W2", "W3"}
# 跨路引用特征：出现另一路的 ID 或明确引用措辞
CROSS_PAT = re.compile(r"(如\s*W[123]\s*所说|参照\s*W[123]|W[123]\s*的结论|与\s*W[123]\s*一致)")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sentences(text):
    parts = re.split(r"[。！？!?\n；;]", text)
    return {p.strip() for p in parts if len(p.strip()) >= 12}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", required=True, help="W1=<path>,W2=<path>,W3=<path>")
    ap.add_argument("--out", required=True, help="冻结结果 JSON 输出路径")
    args = ap.parse_args()

    routes = {}
    for item in args.routes.split(","):
        if "=" not in item:
            print("ERROR: bad --routes format:", item)
            return ERR
        k, v = item.split("=", 1)
        routes[k.strip().upper()] = v.strip()
    if set(routes.keys()) != ROUTE_IDS:
        print("ERROR: 必须提供且仅提供 W1,W2,W3，当前=%s" % sorted(routes))
        return ERR

    errors = []
    texts = {}
    entries = []
    for rid in ("W1", "W2", "W3"):
        p = routes[rid]
        if not os.path.exists(p):
            errors.append("%s 文件不存在: %s" % (rid, p))
            continue
        txt = open(p, encoding="utf-8", errors="ignore").read()
        texts[rid] = txt
        entries.append({
            "id": rid,
            "path": os.path.abspath(p),
            "sha256": sha256(p),
            "bytes": os.path.getsize(p),
        })

    # 跨路引用检测
    for rid, txt in texts.items():
        for m in CROSS_PAT.finditer(txt):
            others = re.findall(r"W[123]", m.group(0))
            if any(o != rid for o in others):
                errors.append("%s 出现跨路引用: %s" % (rid, m.group(0)[:40]))

    # 趋同检测：独特长句两两重合率
    sets = {rid: sentences(txt) for rid, txt in texts.items()}
    overlaps = {}
    ids = list(sets.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if not sets[a] or not sets[b]:
                continue
            inter = len(sets[a] & sets[b])
            union = len(sets[a] | sets[b])
            rate = round(inter / union, 4) if union else 0.0
            overlaps["%s-%s" % (a, b)] = rate
            if rate >= 0.5:
                errors.append("%s 与 %s 独特表述重合率 %.2f，判伪独立需重跑" % (a, b, rate))

    status = "PASS" if not errors else "FAIL"
    result = {
        "schema_version": "1.0",
        "frozen_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "routes": entries,
        "unique_sentence_overlap": overlaps,
        "errors": errors,
        "rule": "仲裁者不得是W1/W2/W3任一路；冻结后哈希变化即串味重跑",
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("FREEZE=%s rates=%s out=%s" % (status, overlaps, args.out))
    for e in errors:
        print("  -", e)
    return OK if status == "PASS" else FAIL


if __name__ == "__main__":
    sys.exit(main())
