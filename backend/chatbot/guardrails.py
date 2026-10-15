"""보미 AI 가드레일: 외부 AI로 보내기 전 개인정보 가리기, AI 답변 속 미확인 정보 가리기.

- mask_pii: 사용자 입력의 주민등록번호·카드번호·전화번호·이메일·상세 주소를 «[주민등록번호 가림]»처럼 바꿉니다.
  외부 AI 사용 여부와 상관없이 서버에 들어온 질문에 항상 적용합니다.
- redact_unverified: AI 답변에 나온 전화번호·URL·금액이 근거 자료에 없으면 «[자료에 없는 정보 · 기관 확인 필요]»로 바꿉니다.
  보고서는 agents/report_writer.check_grounding이 더 엄격하게 대조합니다.
  이어 보내는 답변은 StreamRedactor가 줄 단위로 먼저 검사한 뒤 보냅니다.
- blocked_words: 욕설·위험한 요청·지시 무력화 시도를 단어 규칙으로 막습니다(외부 검사 API가 없어도 동작).
"""
import re

PHONE = re.compile(r'(?<!\d)(?:01[016789]|0(?:2|[3-6][1-5]|70))[-.\s)]?\d{3,4}[-.\s]?\d{4}(?!\d)')
# 기관 대표번호(1588-0000 등)는 개인정보가 아니므로 답변 검사에서만 씁니다.
SERVICE_PHONE = re.compile(r'(?<!\d)1[5-9]\d{2}-\d{4}(?!\d)')
URL = re.compile(r'https?://[^\s)\]>"\']+|www\.[^\s)\]>"\']+')
MONEY = re.compile(r'\d[\d,]*(?:\.\d+)?\s?(?:억|천만|백만|만|천)?\s?원')
PII_PATTERNS = (
    ('주민등록번호', re.compile(r'(?<!\d)\d{6}\s?[-–]?\s?[1-8]\d{6}(?!\d)')),
    ('카드번호', re.compile(r'(?<!\d)\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}(?!\d)')),
    ('전화번호', PHONE),
    ('이메일', re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')),
    ('상세 주소', re.compile(r'[가-힣0-9]+(?:로|길)\s?\d+(?:-\d+)?(?:번길\s?\d+(?:-\d+)?)?|\d+동\s?\d+호')),
)
UNVERIFIED = '[자료에 없는 정보 · 기관 확인 필요]'


def mask_pii(text):
    """(가린 문장, 찾은 개인정보 종류 목록)을 돌려줍니다."""
    found = []
    for kind, pattern in PII_PATTERNS:
        text, count = pattern.subn(f'[{kind} 가림]', text)
        if count:
            found.append(kind)
    return text, found


def mask_messages(messages):
    """대화 전체에 mask_pii를 적용합니다. 이전 대화에 남은 개인정보도 다시 보내지 않습니다."""
    masked, found = [], []
    for message in messages:
        content, kinds = mask_pii(message['content'])
        masked.append({**message, 'content': content})
        for kind in kinds:
            _add_once(found, kind)
    return masked, found


def _digits(value):
    """'02-1234-5678'처럼 표기가 달라도 같은 번호로 비교하도록 숫자만 남깁니다."""
    return re.sub(r'\D', '', value)


def _compact(value):
    """'10 만원'·'100,000원'처럼 띄어쓰기·쉼표가 달라도 같은 금액으로 비교하도록 지웁니다."""
    return re.sub(r'[\s,]', '', value)


def redact_unverified(text, material):
    """(가린 답변, 가린 정보 종류 목록)을 돌려줍니다. material은 AI에게 준 근거 자료 문자열입니다.

    답변 속 URL·전화번호·금액을 하나씩 찾아, 근거 자료에 없으면 UNVERIFIED 문구로 바꿉니다.
    """
    hidden = []
    known_phones = set()
    for pattern in (PHONE, SERVICE_PHONE):
        for phone in pattern.findall(material):
            known_phones.add(_digits(phone))

    for url in URL.findall(text):
        if url.rstrip('.,;:') not in material:
            text = text.replace(url, UNVERIFIED)
            _add_once(hidden, 'URL')

    for pattern in (PHONE, SERVICE_PHONE):
        for phone in pattern.findall(text):
            if _digits(phone) not in known_phones:
                text = text.replace(phone, UNVERIFIED)
                _add_once(hidden, '연락처')

    compact_material = _compact(material)
    for money in MONEY.findall(text):
        if _compact(money) not in compact_material:
            text = text.replace(money, UNVERIFIED)
            _add_once(hidden, '금액')

    return text, hidden


class StreamRedactor:
    """AI 답변을 이어 보낼 때, 가리기 전 정보가 화면에 잠깐이라도 보이지 않게 줄 단위로 검사합니다.

    feed()는 끝난 줄(또는 길어진 문장의 안전한 앞부분)만 redact_unverified로 검사해 돌려주고,
    나머지는 다음 조각과 이어질 수 있으므로 들고 있다가 flush()에서 내보냅니다.
    """
    LONG = 120  # 줄바꿈 없이 이만큼 쌓이면 띄어쓰기 위치에서 끊어 먼저 보냅니다.

    def __init__(self, material):
        self.material = material
        self.buffer = ''
        self.hidden = []

    def _check(self, text):
        text, kinds = redact_unverified(text, self.material)
        for kind in kinds:
            _add_once(self.hidden, kind)
        return text

    def _cut(self):
        """지금 내보내도 되는 위치. 전화번호(02 1234 5678)·금액(10 만원)의 띄어쓰기에서는 끊지 않습니다."""
        newline = self.buffer.rfind('\n')
        if newline >= 0:
            return newline + 1
        if len(self.buffer) < self.LONG:
            return 0
        for index in range(len(self.buffer) - 1, 0, -1):
            if self.buffer[index].isspace() and not self.buffer[index - 1].isdigit() \
                    and self.buffer[index + 1:index + 2] not in ('원', ''):
                return index + 1
        return 0

    def feed(self, text):
        self.buffer += text
        cut = self._cut()
        if not cut:
            return ''
        ready, self.buffer = self.buffer[:cut], self.buffer[cut:]
        return self._check(ready)

    def flush(self):
        ready, self.buffer = self.buffer, ''
        return self._check(ready) if ready else ''


# 외부 유해 콘텐츠 검사(OpenAI 키 필요)와 별개로 항상 쓰는 단어 규칙입니다.
# 자살·학대·폭력 같은 말은 복지 업무에서 정당하게 쓰므로 넣지 않습니다(예: "자살 예방 사업 찾아 줘").
BLOCKED_WORDS = (
    ('욕설', ('씨발', '씨바', 'ㅅㅂ', '병신', '개새끼', '좆', '지랄', '미친놈', '미친년', '닥쳐')),
    ('위험한 요청', ('폭탄만드', '폭탄제조', '마약구하', '마약구매', '필로폰', '총기제작', '해킹하는법', '해킹방법')),
    ('지시 무력화', ('이전지시무시', '지시를무시', '지시는무시', '규칙을무시', '시스템프롬프트', '프롬프트를보여',
                    '탈옥', 'jailbreak', 'ignorepreviousinstructions', 'ignoreallprevious')),
)


def blocked_words(text):
    """단어 규칙에 걸린 분류 이름 목록. 빈 목록이면 통과입니다. 띄어쓰기·대소문자는 무시합니다."""
    compact = re.sub(r'\s+', '', text).lower()
    return [kind for kind, words in BLOCKED_WORDS if any(word in compact for word in words)]


def _add_once(items, item):
    if item not in items:
        items.append(item)
