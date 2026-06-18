import os
import json
import glob
from typing import Dict, Any, List


class JsonToMinutesConverter:
    """JSON 会议纪要 → 可读 TXT 纪要"""
    
    def __init__(self, input_folder: str, output_folder: str):
        self.input_folder = input_folder
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
    
    def convert_all(self) -> Dict[str, Any]:
        """批量转换文件夹下所有 JSON 文件"""
        stats = {"total": 0, "success": 0, "failed": 0, "failed_files": []}
        
        json_files = glob.glob(os.path.join(self.input_folder, "*.json"))
        print(f"📁 发现 {len(json_files)} 个 JSON 文件\n")
        
        for json_path in sorted(json_files):
            filename = os.path.basename(json_path)
            meet_id = filename.replace(".json", "")
            stats["total"] += 1
            
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                txt_content = self.format_minutes(data)
                txt_path = os.path.join(self.output_folder, f"{meet_id}.txt")
                
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(txt_content)
                
                stats["success"] += 1
                
                
            except Exception as e:
                stats["failed"] += 1
                stats["failed_files"].append(filename)
                print(f"   ❌ {filename} 失败: {e}")
        
        return stats
    
    def format_minutes(self, data: Dict[str, Any]) -> str:
        """将 JSON 数据格式化为可读纪要文本"""
        lines = []
        
        # ========== 标题 ==========
        meet_id = data.get("会议ID", "未知")
        topic = data.get("会议主题", "")
        meet_time = data.get("会议时间", "")
        
        lines.append("=" * 60)
        lines.append(f"📋 会议纪要")
        lines.append("=" * 60)
        lines.append(f"会议编号：{meet_id}")
        if topic:
            lines.append(f"会议主题：{topic}")
        if meet_time:
            lines.append(f"会议时间：{meet_time}")
        lines.append("=" * 60)
        lines.append("")
        
        # ========== 参会人员 ==========
        participants = data.get("参会人员", [])
        if participants:
            lines.append("【参会人员】")
            lines.append(f"    {', '.join(participants)}")
            lines.append("")
        
        # ========== 核心讨论议题 ==========
        topics = data.get("核心讨论议题", [])
        if topics:
            lines.append("【核心讨论议题】")
            for i, item in enumerate(topics, 1):
                lines.append(f"    {i}. {item}")
            lines.append("")
        
        # ========== 达成共识/确定方案 ==========
        agreements = data.get("达成共识/确定方案", [])
        if agreements:
            lines.append("【达成共识 / 确定方案】")
            for i, item in enumerate(agreements, 1):
                lines.append(f"    {i}. {item}")
            lines.append("")
        
        # ========== 分工安排 ==========
        assignments = data.get("分工安排", [])
        if assignments:
            lines.append("【分工安排】")
            for i, item in enumerate(assignments, 1):
                lines.append(f"    {i}. {item}")
            lines.append("")
        
        # ========== 待解决问题/遗留事项 ==========
        pending = data.get("待解决问题/遗留事项", [])
        if pending:
            lines.append("【待解决问题 / 遗留事项】")
            for i, item in enumerate(pending, 1):
                lines.append(f"    {i}. {item}")
            lines.append("")
        
        # ========== 预算/费用相关 ==========
        budget = data.get("预算/费用相关", "")
        if budget:
            lines.append("【预算 / 费用相关】")
            lines.append(f"    {budget}")
            lines.append("")
        
        # ========== 风险与注意事项 ==========
        risks = data.get("风险与注意事项", [])
        if risks:
            lines.append("【风险与注意事项】")
            for i, item in enumerate(risks, 1):
                lines.append(f"    {i}. {item}")
            lines.append("")
        
        # ========== 会议摘要 ==========
        summary = data.get("会议摘要", "")
        if summary:
            lines.append("【会议摘要】")
            lines.append(f"    {summary}")
            lines.append("")
        
        # ========== 页脚 ==========
        lines.append("=" * 60)
        lines.append(f"— 纪要生成时间：{self._get_current_time()} —")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ===================== 主函数 =====================
def main():
    # ========== 配置 ==========
    INPUT_FOLDER = "./36_json"      # JSON 文件夹路径
    OUTPUT_FOLDER = "./36_txt"  # 输出 TXT 文件夹路径
    
    # ========== 执行转换 ==========
    converter = JsonToMinutesConverter(INPUT_FOLDER, OUTPUT_FOLDER)
    stats = converter.convert_all()
    
    # ========== 打印统计 ==========
    print(f"\n{'='*50}")
    print(" 转换完成")
    print(f"   总计: {stats['total']} 个")
    print(f"   成功: {stats['success']} 个")
    print(f"   失败: {stats['failed']} 个")
    if stats["failed_files"]:
        print(f"   失败文件: {', '.join(stats['failed_files'])}")
    print(f"{'='*50}")
    print(f"\n输出目录: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()