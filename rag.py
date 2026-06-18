import os
import json
import glob
import requests
from typing import List, Dict, Any, Optional

import chromadb
import ollama
import numpy as np


# ===================== 配置 =====================
class Config:
    CHROMA_PERSIST_DIR = "./chroma_db"
    JSON_FOLDER = "./36_json"
    
    OLLAMA_URL = "http://localhost:11434"
    LLM_MODEL = "qwen:7b"
    EMBEDDING_MODEL = "bge-m3"
    EMBEDDING_DIM = 1024
    
    TOP_K_RESULTS = 5          # 从向量库检索的候选数
    FALLBACK_TOP_N = 1         # 全部低于阈值时保留的最高相似度结果数
    COLLECTION_NAME = "36_storage"


# ===================== Embedding 工具 =====================
def get_embedding(text: str) -> List[float]:
    try:
        res = requests.post(
            f"{Config.OLLAMA_URL}/api/embeddings",
            json={"model": Config.EMBEDDING_MODEL, "prompt": text}
        )
        res.raise_for_status()
        embedding = res.json().get("embedding")
        print(f"DEBUG: embedding type={type(embedding)}, len={len(embedding) if isinstance(embedding, (list, tuple)) else 'N/A'}")
        if embedding and isinstance(embedding, list):
            return embedding
    except Exception as e:
        print(f" Embedding 失败: {e}")
    return [0.0] * Config.EMBEDDING_DIM


def normalize_embedding(embedding: List[float]) -> List[float]:
    """L2 归一化向量"""
    arr = np.array(embedding)
    norm = np.linalg.norm(arr)
    if norm > 0:
        return (arr / norm).tolist()
    return embedding


# ===================== 文本处理工具 =====================
class TextProcessor:
    @staticmethod
    def build_document_text(meeting_data: Dict[str, Any]) -> str:
        parts = []
        if meeting_data.get("会议ID"):
            parts.append(f"会议ID：{meeting_data['会议ID']}")
        if meeting_data.get("会议时间"):
            parts.append(f"会议时间：{meeting_data['会议时间']}")
        if meeting_data.get("会议主题"):
            parts.append(f"会议主题：{meeting_data['会议主题']}")
        if meeting_data.get("参会人员"):
            parts.append(f"参会人员：{', '.join(meeting_data['参会人员'])}")
        if meeting_data.get("核心讨论议题"):
            parts.append(f"核心讨论议题：{', '.join(meeting_data['核心讨论议题'])}")
        if meeting_data.get("达成共识/确定方案"):
            parts.append(f"达成共识：{', '.join(meeting_data['达成共识/确定方案'])}")
        if meeting_data.get("待解决问题/遗留事项"):
            parts.append(f"遗留问题：{', '.join(meeting_data['待解决问题/遗留事项'])}")
        if meeting_data.get("分工安排"):
            parts.append(f"分工安排：{', '.join(meeting_data['分工安排'])}")
        if meeting_data.get("预算/费用相关"):
            parts.append(f"预算费用：{meeting_data['预算/费用相关']}")
        if meeting_data.get("风险与注意事项"):
            parts.append(f"风险事项：{', '.join(meeting_data['风险与注意事项'])}")
        if meeting_data.get("会议摘要"):
            parts.append(f"会议摘要：{meeting_data['会议摘要']}")
        return "\n".join(parts)


