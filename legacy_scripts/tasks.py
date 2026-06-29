import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any

def parse_deadline_from_content(content: str) -> str:
    """从任务内容中提取截止时间"""
    match = re.search(r'截止时间[：:]\s*(\d{4}-\d{2}-\d{2})', content)
    return match.group(1) if match else ""

def parse_responsible_from_content(content: str) -> str:
    """从任务内容中提取负责人"""
    match = re.search(r'负责人[：:]\s*([^，,]+)', content)
    return match.group(1).strip() if match else ""

def generate_tasks_from_json(json_folder: str, output_file: str = "./tasks.json", 
                            target_meetings: List[str] = None):
    """
    从 JSON 文件夹生成 tasks.json
    
    参数:
        json_folder: JSON 文件所在文件夹
        output_file: 输出文件路径
        target_meetings: 指定要处理的会议ID列表，如 ["M0101", "M0102"]，不指定则处理全部
    """
    tasks = {}
    
    # 获取要处理的文件
    if target_meetings:
        json_files = [f"{mid}.json" for mid in target_meetings]
    else:
        json_files = [f for f in os.listdir(json_folder) if f.endswith(".json")]
    
    print(f" 扫描文件夹: {json_folder}")
    print(f" 找到 {len(json_files)} 个 JSON 文件")
    
    for json_file in json_files:
        meet_id = json_file.replace(".json", "")
        filepath = os.path.join(json_folder, json_file)
        
        if not os.path.exists(filepath):
            print(f" 跳过: {filepath} 不存在")
            continue
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 获取会议主题
        meeting_topic = data.get("会议主题", "")
        
        # 获取会议时间（如果有）
        meeting_date = data.get("会议时间", "")
        
        # 获取分工安排
        arrangements = data.get("分工安排", [])
        
        if not arrangements:
            print(f"    {meet_id}: 没有分工安排，跳过")
            continue
        
        # 初始化会议任务结构
        tasks[meet_id] = {
            "会议主题": meeting_topic,
            "会议时间": meeting_date,
            "tasks": []
        }
        
        for idx, task_content in enumerate(arrangements):
            # 提取负责人和截止时间
            responsible = parse_responsible_from_content(task_content)
            deadline = parse_deadline_from_content(task_content)
            
            # 判断任务状态（根据截止时间和当前日期）
            status = "pending"
            completed_at = None
            
            if deadline:
                try:
                    deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
                    today = datetime.now().date()
                    
                    if deadline_date < today:
                        status = "overdue"  # 逾期
                    elif deadline_date == today:
                        status = "due_today"  # 今日到期
                    else:
                        status = "pending"  # 待处理
                except ValueError:
                    status = "pending"
            
            tasks[meet_id]["tasks"].append({
                "id": f"{meet_id}_task_{idx + 1}",
                "content": task_content,
                "responsible": responsible,
                "deadline": deadline,
                "status": status,
                "completed_at": completed_at,
                "notes": ""
            })
        
        print(f"    {meet_id}: 提取 {len(arrangements)} 个任务")
    
    # 保存到文件
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    
    # 打印统计
    total_tasks = sum(len(meeting["tasks"]) for meeting in tasks.values())
    print(f"\n{'='*50}")
    print(f" 生成完成!")
    print(f"   处理会议数: {len(tasks)}")
    print(f"   总任务数: {total_tasks}")
    print(f"   输出文件: {output_file}")
    print(f"{'='*50}")
    
    return tasks




if __name__ == "__main__":
    # 指定要处理的会议ID列表
    target_meetings = ["M0101", "M0102", "M0103", "M0104", "M0105", "M0106"]
    
    # 生成 tasks.json
    tasks = generate_tasks_from_json(
        json_folder="./36_json",  
        output_file="./tasks.json",
        target_meetings=target_meetings
    )
   