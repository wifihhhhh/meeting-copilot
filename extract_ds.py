import os
import re
import json
import time
import requests
from typing import List, Optional

# ===================== 【 API KEY】 =====================
DEEPSEEK_API_KEY = "sk-97cbf750d9bc4cd1bdf6c13bf31b2726"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# ===================== 配置 =====================
INPUT_FOLDER = "./36"
OUTPUT_FOLDER = "./36_json"
MODEL_NAME = "deepseek-chat"

# ===================== 实验日志配置 =====================
LOG_FILE = "./36_experiment_log.txt"

# ===================== 请求头 =====================
HEADERS = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}

# ===================== 辅助函数：从文本中提取参会人员 =====================
def extract_participants_from_text(text: str) -> List[str]:
    """
    从文本中提取所有发言人标识
    匹配 [xxx] 格式（在行首或行中），例如 [no.1]、[主持人]、[张三]
    """
    pattern = r'\[([^\]]+)\]'
    participants = set()
    
    for line in text.split('\n'):
        matches = re.findall(pattern, line)
        for match in matches:
            if match and not match.isdigit() and len(match) < 30:
                participants.add(match)
    
    if not participants:
        pattern2 = r'^\[([^\]]+)\]'
        for line in text.split('\n'):
            line = line.strip()
            match = re.match(pattern2, line)
            if match:
                participants.add(match.group(1))
    
    return sorted(list(participants))


# ===================== 辅助函数：从文本中提取会议时间 =====================
def extract_meeting_time(text: str) -> str:
    """
    从文本中提取会议日期/时间。
    支持多种格式：
      - 会议日期: 2027 年 1 月 05 日
      - 会议日期: 2027 年 01 月 25 日
      - 会议时间：2024-03-15
      - 日期: 2024年3月15日
      - 2024/03/15
      - 2024.03.15
    返回标准化格式 YYYY-MM-DD，若无法提取则返回空字符串。
    """
    # 模式1: 会议日期: YYYY 年 M 月 D 日（支持前导零）
    pattern1 = r'\s*会议日期[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?'
    match = re.search(pattern1, text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    
    # 模式2: 会议日期/时间: YYYY-MM-DD 或 YYYY-M-D
    pattern2 = r'(?:会议日期|会议时间|日期|时间)[：:]\s*(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})'
    match = re.search(pattern2, text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    
    # 模式3: 纯数字格式 YYYY-MM-DD / YYYY/MM.DD / YYYY.MM.DD
    pattern3 = r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})'
    # 优先匹配文本开头附近的日期（避免匹配到正文中的无关数字）
    lines = text.split('\n')[:10]  # 只看前10行
    for line in lines:
        match = re.search(pattern3, line)
        if match:
            year, month, day = match.groups()
            # 简单校验：年份在2000-2100之间，月份1-12，日期1-31
            if 2000 <= int(year) <= 2100 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                return f"{year}-{int(month):02d}-{int(day):02d}"
    
    # 模式4: YYYY年M月D日（中文格式，无日期标记）
    pattern4 = r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日'
    lines = text.split('\n')[:10]
    for line in lines:
        match = re.search(pattern4, line)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
    
    return ""