# ===================== 向量库管理 =====================
class VectorStore:
    def __init__(self):
        os.makedirs(Config.CHROMA_PERSIST_DIR, exist_ok=True)
        self.client = chromadb.PersistentClient(path=Config.CHROMA_PERSIST_DIR)
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME
        )
        print(f" 向量库已连接，当前包含 {self.collection.count()} 条记录")
    
    def add_meeting(self, meeting_data: Dict[str, Any]) -> bool:
        meet_id = meeting_data.get("会议ID")
        if not meet_id:
            return False
        
        doc_text = TextProcessor.build_document_text(meeting_data)
        embedding = normalize_embedding(get_embedding(doc_text))
        
        metadata = {
            "meet_id": meet_id,
            "meeting_topic": meeting_data.get("会议主题", ""),
            "source_file": f"{meet_id}.json"
        }
        
        try:
            try:
                self.collection.delete(ids=[meet_id])
            except Exception:
                pass
            
            self.collection.add(
                ids=[meet_id],
                embeddings=[embedding],
                documents=[doc_text],
                metadatas=[metadata]
            )
            return True
        except Exception as e:
            print(f" {meet_id} 存入失败：{str(e)}")
            return False
    
    def search(self, query: str) -> Dict[str, Any]:
        """检索候选结果，返回 TOP_K_RESULTS 个候选供后续过滤"""
        query_embedding = normalize_embedding(get_embedding(query))
        print(f"DEBUG query_embedding: type={type(query_embedding)}, len={len(query_embedding)}, first5={query_embedding[:5]}")
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=Config.TOP_K_RESULTS  # 统一使用 Config 配置
            )
            print(f"DEBUG search results: ids={results.get('ids')}, distances={results.get('distances')}")
            return results
        except Exception as e:
            print(f" 检索失败：{str(e)}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    def get_stats(self) -> Dict[str, Any]:
        return {"total_meetings": self.collection.count(), "collection_name": Config.COLLECTION_NAME}
    
    def list_all_meetings(self) -> List[str]:
        try:
            results = self.collection.get()
            return results.get("ids", [])
        except Exception:
            return []
    
    def clear(self):
        try:
            self.client.delete_collection(Config.COLLECTION_NAME)
            self.collection = self.client.create_collection(name=Config.COLLECTION_NAME)
            print(" 向量库已清空")
        except Exception as e:
            print(f" 清空失败：{e}")


# ===================== RAG 问答系统 =====================
class RAGQuery:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.similarity_threshold = 0.30
    
    def build_prompt(self, query: str, context: str) -> str:
        return f"""根据以下会议记录，回答问题。只输出答案，不要解释。

会议记录：
{context}

问题：{query}

答案："""
    
    def format_context(self, search_results: Dict[str, Any]) -> str:
        context_parts = []
        documents = search_results.get("documents", [[]])[0]
        metadatas = search_results.get("metadatas", [[]])[0]
        distances = search_results.get("distances", [[]])[0]
        
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            similarity = 1 - dist if dist else 1.0
            meet_id = meta.get("meet_id", "未知") if meta else "未知"
            topic = meta.get("meeting_topic", "无主题") if meta else "无主题"
            
            context_parts.append(f"""
【会议 {i+1}】ID: {meet_id} | 主题: {topic} | 相关度: {similarity:.2%}
内容:
{doc}
""")
        
        return "\n".join(context_parts) if context_parts else "未找到相关会议记录。"
    
    def extract_keywords(self, query: str) -> str:
        """用 LLM 提取问题中的核心关键词"""
        prompt = f"""从以下问题中提取最核心的关键词（1-3个），用于检索相关会议。只输出关键词，用空格分隔。

问题：{query}

关键词："""
        
        try:
            response = ollama.chat(
                model=Config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0, "num_predict": 50}
            )
            keywords = response["message"]["content"].strip()
            print(f" 提取的关键词: {keywords}")
            return keywords
        except Exception as e:
            print(f" 关键词提取失败: {e}，使用原问题")
            return query
    
    def search_with_filter(self, query: str) -> Dict[str, Any]:
        """
        检索并过滤：
        1. 先检索 TOP_K_RESULTS 个候选
        2. 用相似度阈值过滤
        3. 全部低于阈值时，保留 FALLBACK_TOP_N 个最高相似度的
        """
        query_embedding = normalize_embedding(get_embedding(query))
        
        # 1. 检索候选池（统一使用 Config.TOP_K_RESULTS）
        results = self.vector_store.collection.query(
            query_embeddings=[query_embedding],
            n_results=Config.TOP_K_RESULTS
        )
        
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        if not ids:
            return results  # 空结果直接返回
        
        # 2. 计算所有相似度并排序
        similarities = [(1 - dist, i) for i, dist in enumerate(distances)]
        similarities.sort(reverse=True)  # 按相似度降序
        
        filtered_ids = []
        filtered_documents = []
        filtered_metadatas = []
        filtered_distances = []
        
        print(f"\n 检索结果过滤 (阈值: {self.similarity_threshold:.0%}, 候选池: {len(ids)} 个):")
        
        # 3. 按阈值过滤
        above_threshold = []
        below_threshold = []
        
        for sim, i in similarities:
            item_info = {
                "id": ids[i],
                "topic": metadatas[i].get("meeting_topic", "")[:30] if metadatas[i] else "",
                "sim": sim
            }
            if sim >= self.similarity_threshold:
                above_threshold.append(item_info)
                filtered_ids.append(ids[i])
                filtered_documents.append(documents[i])
                filtered_metadatas.append(metadatas[i])
                filtered_distances.append(distances[i])
                print(f"    保留: {ids[i]} | {item_info['topic']} | 相似度: {sim:.2%}")
            else:
                below_threshold.append(item_info)
                print(f"    过滤: {ids[i]} | {item_info['topic']} | 相似度: {sim:.2%}")
        
        # 4. 保底机制：如果全部低于阈值，保留 FALLBACK_TOP_N 个最高相似度的
        if len(filtered_ids) == 0 and len(ids) > 0:
            print(f"    全部低于阈值，强制保留前 {Config.FALLBACK_TOP_N} 个最高相似度结果:")
            for rank, (sim, i) in enumerate(similarities[:Config.FALLBACK_TOP_N], 1):
                filtered_ids.append(ids[i])
                filtered_documents.append(documents[i])
                filtered_metadatas.append(metadatas[i])
                filtered_distances.append(distances[i])
                print(f"      保底 #{rank}: {ids[i]} | 相似度: {sim:.2%}")
        
        return {
            "ids": [filtered_ids],
            "documents": [filtered_documents],
            "metadatas": [filtered_metadatas],
            "distances": [filtered_distances]
        }
    
    def ask(self, query: str) -> Dict[str, Any]:
        # 1. 先用 LLM 提取关键词
        keywords = self.extract_keywords(query)
        
        # 2. 检索并过滤（统一使用 Config 配置，无硬编码）
        search_results = self.search_with_filter(keywords)
        
        # 3. 提取来源
        sources = []
        metadatas = search_results.get("metadatas", [[]])[0]
        for meta in metadatas:
            sources.append({
                "meet_id": meta.get("meet_id", "未知"),
                "topic": meta.get("meeting_topic", "无主题")
            })
        
        # 4. 构建 context 和提问
        context = self.format_context(search_results)
        prompt = self.build_prompt(query, context)
        
        try:
            response = ollama.chat(
                model=Config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "num_predict": 1024}
            )
            answer = response["message"]["content"]
        except Exception as e:
            answer = f" 生成回答失败：{str(e)}"
        
        return {
            "query": query,
            "answer": answer,
            "sources": sources,
            "context": context
        }


