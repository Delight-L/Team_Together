"""보미 AI 가드레일: 외부 AI로 보내기 전 개인정보 가리기, AI 답변 속 미확인 정보 가리기.

- mask_pii: 사용자 입력의 주민등록번호·카드번호·전화번호·이메일·상세 주소를 «[주민등록번호 가림]»처럼 바꿉니다.
  외부 AI 사용 여부와 상관없이 서버에 들어온 질문에 항상 적용합니다.
- redact_unverified: AI 답변에 나온 전화번호·URL·금액이 근거 자료에 없으면 «[자료에 없는 정보 · 기관 확인 필요]»로 바꿉니다.
  보고서는 agents/report_writer.check_grounding이 더 엄격하게 대조합니다.
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
        found += [kind for kind in kinds if kind not in found]
    return masked, found


def mask_question(question, history=None):
    """예전 JSON 호출 경로용: 질문과 이력(content 또는 text 항목)의 개인정보를 가립니다."""
    question = mask_pii(str(question))[0]
    if isinstance(history, list):
        history = [{**item, **{key: mask_pii(str(item[key]))[0] for key in ('content', 'text') if key in item}}
                   if isinstance(item, dict) else item for item in history]
    return question, history


def _digits(value):
    return re.sub(r'\D', '', value)


def redact_unverified(text, material):
    """(가린 답변, 가린 정보 종류 목록)을 돌려줍니다. material은 AI에게 준 근거 자료 문자열입니다."""
    found = []
    known_phones = {_digits(p) for pattern in (PHONE, SERVICE_PHONE) for p in pattern.findall(material)}
    compact_material = re.sub(r'[\s,]', '', material)

    def phone(match):
        if _digits(match.group()) in known_phones:
            return match.group()
        found.append('연락처')
        return UNVERIFIED

    def url(match):
        value = match.group().rstrip('.,;:')
        if value in material:
            return match.group()
        found.append('URL')
        return UNVERIFIED

    def money(match):
        if re.sub(r'[\s,]', '', match.group()) in compact_material:
            return match.group()
        found.append('금액')
        return UNVERIFIED

    text = URL.sub(url, text)
    for pattern in (PHONE, SERVICE_PHONE):
        text = pattern.sub(phone, text)
    text = MONEY.sub(money, text)
    return text, sorted(set(found), key=found.index)