# ===================== 强约束Prompt =====================
def get_system_prompt(participants: List[str], meeting_time: str = "") -> str:
    participants_json = json.dumps(participants, ensure_ascii=False)
    time_hint = f"\n【已知会议时间】\n{meeting_time}" if meeting_time else ""
    
    return f"""你是专业会议信息抽取专家。只输出合法JSON，禁止任何多余文字。

【已知参会人员】
{participants_json}{time_hint}

【输出格式】
{{
  "会议ID": "字符串",
  "会议主题": "字符串",
  "会议时间": "YYYY-MM-DD 格式，或空字符串",
  "参会人员": {participants_json},
  "核心讨论议题": ["议题1", "议题2"],
  "达成共识/确定方案": ["方案1", "方案2"],
  "待解决问题/遗留事项": ["事项1", "事项2"],
  "分工安排": ["负责人：XXX，任务：XXX"],
  "预算/费用相关": "费用描述",
  "风险与注意事项": ["风险1", "风险2"],
  "会议摘要": "一段话总结"
}}

无内容填空字符串或空数组。会议时间必须严格使用 YYYY-MM-DD 格式，若文本中无明确日期则填空字符串。"""


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def write_log(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def clean_text(text):
    """清洗文本，只去除特殊标记，保留换行"""
    text = re.sub(r"\[no\.\d+\]\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def parse_json_output(text):
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def llm_extract(meet_id, content, max_retries=3):
    # 提取参会人员（使用原始文本）
    participants = extract_participants_from_text(content)
    
    # 提取会议时间
    meeting_time = extract_meeting_time(content)
    
    # 清洗内容用于 LLM
    clean_content = clean_text(content)
    
    SYSTEM_PROMPT = get_system_prompt(participants, meeting_time)
    
    user_prompt = f"会议ID：{meet_id}\n会议内容：\n{clean_content}"
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 2048
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=HEADERS,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                res_text = result["choices"][0]["message"]["content"].strip()
                json_data = parse_json_output(res_text)
                
                if json_data:
                    json_data["会议ID"] = meet_id
                    
                    default_fields = {
                        "会议主题": "",
                        "会议时间": meeting_time,  
                        "参会人员": participants,
                        "核心讨论议题": [],
                        "达成共识/确定方案": [],
                        "待解决问题/遗留事项": [],
                        "分工安排": [],
                        "预算/费用相关": "",
                        "风险与注意事项": [],
                        "会议摘要": ""
                    }
                    for key, default_value in default_fields.items():
                        if key not in json_data:
                            json_data[key] = default_value
                        elif key == "参会人员":
                            json_data["参会人员"] = participants
                        elif key == "会议时间" and not json_data.get("会议时间"):
                            # 如果LLM没提取到时间，但正则提取到了，用正则的结果
                            json_data["会议时间"] = meeting_time
                    
                    return json_data
                else:
                    print(f" {meet_id} JSON解析失败 (尝试 {attempt+1}/{max_retries})")
                    
            elif response.status_code == 429:
                wait_time = (attempt + 1) * 2
                print(f"{meet_id} 限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                print(f"{meet_id} HTTP {response.status_code}")
                
        except Exception as e:
            print(f"{meet_id} 异常：{e}")
        
        if attempt < max_retries - 1:
            time.sleep((attempt + 1) * 2)
    
    return None


# ===================== 批量处理 =====================
def main():
    start_time = time.time()
    write_log("=" * 60)
    write_log("开始新一轮会议信息抽取任务")
    write_log(f"输入目录：{INPUT_FOLDER}")
    write_log(f"输出目录：{OUTPUT_FOLDER}")
    write_log(f"使用模型：{MODEL_NAME}")
    
    ensure_dir(OUTPUT_FOLDER)
    
    if not os.path.exists(INPUT_FOLDER):
        print(f"输入目录 {INPUT_FOLDER} 不存在！")
        return
    
    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith(".txt")]
    total_files = len(files)
    
    print(f"\n{'='*50}")
    print(f"输入目录：{INPUT_FOLDER}")
    print(f"输出目录：{OUTPUT_FOLDER}")
    print(f"共发现 {total_files} 个会议文件")
    print(f"使用模型：DeepSeek API ({MODEL_NAME})")
    print(f"{'='*50}\n")
    print("正在处理，请稍候...\n")
    
    success_count = 0
    fail_count = 0
    failures = []
    
    for idx, filename in enumerate(files, 1):
        meet_id = filename.split("_")[0]
        filepath = os.path.join(INPUT_FOLDER, filename)
        
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        
        result = llm_extract(meet_id, text)
        
        if result:
            out_path = os.path.join(OUTPUT_FOLDER, f"{meet_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            success_count += 1
        else:
            fail_count += 1
            failures.append(meet_id)
        
        time.sleep(0.5)
    
    end_time = time.time()
    total_cost = round(end_time - start_time, 2)
    
    write_log(f"文件总数：{success_count + fail_count}")
    write_log(f"处理成功：{success_count} 个，处理失败：{fail_count} 个")
    if success_count + fail_count > 0:
        write_log(f"任务成功率：{success_count/(success_count+fail_count)*100:.1f}%")
    write_log(f"本轮总运行用时：{total_cost} 秒")
    if failures:
        write_log(f"失败文件ID列表：{', '.join(failures)}")
    write_log("本轮抽取任务结束\n")
    
    print(f"\n{'='*50}")
    print(f"处理完成汇总")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    if success_count + fail_count > 0:
        print(f"成功率: {success_count/(success_count+fail_count)*100:.1f}%")
    print(f"总用时: {total_cost} 秒")
    
    if failures:
        print(f"\n 失败文件列表: {', '.join(failures)}")
    print(f"{'='*50}\n")
    
    print("LLM 结构化抽取全部完成！")

if __name__ == "__main__":
    main()