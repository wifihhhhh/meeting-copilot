import os
import re
import math

# ====================== 【路径】 ======================
STD_FOLDER = r"./10会议_人工标注"   # 人工标注文件夹
SYS_FOLDER = r"./10会议_txt"        # 系统结果文件夹
SIMILAR_THRESHOLD = 0.35           # 相似度阈值

# ====================== 关键词提取与相似度计算 ======================
def extract_keywords(text):
    """提取关键词：中文字符 + 数字"""
    if not text:
        return []
    chars = list(re.findall(r'[\u4e00-\u9fa5]', str(text)))
    numbers = re.findall(r'\d+', str(text))
    return chars + numbers


def keyword_coverage_sim(sys_text, std_text):
    """基于关键词覆盖率的相似度计算"""
    sys_kw = set(extract_keywords(sys_text))
    std_kw = set(extract_keywords(std_text))

    if not sys_kw or not std_kw:
        return 0.0

    intersection = sys_kw & std_kw
    coverage = len(intersection) / len(std_kw) if std_kw else 0
    union = sys_kw | std_kw
    jaccard = len(intersection) / len(union) if union else 0

    return coverage * 0.7 + jaccard * 0.3


# ====================== 解析文件（标准答案和系统结果格式相同） ======================
def parse_file(text):
    """解析会议文件，提取达成共识和待解决问题"""
    result = {"达成共识": [], "待解决问题": []}

    # 提取达成共识
    match = re.search(
        r'【达成共识/确定方案】\s*(.*?)(?=【待解决问题/遗留事项】|【分工安排】|【预算/费用相关】|【风险与注意事项】|【会议摘要】|={10,}|\Z)',
        text, re.DOTALL
    )
    if match:
        for line in match.group(1).strip().split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('•'):
                item = line[1:].strip()
                if item and len(item) > 3:
                    result["达成共识"].append(item)

    # 提取待解决问题
    match = re.search(
        r'【待解决问题/遗留事项】\s*(.*?)(?=【分工安排】|【预算/费用相关】|【风险与注意事项】|【会议摘要】|={10,}|\Z)',
        text, re.DOTALL
    )
    if match:
        for line in match.group(1).strip().split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('•'):
                item = line[1:].strip()
                if item and len(item) > 3:
                    result["待解决问题"].append(item)

    return result


# ====================== 语义匹配计算指标 ======================
def compute_metrics(standard_items, system_items):
    """计算TP/FP/FN/P/R/F1 - 贪心多对多匹配"""
    if not standard_items and not system_items:
        return {"TP": 0, "FP": 0, "FN": 0, "P": 1.0, "R": 1.0, "F1": 1.0}
    if not standard_items:
        return {"TP": 0, "FP": len(system_items), "FN": 0, "P": 0.0, "R": 1.0, "F1": 0.0}
    if not system_items:
        return {"TP": 0, "FP": 0, "FN": len(standard_items), "P": 1.0, "R": 0.0, "F1": 0.0}

    matched_std = set()
    matched_sys = set()
    matched_pairs = []

    # 构建相似度矩阵
    sim_matrix = []
    for i, sys_item in enumerate(system_items):
        for j, std_item in enumerate(standard_items):
            sim = keyword_coverage_sim(sys_item, std_item)
            sim_matrix.append((sim, i, j))

    # 按相似度降序排序，贪心匹配
    sim_matrix.sort(reverse=True)

    for sim, i, j in sim_matrix:
        if i in matched_sys or j in matched_std:
            continue
        if sim >= SIMILAR_THRESHOLD:
            matched_sys.add(i)
            matched_std.add(j)
            matched_pairs.append((system_items[i], standard_items[j], sim))

    TP = len(matched_pairs)
    FP = len(system_items) - len(matched_sys)
    FN = len(standard_items) - len(matched_std)
    P = TP / (TP + FP) if (TP + FP) > 0 else 0
    R = TP / (TP + FN) if (TP + FN) > 0 else 0
    F1 = 2 * P * R / (P + R) if (P + R) > 0 else 0

    return {
        "TP": TP, "FP": FP, "FN": FN,
        "P": round(P, 3), "R": round(R, 3), "F1": round(F1, 3),
        "matched_pairs": matched_pairs
    }


