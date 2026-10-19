"""첨부 약식보고서의 OOXML 구성요소를 재사용해 편집 가능한 DOCX를 만듭니다."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from backend.agents.report_writer import section_labels, generate_draft, validate_content, report_source_label
from backend.common import seoul_now

TEMPLATE = Path(__file__).resolve().parents[1] / 'resources' / 'templates' / '약식보고서_서식_보고서.docx'
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


def _hanging(paragraph, left, hanging):
    """줄이 넘칠 때 둘째 줄이 기호(ㅇ, -) 뒤 글자 위치에 맞춰 들여쓰이게 합니다(단위: 1/20pt)."""
    ind = paragraph.find('w:pPr/w:ind', NS)
    if ind is None:
        ind = etree.SubElement(paragraph.find('w:pPr', NS), _tag('ind'))
    for name in ('firstLine', 'hanging'):
        ind.attrib.pop(_tag(name), None)
    ind.set(_tag('left'), str(left))
    ind.set(_tag('hanging'), str(hanging))


def _fit_title(paragraph, text):
    """제목이 한 줄(약 470pt)에 들어가도록 글자 크기를 줄입니다. 최소 18pt, 더 길면 두 줄로 넘어갑니다."""
    size = max(36, min(54, int(2 * 470 / max(len(text), 1))))
    for node in paragraph.findall('.//w:sz', NS):
        node.set(_tag('val'), str(size))
    spacing = paragraph.find('w:pPr/w:spacing', NS)
    if spacing is not None:
        spacing.set(_tag('line'), str(size * 10))
        spacing.set(_tag('lineRule'), 'atLeast')


def _widen_date_column(table, width=2200):
    """날짜 칸이 ’26. 10. 19.(월) 한 줄에 들어가도록 넓히고, 옆 칸을 그만큼 줄입니다."""
    columns = table.findall('w:tblGrid/w:gridCol', NS)
    total = sum(int(column.get(_tag('w'))) for column in columns)
    for column, value in zip(columns, (width, total - width)):
        column.set(_tag('w'), str(value))
    for row in table.findall('w:tr', NS)[1:]:
        for cell, value in zip(row.findall('w:tc', NS), (width, total - width)):
            cell.find('w:tcPr/w:tcW', NS).set(_tag('w'), str(value))


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
        now = seoul_now()
        date = '’' + now.strftime('%y. %m. %d.') + '(' + '월화수목금토일'[now.weekday()] + ')'
        metadata = f'{department} / 담당: {author}' + (f' / 연락처: {contact}' if contact else '')
        for paragraph, text in zip(title.findall('.//w:p', NS), [draft['title'], date, metadata]):
            _replace_text(paragraph, text)
        _fit_title(title.find('.//w:p', NS), draft['title'])
        _widen_date_column(title)
        _allow_growth(title)
        body.append(title)
        _replace_text(overview.find('.//w:p', NS), draft['summary'])
        cell = overview.find('.//w:tc', NS)
        for paragraph in cell.findall('w:p', NS)[1:]:
            cell.remove(paragraph)
        _allow_growth(overview)
        body.append(overview)
        # 검토 요지는 위 요약 상자에 들어가므로 본문에는 다시 쓰지 않습니다.
        # 사업 검토가 없는 구상 보고서는 제안 항목 이름을 '사업 구상·추진 제안'으로 씁니다.
        for key, label in section_labels(not workflow.get('reviews')):
            if key == 'summary':
                continue
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
                _hanging(paragraph, *((580, 580) if lower else (400, 400)))
                body.append(paragraph)
        paragraph = deepcopy(note)
        _replace_text(paragraph, '     ※ 자료 출처: ' + report_source_label(source_note))
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
