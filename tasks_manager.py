import json
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

class TaskManager:
    def __init__(self, task_file="./tasks.json", json_folder="./36_json"):
        self.task_file = task_file
        self.json_folder = json_folder
        self.tasks = self.load_tasks()
    
    def load_tasks(self) -> Dict:
        """加载任务数据"""
        if os.path.exists(self.task_file):
            with open(self.task_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def save_tasks(self):
        """保存任务数据"""
        with open(self.task_file, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)
    
    def parse_task_content(self, content: str) -> Dict:
        """解析分工安排字符串，提取负责人和截止时间"""
        result = {"responsible": "", "deadline": "", "description": content}
        
        import re
        resp_match = re.search(r'负责人[：:]\s*([^，,]+)', content)
        if resp_match:
            result["responsible"] = resp_match.group(1).strip()
        
        deadline_match = re.search(r'截止时间[：:]\s*(\d{4}-\d{2}-\d{2})', content)
        if deadline_match:
            result["deadline"] = deadline_match.group(1)
        
        return result
    
    def sync_from_json(self, meet_ids: list = None):
        """从 JSON 文件夹同步任务"""
        if meet_ids:
            json_files = [f"{mid}.json" for mid in meet_ids if os.path.exists(os.path.join(self.json_folder, f"{mid}.json"))]
            print(f" 只同步指定的 {len(json_files)} 个会议: {meet_ids}")
        else:
            json_files = [f for f in os.listdir(self.json_folder) if f.endswith(".json")]
            print(f" 同步全部 {len(json_files)} 个会议")
        
        for json_file in json_files:
            meet_id = json_file.replace(".json", "")
            filepath = os.path.join(self.json_folder, json_file)
            
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            arrangements = data.get("分工安排", [])
            
            if meet_id not in self.tasks:
                self.tasks[meet_id] = {
                    "会议主题": data.get("会议主题", ""),
                    "会议时间": data.get("会议时间", ""), 
                    "tasks": []
                }
            
            existing_tasks = {t["content"]: t for t in self.tasks[meet_id]["tasks"]}
            
            for task_content in arrangements:
                if task_content not in existing_tasks:
                    parsed = self.parse_task_content(task_content)
                    self.tasks[meet_id]["tasks"].append({
                        "id": f"{meet_id}_task_{len(self.tasks[meet_id]['tasks'])}",
                        "content": task_content,
                        "responsible": parsed["responsible"],
                        "deadline": parsed["deadline"],
                        "status": "pending",
                        "completed_at": None,
                        "notes": ""
                    })
        
        self.save_tasks()
        print(f" 任务同步完成，共处理 {len(json_files)} 个会议")
    
    def update_task_status(self, task_id: str, status: str, notes: str = ""):
        """更新任务状态"""
        for meet_id, meeting in self.tasks.items():
            for task in meeting["tasks"]:
                if task["id"] == task_id:
                    task["status"] = status
                    if status == "completed":
                        task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    task["notes"] = notes
                    self.save_tasks()
                    return True
        return False
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务（用于选择要完成的任务）"""
        all_tasks = []
        for meet_id, meeting in self.tasks.items():
            for task in meeting["tasks"]:
                if task["status"] != "completed":  # 只显示未完成的任务
                    all_tasks.append({
                        "meet_id": meet_id,
                        "meeting_topic": meeting["会议主题"],
                        **task
                    })
        return all_tasks

    def complete_task_interactive(self):
        """交互式完成任务"""
        all_tasks = self.get_all_tasks()
    
        if not all_tasks:
            print("\n 所有任务都已完成！太棒了！")
            return
    
        print("\n📋 未完成的任务列表:")
        print("-" * 60)
        for idx, task in enumerate(all_tasks, 1):
            deadline_info = f" (截止: {task['deadline']})" if task['deadline'] else ""
            print(f"   {idx}. [{task['meet_id']}] {task['content'][:50]}...{deadline_info}")
            print(f"      负责人: {task['responsible']} | 状态: {task['status']}")
    
        print("-" * 60)
    
        while True:
            try:
                choice = input("\n请输入要标记完成的任务序号（输入 0 取消）: ").strip()
                if choice == '0':
                    print("已取消")
                    return
            
                idx = int(choice) - 1
                if 0 <= idx < len(all_tasks):
                    task = all_tasks[idx]
                    print(f"\n📌 确认完成任务: {task['content'][:60]}...")
                    confirm = input("确认标记为完成？(y/n): ").strip().lower()
                    if confirm == 'y':
                        self.update_task_status(task['id'], "completed", "用户手动标记完成")
                        print(f" 任务 [{task['meet_id']}] 已标记为完成！")
                    else:
                        print("已取消")
                    return
                else:
                    print(f" 无效的序号，请输入 1-{len(all_tasks)} 之间的数字")
            except ValueError:
                print(" 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n已取消")
                return
            
            
    def get_my_tasks(self, responsible: str) -> List[Dict]:
        """获取某人负责的所有任务"""
        my_tasks = []
        for meet_id, meeting in self.tasks.items():
            for task in meeting["tasks"]:
                if task["responsible"] == responsible:
                    my_tasks.append({
                        "meet_id": meet_id,
                        "meeting_topic": meeting["会议主题"],
                        **task
                    })
        return my_tasks
    
    def get_all_responsible_persons(self) -> List[str]:
        """获取所有负责人列表"""
        persons = set()
        for meet_id, meeting in self.tasks.items():
            for task in meeting["tasks"]:
                if task["responsible"]:
                    persons.add(task["responsible"])
        return sorted(list(persons))
    
    def get_overdue_tasks(self) -> List[Dict]:
        """获取逾期未完成的任务"""
        overdue = []
        today = date.today()
        
        for meet_id, meeting in self.tasks.items():
            for task in meeting["tasks"]:
                if task["status"] != "completed" and task["deadline"]:
                    try:
                        deadline_date = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
                        if deadline_date < today:
                            overdue.append({
                                "meet_id": meet_id,
                                "meeting_topic": meeting["会议主题"],
                                **task,
                                "overdue_days": (today - deadline_date).days
                            })
                    except ValueError:
                        continue
        
        # 按逾期天数排序（逾期最久的排在前面）
        overdue.sort(key=lambda x: x["overdue_days"], reverse=True)
        return overdue
    
    def get_upcoming_tasks(self, days: int = 3) -> List[Dict]:
        """
        获取即将到期的任务
        
        参数:
            days: 提前几天提醒（默认3天）
        
        返回:
            即将到期的任务列表（包含 deadline 和剩余天数）
        """
        upcoming = []
        today = date.today()
        end_date = today + timedelta(days=days)
        
        for meet_id, meeting in self.tasks.items():
            for task in meeting["tasks"]:
                # 只关心未完成且有截止日期的任务
                if task["status"] != "completed" and task["deadline"]:
                    try:
                        deadline_date = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
                        
                        # 判断是否在提醒范围内（今天之后、days天之内）
                        if today < deadline_date <= end_date:
                            days_left = (deadline_date - today).days
                            upcoming.append({
                                "meet_id": meet_id,
                                "meeting_topic": meeting["会议主题"],
                                **task,
                                "days_left": days_left
                            })
                    except ValueError:
                        continue
        
        # 按剩余天数排序（紧急的排在前面）
        upcoming.sort(key=lambda x: x["days_left"])
        return upcoming
    
    def get_today_tasks(self) -> List[Dict]:
        """获取今天到期的任务"""
        today = date.today()
        today_tasks = []
        
        for meet_id, meeting in self.tasks.items():
            for task in meeting["tasks"]:
                if task["status"] != "completed" and task["deadline"]:
                    try:
                        deadline_date = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
                        if deadline_date == today:
                            today_tasks.append({
                                "meet_id": meet_id,
                                "meeting_topic": meeting["会议主题"],
                                **task
                            })
                    except ValueError:
                        continue
        
        return today_tasks
    
    def print_reminders(self):
        """打印提醒信息（即将到期 + 今天到期 + 已逾期）"""
        print("\n" + "=" * 60)
        print("   ⏰ 任务提醒")
        print("=" * 60)
        
        # 1. 逾期任务
        overdue = self.get_overdue_tasks()
        if overdue:
            print(f"\n❌ 逾期未完成任务 ({len(overdue)} 项):")
            for task in overdue:
                content_preview = task['content'][:60] + "..." if len(task['content']) > 60 else task['content']
                print(f"   - [{task['meet_id']}] {content_preview}")
                print(f"     逾期 {task['overdue_days']} 天 | 负责人: {task['responsible']} | 截止: {task['deadline']}")
        
        # 2. 今天到期
        today_tasks = self.get_today_tasks()
        if today_tasks:
            print(f"\n🔴 今日到期 ({len(today_tasks)} 项):")
            for task in today_tasks:
                content_preview = task['content'][:60] + "..." if len(task['content']) > 60 else task['content']
                print(f"   - [{task['meet_id']}] {content_preview}")
                print(f"     负责人: {task['responsible']} | 截止: {task['deadline']}")
        
        # 3. 即将到期
        upcoming = self.get_upcoming_tasks(days=3)
        if upcoming:
            print(f"\n🟡 3天内到期 ({len(upcoming)} 项):")
            for task in upcoming:
                content_preview = task['content'][:60] + "..." if len(task['content']) > 60 else task['content']
                print(f"   - [{task['meet_id']}] {content_preview}")
                print(f"     剩余 {task['days_left']} 天 | 负责人: {task['responsible']} | 截止: {task['deadline']}")
        
        if not overdue and not today_tasks and not upcoming:
            print("\n 太棒了！没有即将到期的任务。")
        
        print("\n" + "=" * 60)
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total = 0
        completed = 0
        pending = 0
        in_progress = 0
        overdue = 0
        
        for meet_id, meeting in self.tasks.items():
            for task in meeting["tasks"]:
                total += 1
                if task["status"] == "completed":
                    completed += 1
                elif task["status"] == "in_progress":
                    in_progress += 1
                else:
                    pending += 1
        
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "in_progress": in_progress,
            "completion_rate": round(completed/total*100, 1) if total > 0 else 0,
            "overdue": len(self.get_overdue_tasks())  
        }
    
    def get_meetings_by_date(self) -> List[Dict]:
        """按会议时间排序所有会议"""
        meetings = []
        for meet_id, meeting in self.tasks.items():
            meeting_date = meeting.get("会议时间", "")
            meetings.append({
                "meet_id": meet_id,
                "会议主题": meeting["会议主题"],
                "会议时间": meeting_date,
                "task_count": len(meeting["tasks"]),
                "completed_count": sum(1 for t in meeting["tasks"] if t["status"] == "completed")
            })
        # 按会议时间排序（越早的越靠前）
        meetings.sort(key=lambda x: x["会议时间"])
        return meetings
    
    def print_person_tasks(self, person: str):
        """打印某人的任务详情"""
        tasks = self.get_my_tasks(person)
        
        if not tasks:
            print(f"\n 没有找到 {person} 负责的任务")
            return
        
        # 分类
        pending_tasks = [t for t in tasks if t['status'] == 'pending']
        in_progress_tasks = [t for t in tasks if t['status'] == 'in_progress']
        completed_tasks = [t for t in tasks if t['status'] == 'completed']
        
        print(f"\n{'='*60}")
        print(f"📋 {person} 负责的任务 ({len(tasks)} 项)")
        print(f"{'='*60}")
        
        if in_progress_tasks:
            print(f"\n🔄 进行中 ({len(in_progress_tasks)} 项):")
            for t in in_progress_tasks:
                deadline = f" (截止: {t['deadline']})" if t['deadline'] else ""
                content_preview = t['content'][:70] + "..." if len(t['content']) > 70 else t['content']
                print(f"   - [{t['meet_id']}] {content_preview}{deadline}")
        
        if pending_tasks:
            print(f"\n⏳ 待处理 ({len(pending_tasks)} 项):")
            for t in pending_tasks:
                deadline = f" (截止: {t['deadline']})" if t['deadline'] else ""
                content_preview = t['content'][:70] + "..." if len(t['content']) > 70 else t['content']
                print(f"   - [{t['meet_id']}] {content_preview}{deadline}")
        
        if completed_tasks:
            print(f"\n✅ 已完成 ({len(completed_tasks)} 项):")
            for t in completed_tasks[:10]:
                content_preview = t['content'][:70] + "..." if len(t['content']) > 70 else t['content']
                print(f"   - [{t['meet_id']}] {content_preview}")
            if len(completed_tasks) > 10:
                print(f"   ... 还有 {len(completed_tasks) - 10} 项已完成")
        
        print(f"\n{'='*60}")


# ===================== 交互式命令行 =====================
def interactive_mode():
    """交互式模式"""
    print("\n" + "=" * 60)
    print("   📋 任务管理助手")
    print("=" * 60)
    
    # 初始化
    tm = TaskManager(json_folder="./36_json")
    
    # 同步指定的6个会议
    target_meetings = ["M0101", "M0102", "M0103", "M0104", "M0105", "M0106"]
    tm.sync_from_json(meet_ids=target_meetings)
    
    # 显示统计
    stats = tm.get_statistics()
    print(f"\n📊 总体统计:")
    print(f"   总任务数: {stats['total']}")
    print(f"   ✅ 已完成: {stats['completed']}")
    print(f"   🔄 进行中: {stats['in_progress']}")
    print(f"   ⏳ 待处理: {stats['pending']}")
    print(f"   📈 完成率: {stats['completion_rate']}%")
    
    # 显示所有负责人
    persons = tm.get_all_responsible_persons()
    print(f"\n👥 当前有任务的负责人: {', '.join(persons)}")
    
    print("\n" + "-" * 60)
    print("命令说明:")
    print("   - 输入姓名查看该负责人的任务 (如: A, B, C, D)")
    print("   - 输入 'all' 查看所有人的任务")
    print("   - 输入 'stats' 查看总体统计")
    print("   - 输入 'complete' 标记任务为完成")
    print("   - 输入 'reminder' 查看任务提醒（逾期+今天+即将到期）")
    print("   - 输入 'overdue' 查看逾期任务")
    print("   - 输入 'timeline' 查看按时间排序的会议列表")
    print("   - 输入 'q' 退出")
    print("-" * 60)
    
    while True:
        try:
            cmd = input("\n🤔 请输入命令或负责人姓名: ").strip()
            
            if cmd.lower() == 'q':
                print("\n👋 再见！")
                break
            
            elif cmd.lower() == 'stats':
                stats = tm.get_statistics()
                print(f"\n📊 总体统计:")
                print(f"   总任务数: {stats['total']}")
                print(f"   ✅ 已完成: {stats['completed']}")
                print(f"   🔄 进行中: {stats['in_progress']}")
                print(f"   ⏳ 待处理: {stats['pending']}")
                print(f"   📈 完成率: {stats['completion_rate']}%")
                
            elif cmd.lower() == 'complete':
                tm.complete_task_interactive()
            
            elif cmd.lower() == 'reminder':
                tm.print_reminders()
            
            elif cmd.lower() == 'overdue':
                overdue = tm.get_overdue_tasks()
                if overdue:
                    print(f"\n❌ 逾期未完成任务 ({len(overdue)} 项):")
                    for task in overdue:
                        content_preview = task['content'][:60] + "..." if len(task['content']) > 60 else task['content']
                        print(f"   - [{task['meet_id']}] {content_preview}")
                        print(f"     逾期 {task['overdue_days']} 天 | 负责人: {task['responsible']} | 截止: {task['deadline']}")
                else:
                    print("\n 没有逾期未完成的任务！")
            
            elif cmd.lower() == 'timeline':
                meetings = tm.get_meetings_by_date()
                if meetings:
                    print("\n📅 会议时间线:")
                    print("-" * 60)
                    for m in meetings:
                        date_str = m["会议时间"] if m["会议时间"] else "时间未知"
                        print(f"   {date_str} | {m['meet_id']} | {m['会议主题'][:30]} | 任务: {m['task_count']} | 已完成: {m['completed_count']}")
                else:
                    print("\n 暂无会议数据")
            
            elif cmd.lower() == 'all':
                persons = tm.get_all_responsible_persons()
                for person in persons:
                    tm.print_person_tasks(person)
            
            else:
                # 输入的是姓名，查看该负责人的任务
                tm.print_person_tasks(cmd)
                
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f" 出错: {e}")
            
            
# ===================== 主函数 =====================
if __name__ == "__main__":
    interactive_mode()