# ===================== 数据导入 =====================
class DataImporter:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    def import_from_folder(self, folder_path: str) -> Dict[str, Any]:
        stats = {"total_found": 0, "success": 0, "failed": 0, "failed_ids": []}
        
        if not os.path.exists(folder_path):
            print(f" 文件夹不存在：{folder_path}")
            return stats
        
        json_files = glob.glob(os.path.join(folder_path, "*.json"))
        print(f"\n 导入文件夹：{folder_path}")
        print(f"   找到 {len(json_files)} 个 JSON 文件")
        
        for json_file in json_files:
            meet_id = os.path.basename(json_file).replace(".json", "")
            stats["total_found"] += 1
            
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    meeting_data = json.load(f)
                meeting_data["会议ID"] = meet_id
                
                if self.vector_store.add_meeting(meeting_data):
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
                    stats["failed_ids"].append(meet_id)
                    print(f"    {meet_id} 导入失败")
            except Exception as e:
                stats["failed"] += 1
                stats["failed_ids"].append(meet_id)
                print(f"    {meet_id} 读取失败：{str(e)}")
        
        return stats


# ===================== 交互式命令行 =====================
class InteractiveCLI:
    def __init__(self, rag: RAGQuery):
        self.rag = rag
        self.vector_store = rag.vector_store
    
    def run(self):
        self.print_welcome()
        
        while True:
            try:
                query = input("\n🤔 请输入问题 (输入 q 退出, i 查看统计): ").strip()
                
                if query.lower() == 'q':
                    print("\n👋 再见！")
                    break
                if query.lower() == 'i':
                    self.show_stats()
                    continue
                if not query:
                    continue
                
                print("\n🔍 正在检索相关会议...")
                result = self.rag.ask(query)
                self.print_result(result)
                
            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
    
    def print_welcome(self):
        print("\n" + "=" * 60)
        print("   📚 会议纪要 RAG 智能问答系统")
        print("=" * 60)
        print("\n   💡 使用说明：")
        print("       - 输入任意问题，系统会从历史会议中检索相关信息")
        print("       - 输入 'q' 退出程序")
        print("       - 输入 'i' 查看向量库统计")
        print("\n   📝 示例问题：")
        print("       - 上次关于预算的会议有什么决议？")
        print("       - 张三负责了哪些任务？")
        print("       - 有什么遗留问题没有解决？")
        print("\n" + "=" * 60)
    
    def print_result(self, result: Dict[str, Any]):
        print("\n" + "-" * 50)
        print(f"📋 问题：{result['query']}")
        print("-" * 50)
        print(f"💡 回答：\n{result['answer']}")
        
        if result['sources']:
            print("\n📚 参考来源：")
            for i, source in enumerate(result['sources'], 1):
                print(f"   {i}. 会议 {source['meet_id']} - {source['topic'][:50]}")
        print("-" * 50)
    
    def show_stats(self):
        stats = self.vector_store.get_stats()
        meetings = self.vector_store.list_all_meetings()
        
        print("\n" + "-" * 40)
        print(" 向量库统计")
        print("-" * 40)
        print(f"   会议总数：{stats['total_meetings']}")
        if meetings:
            print(f"   会议列表：{', '.join(meetings[:10])}")
            if len(meetings) > 10:
                print(f"   ... 共 {len(meetings)} 条")
        print("-" * 40)


