import pytest

from services.meeting_rag import MeetingRAG, chunk_text


def test_chunk_text_keeps_content():
    chunks = chunk_text("abcdefg" * 200, chunk_size=100, overlap=10)
    assert len(chunks) > 1
    assert chunks[0]


def test_meeting_rag_indexes_and_searches(tmp_path):
    pytest.importorskip("chromadb")
    rag = MeetingRAG(chroma_path=tmp_path, collection_name="test_meeting_minutes")
    count = rag.index_meeting(
        meeting_id=1,
        title="微服务拆分技术评审",
        meeting_date="2024-06-15",
        minutes_markdown="会议决定采用 DDD，第一期拆分用户服务和订单服务。王工负责补充服务边界文档。",
    )

    hits = rag.similarity_search("微服务拆分结论是什么", top_k=2)

    assert count >= 1
    assert hits
    assert hits[0].meeting_id == 1
    assert "微服务" in hits[0].title


def test_meeting_rag_answer_without_llm(tmp_path):
    pytest.importorskip("chromadb")
    rag = MeetingRAG(chroma_path=tmp_path, collection_name="test_meeting_answers")
    rag.store_minutes(
        meeting_id=2,
        title="Q3 产品规划讨论",
        meeting_date="2024-06-01",
        minutes_markdown="决议：Q3 优先开发分享裂变和邀请奖励。李经理负责 PRD。",
    )

    result = rag.answer("Q3 优先开发什么？", use_llm=False)

    assert "分享裂变" in result["answer"]
    assert result["sources"][0]["title"] == "Q3 产品规划讨论"


def test_meeting_rag_hybrid_search_boosts_exact_keywords(tmp_path):
    pytest.importorskip("chromadb")
    rag = MeetingRAG(chroma_path=tmp_path, collection_name="test_hybrid_meeting_search")
    rag.store_minutes(
        meeting_id=10,
        title="酒店运营复盘",
        meeting_date="2024-05-20",
        minutes_markdown="会议讨论了入住率、早餐供应和前台排班优化方案。",
    )
    rag.store_minutes(
        meeting_id=11,
        title="项目分工会议",
        meeting_date="2024-05-21",
        minutes_markdown="行动项：赵敏负责整理验收材料，截止时间为本周五。",
    )

    hits = rag.similarity_search("赵敏负责什么任务？", top_k=1)

    assert hits
    assert hits[0].meeting_id == 11
    assert "赵敏" in hits[0].content
