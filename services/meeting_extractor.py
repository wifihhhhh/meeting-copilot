import json
import re
from typing import Any, Callable, TypeVar

from pydantic import ValidationError
from requests import RequestException

from config import FIELD_LEVEL_HYBRID_EXTRACTION, MIN_RAW_TEXT_LENGTH, PROMPT_DIR
from services.meeting_schema import ActionItem, DecisionItem, DiscussionPoint, MeetingMinutes, Topic
from services.ollama_client import OllamaClient, parse_json_block

T = TypeVar("T")


class MeetingExtractionError(Exception):
    """Base exception for meeting extraction failures."""


class InvalidMeetingTextError(MeetingExtractionError):
    """Raised when the input text is empty or too short."""


class OllamaGenerationError(MeetingExtractionError):
    """Raised when Ollama cannot generate a usable response."""


class LLMOutputParseError(MeetingExtractionError):
    """Raised when the LLM response cannot be parsed as JSON."""


class MeetingSchemaValidationError(MeetingExtractionError):
    """Raised when parsed JSON does not match MeetingMinutes schema."""


class MeetingExtractor:
    def __init__(
        self,
        client: OllamaClient | None = None,
        field_level_hybrid: bool = FIELD_LEVEL_HYBRID_EXTRACTION,
    ) -> None:
        self.client = client or OllamaClient()
        self.field_level_hybrid = field_level_hybrid

    def extract(
        self,
        raw_text: str,
        use_llm: bool = True,
        fallback_to_heuristic: bool = True,
    ) -> MeetingMinutes:
        raw_text = self._validate_input(raw_text)
        if not use_llm:
            return self._heuristic_extract(raw_text)

        try:
            llm_result = self._extract_with_ollama(raw_text)
            if self.field_level_hybrid:
                return self._merge_field_level(raw_text, llm_result)
            return llm_result
        except MeetingExtractionError:
            if fallback_to_heuristic:
                return self._heuristic_extract(raw_text)
            raise

    def _merge_field_level(self, raw_text: str, llm_result: MeetingMinutes) -> MeetingMinutes:
        """Keep LLM action items, while preferring high-precision rule decisions."""
        rule_decisions = self._find_decisions(raw_text)
        if not rule_decisions:
            return llm_result
        return llm_result.model_copy(update={"decisions": rule_decisions})

    def _extract_with_ollama(self, raw_text: str) -> MeetingMinutes:
        prompt = self._build_prompt(raw_text)
        schema = MeetingMinutes.model_json_schema()
        try:
            response = self.client.generate(prompt, temperature=0.1, format_schema=schema)
        except RequestException as exc:
            raise OllamaGenerationError(f"Ollama request failed: {exc}") from exc
        except Exception as exc:
            raise OllamaGenerationError(f"Ollama generation failed: {exc}") from exc

        try:
            data = parse_json_block(response)
        except (json.JSONDecodeError, ValueError) as exc:
            data = self._repair_json(response, schema)

        try:
            return MeetingMinutes.model_validate(data)
        except ValidationError as exc:
            repaired = self._repair_json(json.dumps(data, ensure_ascii=False), schema)
            try:
                return MeetingMinutes.model_validate(repaired)
            except ValidationError as repaired_exc:
                raise MeetingSchemaValidationError(
                    f"LLM output does not match MeetingMinutes schema: {repaired_exc}"
                ) from exc

    def _repair_json(self, broken_text: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            template = (PROMPT_DIR / "repair_json_prompt.md").read_text(encoding="utf-8")
            prompt = template.replace("{{BROKEN_JSON}}", broken_text).replace(
                "{{JSON_SCHEMA}}", json.dumps(schema, ensure_ascii=False, indent=2)
            )
            repaired = self.client.generate(prompt, temperature=0.0, format_schema=schema)
            return parse_json_block(repaired)
        except Exception as exc:
            raise LLMOutputParseError(f"Could not parse or repair LLM JSON output: {exc}") from exc

    @staticmethod
    def _validate_input(raw_text: str) -> str:
        if raw_text is None:
            raise InvalidMeetingTextError("会议记录不能为空。")
        clean = raw_text.strip()
        if len(clean) < MIN_RAW_TEXT_LENGTH:
            raise InvalidMeetingTextError("会议记录太短，请输入更完整的会议文本。")
        return clean

    @staticmethod
    def _build_prompt(raw_text: str) -> str:
        prompt_template = (PROMPT_DIR / "extract_minutes_prompt.md").read_text(encoding="utf-8")
        schema = json.dumps(MeetingMinutes.model_json_schema(), ensure_ascii=False, indent=2)
        return prompt_template.replace("{{MEETING_TEXT}}", raw_text).replace("{{JSON_SCHEMA}}", schema)

    def _heuristic_extract(self, raw_text: str) -> MeetingMinutes:
        participants = self._find_participants(raw_text)
        actions = self._find_actions(raw_text)
        decisions = self._find_decisions(raw_text)
        title = self._find_title(raw_text)
        date = self._find_date(raw_text)
        time = self._find_time(raw_text)
        topics = self._split_topics(raw_text, decisions)
        summary = self._summary(raw_text, decisions, actions)
        return MeetingMinutes(
            title=title,
            date=date,
            time=time,
            participants=participants,
            summary=summary,
            topics=topics,
            decisions=decisions,
            action_items=actions,
        )

    @staticmethod
    def _find_title(text: str) -> str:
        title_match = re.search(r"(?:主题|会议主题)[:：]\s*(.+)", text)
        if title_match:
            return title_match.group(1).strip()[:80]
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return first_line[:40] if first_line else "未命名会议"

    @staticmethod
    def _find_date(text: str) -> str:
        match = re.search(r"(20\d{2}[-年/]\d{1,2}[-月/]\d{1,2}日?)", text)
        return match.group(1) if match else ""

    @staticmethod
    def _find_time(text: str) -> str:
        explicit = re.search(r"(?:时间|会议时间)[:：]\s*([0-2]?\d:[0-5]\d(?:\s*[-~—]\s*[0-2]?\d:[0-5]\d)?)", text)
        return explicit.group(1).strip() if explicit else ""

    @staticmethod
    def _find_participants(text: str) -> list[str]:
        explicit = re.search(r"(?:参会人|参会人员|参与人)[:：]\s*(.+)", text)
        if explicit:
            names = re.split(r"[、,，\s]+", explicit.group(1).strip())
            return [name for name in names if name]
        speakers = re.findall(r"([\u4e00-\u9fa5A-Za-z]{2,10})[:：]", text)
        ignored = {"主题", "会议主题", "时间", "会议时间", "议题", "决议", "参会人"}
        seen: list[str] = []
        for speaker in speakers:
            if speaker not in seen and speaker not in ignored:
                seen.append(speaker)
        return seen[:12]

    @staticmethod
    def _find_actions(text: str) -> list[ActionItem]:
        patterns = [
            r"([\u4e00-\u9fa5A-Za-z]{2,10})\s*(\d{1,2}[/-]\d{1,2}|下周[一二三四五六日天]?|本周[一二三四五六日天]?|[一二三四五六七八九十]+月\d{1,2}日)?\s*前?(.{0,8})(完成|提交|输出|整理|设计|跟进|确认|补充)([^。；;\n]+)",
            r"安排\s*([\u4e00-\u9fa5A-Za-z]{2,10})([^。；;\n]+)",
        ]
        actions: list[ActionItem] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                groups = match.groups()
                owner = groups[0]
                deadline = next((item for item in groups[1:] if item and _looks_like_deadline(item)), "")
                task = "".join(item for item in groups[1:] if item and not _looks_like_deadline(item)).strip()
                if task:
                    actions.append(ActionItem(owner=owner, task=task, deadline=deadline, status="待办"))
        return _dedupe_models(actions, key=lambda item: f"{item.owner}:{item.task}")[:10]

    @staticmethod
    def _find_decisions(text: str) -> list[DecisionItem]:
        decisions: list[DecisionItem] = []
        for line in re.split(r"[。\n]", text):
            if any(word in line for word in ["决定", "决议", "确定", "统一", "达成一致", "采用"]):
                owner_match = re.search(r"由([\u4e00-\u9fa5A-Za-z]{2,10})", line)
                deadline_match = re.search(r"(\d{1,2}[/-]\d{1,2}|[一二三四五六七八九十]+月\d{1,2}日|下周[一二三四五六日天]?)", line)
                decisions.append(
                    DecisionItem(
                        owner=owner_match.group(1) if owner_match else "",
                        content=line.strip(),
                        deadline=deadline_match.group(1) if deadline_match else "",
                        topic="",
                    )
                )
        return _dedupe_models(decisions, key=lambda item: item.content)[:10]

    @staticmethod
    def _split_topics(text: str, decisions: list[DecisionItem]) -> list[Topic]:
        sections = re.split(r"(议题[一二三四五六七八九十\d]+[:：].+)", text)
        topics: list[Topic] = []
        if len(sections) > 1:
            for index in range(1, len(sections), 2):
                title = sections[index].strip()
                body = sections[index + 1].strip() if index + 1 < len(sections) else ""
                points = [
                    DiscussionPoint(point=line.strip())
                    for line in re.split(r"[。\n]", body)
                    if line.strip()
                ][:6]
                topics.append(Topic(title=title, discussion_points=points, decisions=[]))
        if not topics:
            points = [
                DiscussionPoint(point=line.strip())
                for line in re.split(r"[。\n]", text)
                if line.strip()
            ][:8]
            topics.append(Topic(title="综合讨论", discussion_points=points, decisions=[item.content for item in decisions]))
        return topics

    @staticmethod
    def _summary(text: str, decisions: list[DecisionItem], actions: list[ActionItem]) -> str:
        summary = text.replace("\n", " ").strip()[:140]
        return f"本次会议围绕主要议题展开讨论，形成 {len(decisions)} 项决议和 {len(actions)} 个待办事项。{summary}"


def _looks_like_deadline(text: str) -> bool:
    return bool(re.search(r"(\d{1,2}[/-]\d{1,2}|下周|本周|月\d{1,2}日)", text))


def _dedupe_models(items: list[T], key: Callable[[T], str]) -> list[T]:
    seen: set[str] = set()
    result: list[T] = []
    for item in items:
        marker = key(item)
        if marker and marker not in seen:
            seen.add(marker)
            result.append(item)
    return result