# ====================== 批量评估 ======================
def main():
    all_files = [f for f in os.listdir(STD_FOLDER) if f.endswith(".txt")]

    total = {
        "达成共识": {"TP": 0, "FP": 0, "FN": 0},
        "待解决问题": {"TP": 0, "FP": 0, "FN": 0}
    }

    print("=" * 70)
    print("会议纪要抽取结果评估（关键词覆盖率语义匹配）")
    print(f"标准文件夹: {STD_FOLDER}")
    print(f"系统文件夹: {SYS_FOLDER}")
    print(f"相似度阈值: {SIMILAR_THRESHOLD}")
    print("=" * 70)

    for fname in sorted(all_files):
        std_path = os.path.join(STD_FOLDER, fname)
        sys_path = os.path.join(SYS_FOLDER, fname)

        if not os.path.exists(sys_path):
            print(f"\n⚠️ 跳过 {fname}（系统结果不存在）")
            continue

        with open(std_path, "r", encoding="utf-8") as f:
            std_text = f.read()
        with open(sys_path, "r", encoding="utf-8") as f:
            sys_text = f.read()

        std = parse_file(std_text)
        sys = parse_file(sys_text)

        m1 = compute_metrics(std["达成共识"], sys["达成共识"])
        m2 = compute_metrics(std["待解决问题"], sys["待解决问题"])

        for k in ["TP", "FP", "FN"]:
            total["达成共识"][k] += m1[k]
            total["待解决问题"][k] += m2[k]

        print(f"\n📄 {fname}")
        print(f"  达成共识     | 标准{len(std['达成共识'])}条 系统{len(sys['达成共识'])}条 | TP={m1['TP']} FP={m1['FP']} FN={m1['FN']} | P={m1['P']} R={m1['R']} F1={m1['F1']}")
        print(f"  待解决问题   | 标准{len(std['待解决问题'])}条 系统{len(sys['待解决问题'])}条 | TP={m2['TP']} FP={m2['FP']} FN={m2['FN']} | P={m2['P']} R={m2['R']} F1={m2['F1']}")

        if m1['matched_pairs']:
            print(f"  达成共识匹配详情:")
            for sys_item, std_item, sim in m1['matched_pairs']:
                print(f"    [sim={sim:.2f}] 系统: {sys_item[:50]}... ↔ 标准: {std_item[:50]}...")

    # ====================== 最终汇总 ======================
    print("\n" + "=" * 70)
    print("📊 全部文件最终评估结果")
    print("=" * 70)

    for name, data in [("达成共识/确定方案", total["达成共识"]), ("待解决问题/遗留事项", total["待解决问题"])]:
        TP, FP, FN = data["TP"], data["FP"], data["FN"]
        P = TP / (TP + FP) if (TP + FP) > 0 else 0
        R = TP / (TP + FN) if (TP + FN) > 0 else 0
        F1 = 2 * P * R / (P + R) if (P + R) > 0 else 0

        print(f"\n【{name}】")
        print(f"  正确匹配(TP): {TP}")
        print(f"  错误提取(FP): {FP}")
        print(f"  遗漏未提(FN): {FN}")
        print(f"  精确率 P = {P:.3f}")
        print(f"  召回率 R = {R:.3f}")
        print(f"  F1 分数   = {F1:.3f}")

    total_tp = total["达成共识"]["TP"] + total["待解决问题"]["TP"]
    total_fp = total["达成共识"]["FP"] + total["待解决问题"]["FP"]
    total_fn = total["达成共识"]["FN"] + total["待解决问题"]["FN"]
    total_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    total_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    total_f1 = 2 * total_p * total_r / (total_p + total_r) if (total_p + total_r) > 0 else 0

    print(f"\n{'=' * 70}")
    print("【总体评估】")
    print(f"  总正确匹配(TP): {total_tp}")
    print(f"  总错误提取(FP): {total_fp}")
    print(f"  总遗漏未提(FN): {total_fn}")
    print(f"  总体精确率 P = {total_p:.3f}")
    print(f"  总体召回率 R = {total_r:.3f}")
    print(f"  总体F1分数   = {total_f1:.3f}")
    print("=" * 70)


if __name__ == "__main__":
    main()