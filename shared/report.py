"""첨부 약식보고서의 OOXML 구성요소를 재사용해 편집 가능한 DOCX를 만듭니다."""
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo
from lxml import etree
from agents.report_writer import SECTIONS, generate_draft, validate_content

TEMPLATE = Path(__file__).resolve().parents[1] / 'docs' / '약식보고서_서식_보고서.docx'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def _tag(name):
    return '{' + NS['w'] + '}' + name


def _replace_text(paragraph, text, preferred_font=None):
    runs = paragraph.findall('w:r', NS)
    chosen = next((run for run in runs if preferred_font and
                   run.find('w:rPr/w:rFonts', NS) is not None and
                   run.find('w:rPr/w:rFonts', NS).get(_tag('eastAsia')) == preferred_font),
                  runs[0] if runs else None)
    properties = deepcopy(chosen.find('w:rPr', NS)) if chosen is not None else None
    for child in list(paragraph):
        if child.tag != _tag('pPr'):
            paragraph.remove(child)
    run = etree.SubElement(paragraph, _tag('r'))
    if properties is not None:
        run.append(properties)
    node = etree.SubElement(run, _tag('t'))
    node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    node.text = text


def _allow_growth(element):
    # 원본의 고정 행 높이는 입력 내용이 길어질 때 잘릴 수 있습니다.
    for height in element.findall('.//w:trHeight', NS):
        height.set(_tag('hRule'), 'atLeast')


def build_report(context, rows, author, department, opinion, source_note, workflow=None,
                 content=None, contact=''):
    workflow = workflow or {'done': [0, 1, 2], 'analysis_evidence': rows, 'reviews': []}
    draft = validate_content(content or generate_draft(context, workflow))
    if not content and opinion.strip():
        draft['next_steps'] = opinion.strip()
    output = BytesIO()
    with ZipFile(TEMPLATE) as source, ZipFile(output, 'w') as destination:
        root = etree.fromstring(source.read('word/document.xml'))
        body = root.find('w:body', NS)
        patterns = list(body)
        if (len(patterns) < 13 or patterns[0].tag != _tag('tbl') or
                patterns[5].tag != _tag('tbl') or patterns[-1].tag != _tag('sectPr') or
                any(patterns[i].tag != _tag('p') for i in (7, 9, 11, 12))):
            raise ValueError('약식보고서 템플릿 구조가 변경되었습니다. 서식 연결을 확인하세요.')
        title, overview = deepcopy(patterns[0]), deepcopy(patterns[5])
        heading, detail, explanation, note = (deepcopy(patterns[i]) for i in (7, 9, 11, 12))
        section = deepcopy(patterns[-1])
        for child in list(body):
            body.remove(child)
        now = datetime.now(ZoneInfo('Asia/Seoul'))
        date = '’' + now.strftime('%y. %m. %d.') + '(' + '월화수목금토일'[now.weekday()] + ')'
        metadata = f'{department} / 담당: {author}' + (f' / 연락처: {contact}' if contact else '')
        for paragraph, text in zip(title.findall('.//w:p', NS), [draft['title'], date, metadata]):
            _replace_text(paragraph, text)
        _allow_growth(title)
        body.append(title)
        _replace_text(overview.find('.//w:p', NS), draft['summary'])
        cell = overview.find('.//w:tc', NS)
        for paragraph in cell.findall('w:p', NS)[1:]:
            cell.remove(paragraph)
        _allow_growth(overview)
        body.append(overview)
        for key, label in SECTIONS:
            paragraph = deepcopy(heading)
            _replace_text(paragraph, '□ ' + label)
            etree.SubElement(paragraph.find('w:pPr', NS), _tag('keepNext'))
            body.append(paragraph)
            for line in draft[key].splitlines():
                if not line.strip():
                    continue
                lower = line.lstrip().startswith('-')
                paragraph = deepcopy(explanation if lower else detail)
                _replace_text(paragraph, '   - ' + line.lstrip('- ').strip() if lower else ' ㅇ ' + line.strip(),
                              preferred_font='휴먼명조' if lower else None)
                body.append(paragraph)
        paragraph = deepcopy(note)
        _replace_text(paragraph, '     ※ 자료 출처: ' + source_note)
        body.append(paragraph)
        if workflow.get('is_demo'):
            paragraph = deepcopy(note)
            _replace_text(paragraph, '     ※ 시연 자료 · 기관 제출 불가')
            body.append(paragraph)
        body.append(section)
        # 스타일·섹션·머리말/꼬리말·관계 등 나머지 패키지 파트는 원본 그대로 보존합니다.
        for entry in source.infolist():
            data = (etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                    if entry.filename == 'word/document.xml' else source.read(entry.filename))
            destination.writestr(entry, data)
    return output.getvalue()
