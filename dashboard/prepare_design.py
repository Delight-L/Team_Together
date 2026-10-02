"""원본의 화면·스타일·동작을 수정 가능한 파일로 분리하는 일회성 도구."""

from pathlib import Path
import re

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="초기 HTML 분리 도구 (현재 UI 파일을 덮어씁니다)"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="현재 UI 파일을 원본으로 덮어쓰기"
    )
    args = parser.parse_args()
    if not args.overwrite:
        print("일상적인 수정은 dashboard/ui 폴더에서 하세요.")
        print("초기 원본으로 되돌릴 때만 --overwrite 옵션을 지정하세요.")
        return

    BASE = Path(__file__).resolve().parent
    source = (BASE / "isolation-dashboard_260921.html").read_text(encoding="utf-8")
    ui = BASE / "ui"
    ui.mkdir(exist_ok=True)

    # 디자인을 바꾸기 전의 Streamlit 기본 위젯 버전도 보관합니다.
    backup = BASE / "main_native.py"
    if not backup.exists():
        backup.write_text(
            (BASE / "main.py").read_text(encoding="utf-8"), encoding="utf-8"
        )

    style = re.search(r"<style>(.*?)</style>", source, re.S).group(1)
    # Streamlit의 Shadow DOM 안에서 원본 body와 :root 역할을 맡는 컨테이너입니다.
    style = style.replace(":root", ".dashboard-root")
    style = re.sub(r"\bhtml\{", ".dashboard-root{", style)
    style = re.sub(r"\bbody\{", ".dashboard-root{", style)
    style += "\n/* Streamlit 안에서도 원본처럼 화면 높이를 가득 채웁니다. */\n.dashboard-root{width:100%;height:100dvh;overflow:hidden;position:relative;}\n"
    (ui / "style.css").write_text(
        "/* 색·너비·카드·폰트: 원본 HTML의 CSS와 동일합니다. */\n" + style,
        encoding="utf-8",
    )
    body = source.split("<body>", 1)[1].split("<script>", 1)[0]
    fonts = re.search(
        r'<link href="https://fonts.googleapis.com/css2[^>]+>', source
    ).group(0)
    layout = (
        "<!-- 로그인 / 앱 셸 / 오른쪽 챗봇: 원본 화면 구조 -->\n"
        + fonts
        + '\n<div class="dashboard-root" id="dashboard-root">\n'
        + body
        + "\n</div>\n"
    )
    (ui / "layout.html").write_text(layout, encoding="utf-8")

    script = source.split("/* ===== UI ===== */", 1)[1].split("</script>", 1)[0]
    script = script.replace("document.querySelector(s)", "root.querySelector(s)")
    script = script.replace("document.addEventListener(", "listen(")
    script = script.replace(
        "getComputedStyle(document.documentElement)", "getComputedStyle(root)"
    )
    script = script.replace("innerWidth", "root.clientWidth")
    script = script.replace("window._wt", "weightTimer")
    script = script.replace("const ACC=[", "const ORIGINAL_DEMO_ACCOUNTS=[")
    script = script.replace(
        "const S={user:null", "const ACC=BOOT.accounts;\nconst S={user:null"
    )
    script = script.replace("city:'강남구'", "city:Object.keys(GEO)[0]")
    script = script.replace(
        "a.admin?'강남구':a.org", "a.admin?Object.keys(GEO)[0]:a.org"
    )
    script = script.replace("END-365", "MIN_DAY")
    script = script.replace(
        "Math.min(END,toD(S.date)+ +el.dataset.step)",
        "Math.max(MIN_DAY,Math.min(END,toD(S.date)+ +el.dataset.step))",
    )
    script = script.replace(
        "const f1=v=>v.toFixed(1)", "const f1=v=>Number.isFinite(v)?v.toFixed(1):'—'"
    )
    script = script.replace(
        "const dl=d=>",
        "const dl=d=>!Number.isFinite(d)?'<span class=\"flat\">비교 자료 없음</span>':",
    )
    script = script.replace(
        "const dtxt=d=>", "const dtxt=d=>!Number.isFinite(d)?'비교 자료 없음':"
    )

    # 샘플 대상자 생성 함수를 삭제하고 Python에서 읽은 people.csv를 연결합니다.
    people_start = script.index("const PEOPLE={};")
    people_end = script.index("function viewUsers()")
    script = (
        script[:people_start]
        + "const STAT=BOOT.statuses;\nfunction people(city){return BOOT.people[city]||[]}\n"
        + script[people_end:]
    )

    # SVG 시각화 함수는 별도 파일에 모아 추후 교체하기 쉽게 합니다.
    chart_start = script.index("function chartSVG(")
    chart_end = script.index("function trendCard(")
    chart = script[chart_start:chart_end]
    (ui / "charts.js").write_text(
        "/* 파트 3. 위험도 추이 SVG — W/H: 크기, series: 시계열, labels: 가로축.\n * 디자인을 유지하면서 시각화 종류를 바꾸려면 이 함수를 수정하세요. */\n"
        + chart,
        encoding="utf-8",
    )
    script = script[:chart_start] + script[chart_end:]

    # 파트별 주석을 실제 동작 함수 바로 위에 붙입니다.
    notes = {
        "snap": "데이터 조회: 선택 기간의 5개 요인 → 가중 점수 → 이전 대비 변화",
        "menuDef": "왼쪽 메뉴: 그룹·아이콘·표시 이름을 변경할 위치",
        "renderSide": "사이드바: 원본 236px 너비, 접으면 64px",
        "renderTop": "상단: 페이지 제목, 지자체 탭, 집계 기준, 챗봇 버튼",
        "ctrlBar": "조회 조건: 일/월 탭, 기준일, 앞뒤 날짜 이동",
        "mapSVG": "지도: 행정동 SVG 경계, 위험 단계 색, 선택 강조, 숫자 라벨",
        "detailHTML": "선택 지역 카드: 위험 점수, 요인 막대, 안내 문장",
        "trendCard": "추이 카드: 지역 평균·선택 동의 시계열을 charts.js에 전달",
        "rankCard": "순위 카드: 현재 위험 단계 필터를 적용한 상위 8개 동",
        "viewDash": "화면 1. 종합 현황: 지도 + 상세 / 아래 추이 + 우선 확인 순위",
        "viewAnalysis": "화면 2. 동별 분석: 위험도·요인 기여 누적 막대 표",
        "viewUsers": "화면 3. 대상자 관리: people.csv를 상태·동으로 필터링",
        "viewActions": "화면 4. 조치 현황: 미배정·방문 예정·상담 완료·모니터링",
        "viewData": "화면 5. 데이터 연계: 자료 출처와 반영 지표",
        "viewSettings": "화면 6. 위험도 기준: 가중치 슬라이더와 초기화",
        "viewLogs": "화면 7. 관리자 로그: 현재 화면 세션의 접속·조회·질의·설정",
        "answer": "오른쪽 챗봇: 현재 지역·기간·선택 동에 따른 규칙 기반 답변",
        "login": "로그인: 원본의 시연 계정과 소속 일치 확인",
        "logout": "로그아웃: 앱을 숨기고 원본 로그인 화면으로 돌아가기",
        "pick": "지도·순위 클릭: 선택 동을 기억한 뒤 상세·추이를 다시 그리기",
    }
    for name, note in notes.items():
        script = script.replace(
            f"function {name}(", f"\n// ---------- {note} ----------\nfunction {name}("
        )
    script = script.replace(
        "listen('click'",
        "// 파트 8. 클릭 동작: 메뉴·지도·필터·로그아웃을 한곳에서 처리합니다.\nlisten('click'",
    )
    script = script.replace(
        "listen('change'",
        "// 파트 9. 입력 변경: 날짜·월·대상자 행정동 필터\nlisten('change'",
    )
    script = script.replace(
        "listen('input'",
        "// 파트 10. 슬라이더: 가중치 변경 후 다른 화면에서 새 점수 반영\nlisten('input'",
    )
    (ui / "dashboard.js").write_text(
        "// 파트 4~10. 원본 대시보드의 화면 생성 및 사용자 동작\n" + script,
        encoding="utf-8",
    )
    print(
        "Created ui/layout.html, ui/style.css, ui/charts.js, ui/dashboard.js; retained main_native.py"
    )


if __name__ == "__main__":
    main()