# ===================== 主函数 =====================
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="会议纪要 RAG 系统")
    parser.add_argument("--import-only", action="store_true", help="只导入数据")
    parser.add_argument("--query", type=str, help="直接提问")
    parser.add_argument("--clear", action="store_true", help="清空向量库")
    
    args = parser.parse_args()
    
    print(" 正在初始化向量库...")
    vector_store = VectorStore()
    
    if args.clear:
        vector_store.clear()
    
    if vector_store.collection.count() == 0:
        print("\n 向量库为空，开始导入会议纪要数据...")
        importer = DataImporter(vector_store)
        stats = importer.import_from_folder(Config.JSON_FOLDER)
        
        print("\n" + "=" * 50)
        print(" 导入统计")
        print(f"   发现文件：{stats['total_found']} 个")
        print(f"   导入成功：{stats['success']} 个")
        print(f"   导入失败：{stats['failed']} 个")
        print("=" * 50)
    else:
        print(f"\n 向量库已有 {vector_store.collection.count()} 条记录")
    
    if args.query:
        rag = RAGQuery(vector_store)
        result = rag.ask(args.query)
        print(f"\n 问题：{result['query']}")
        print(f" 回答：\n{result['answer']}")
        return
    
    if args.import_only:
        print("\n 导入完成，退出。")
        return
    
    rag = RAGQuery(vector_store)
    cli = InteractiveCLI(rag)
    cli.run()


if __name__ == "__main__":
    main()