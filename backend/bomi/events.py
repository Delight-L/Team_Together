"""프론트엔드(BomiChat.jsx)와 맺은 이벤트 계약. 이 파일이 계약의 유일한 정의입니다.

이벤트는 (이름, 내용) 쌍이며 서버가 `event: 이름 / data: JSON`(SSE)으로 내보냅니다.
화면은 아래 10종을 처리하므로 이름과 내용 필드를 바꾸면 화면이 깨집니다.

| 이름 | 내용 | 화면에서 하는 일 |
|---|---|---|
| route      | agent, label, by          | 담당 이름 표시 |
| sources    | records, mode             | 참고한 복지사업 목록 |
| conversation | state                   | 다음 요청에 보낼 서명된 대화 근거 |
| token      | text                      | 답변 글자를 이어 붙임 |
| replace    | text, mode, source        | 답변 전체를 교체 |
| follow_ups | questions                 | 후속 질문 버튼 |
| actions    | actions                   | 액션 버튼(보고서 탭 열기 등) |
| notice     | message, question(선택)   | 안내문. question이 있으면 사용자 말풍선도 교체 |
| error      | message                   | 오류 표시와 재시도 |
| done       | (없음)                    | 스트림 완료. 없으면 화면이 «연결 중단» 오류를 냄 |

순서 규칙
- 요청 맨 앞에 notice(개인정보 가림)가 올 수 있고, 그다음은 항상 route입니다.
- 마지막은 항상 done 한 번입니다(`seal`이 보장합니다. 에이전트는 done을 보내지 않습니다).
- error는 치명적이지 않습니다. 뒤에 대체 답변(replace)이 이어질 수 있습니다.
"""

import logging
from collections.abc import Iterator

from backend.db.welfare_chatbot_repository import WelfareDataError

LOGGER = logging.getLogger(__name__)

Event = tuple[str, dict]

ROUTE, SOURCES, TOKEN, REPLACE = 'route', 'sources', 'token', 'replace'
FOLLOW_UPS, ACTIONS, NOTICE, ERROR, DONE = 'follow_ups', 'actions', 'notice', 'error', 'done'
CONVERSATION = 'conversation'
EVENT_NAMES = (
    ROUTE,
    SOURCES,
    TOKEN,
    REPLACE,
    FOLLOW_UPS,
    ACTIONS,
    NOTICE,
    ERROR,
    DONE,
    CONVERSATION,
)

FAILURE_MESSAGE = '답변을 만드는 중 문제가 생겼습니다. 잠시 후 다시 질문해 주세요.'
WELFARE_DATA_MESSAGE = (
    '복지자료 DB를 조회하지 못했습니다. 관리자에게 DB 연결과 자료 적재 상태 확인을 요청해 주세요.'
)


def route(agent: str, label: str, by: str) -> Event:
    return ROUTE, {'agent': agent, 'label': label, 'by': by}


def sources(records: list, mode: str, **metadata) -> Event:
    return SOURCES, {'records': records, 'mode': mode, **metadata}


def conversation(state: str) -> Event:
    return CONVERSATION, {'state': state}


def token(text: str) -> Event:
    return TOKEN, {'text': text}


def replace(text: str, mode: str = '', source: str = '') -> Event:
    return REPLACE, {'text': text, 'mode': mode, 'source': source}


def follow_ups(questions: list) -> Event:
    return FOLLOW_UPS, {'questions': list(questions)}


def actions(items: list) -> Event:
    return ACTIONS, {'actions': items}


def notice(message: str, question: str | None = None) -> Event:
    payload = {'message': message}
    if question is not None:
        payload['question'] = question
    return NOTICE, payload


def error(message: str) -> Event:
    return ERROR, {'message': message}


def done() -> Event:
    return DONE, {}


def seal(stream: Iterator[Event]) -> Iterator[Event]:
    """계약을 지키도록 스트림을 감쌉니다.

    - 에이전트가 보낸 done은 버리고, 끝에 done을 정확히 한 번만 붙입니다.
    - 중간에 예외가 나면 상세 내용 없이 error 이벤트로 바꾸고 done으로 마칩니다.
    - 받는 쪽이 멈추면 안쪽 스트림도 닫습니다.
    """
    try:
        for name, payload in stream:
            if name != DONE:
                yield name, payload
    except WelfareDataError:
        LOGGER.exception('복지자료 DB 조회 실패')
        yield error(WELFARE_DATA_MESSAGE)
    except Exception:
        LOGGER.exception('보미 답변 처리 실패')
        yield error(FAILURE_MESSAGE)
    finally:
        close = getattr(stream, 'close', None)
        if close:
            close()
    yield done()
