from database.repository import MeetingRepository
from services.auth_service import AuthError, AuthService


def test_repository_create_and_list():
    repo = MeetingRepository()
    meeting_id = repo.create_meeting(
        title="测试会议",
        meeting_date="2024-06-01",
        raw_text="测试原文",
        minutes_json={
            "title": "测试会议",
            "action_items": [{"owner": "张三", "task": "完成 PRD", "deadline": "6/7", "status": "待办"}],
            "decisions": [{"owner": "李四", "content": "采用方案 A", "deadline": "", "topic": "方案评审"}],
        },
        minutes_markdown="# 测试会议",
    )
    record = repo.get_meeting(meeting_id)
    assert record is not None
    assert record.title == "测试会议"
    assert repo.list_action_items(meeting_id)[0].task == "完成 PRD"
    assert repo.list_decisions(meeting_id)[0].content == "采用方案 A"


def test_repository_save_evaluation_result():
    repo = MeetingRepository()
    result_id = repo.save_evaluation_result(
        metric_name="action_item_extraction",
        precision=0.8,
        recall=0.6,
        f1=0.685,
        notes="unit test",
        payload={"cases": 1},
    )
    results = repo.list_evaluation_results()
    assert any(item.id == result_id and item.metric_name == "action_item_extraction" for item in results)


def test_repository_filters_meetings_by_user():
    repo = MeetingRepository()
    auth = AuthService()
    try:
        user1 = auth.register("repo_user_one", "secret123", "User One")
    except AuthError:
        user1 = auth.authenticate("repo_user_one", "secret123")
    try:
        user2 = auth.register("repo_user_two", "secret123", "User Two")
    except AuthError:
        user2 = auth.authenticate("repo_user_two", "secret123")

    first_id = repo.create_meeting(
        title="用户一会议",
        meeting_date="2024-06-01",
        raw_text="用户一原文",
        minutes_json={"title": "用户一会议", "action_items": [], "decisions": []},
        minutes_markdown="# 用户一会议",
        user_id=user1.id,
    )
    second_id = repo.create_meeting(
        title="用户二会议",
        meeting_date="2024-06-02",
        raw_text="用户二原文",
        minutes_json={"title": "用户二会议", "action_items": [], "decisions": []},
        minutes_markdown="# 用户二会议",
        user_id=user2.id,
    )

    first_user_meetings = repo.list_meetings(user_id=user1.id)
    second_user_meetings = repo.list_meetings(user_id=user2.id)

    assert any(item.id == first_id for item in first_user_meetings)
    assert all(item.id != second_id for item in first_user_meetings)
    assert any(item.id == second_id for item in second_user_meetings)


def test_repository_updates_action_status_for_owner():
    repo = MeetingRepository()
    auth = AuthService()
    try:
        user = auth.register("repo_status_user", "secret123", "Status User")
    except AuthError:
        user = auth.authenticate("repo_status_user", "secret123")

    meeting_id = repo.create_meeting(
        title="Action Board Meeting",
        meeting_date="2024-06-03",
        raw_text="Action board raw text",
        minutes_json={
            "title": "Action Board Meeting",
            "action_items": [{"owner": "Alice", "task": "Prepare launch checklist", "deadline": "6/10", "status": "待办"}],
            "decisions": [],
        },
        minutes_markdown="# Action Board Meeting",
        user_id=user.id,
    )
    item = repo.list_action_items(meeting_id, user_id=user.id)[0]
    repo.update_action_item_status(item.id, "进行中", user_id=user.id)

    updated = repo.list_action_items(meeting_id, user_id=user.id)[0]
    assert updated.status == "进行中"
