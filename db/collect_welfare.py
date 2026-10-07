"""지자체복지서비스 목록·상세를 PostgreSQL DB2에 정기 수집한다."""
from __future__ import annotations

import argparse
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import requests
from dotenv import load_dotenv
from sqlalchemy import text

from db.db2_welfare import LOCK_ID, WelfareStore

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations"
LOG = logging.getLogger("db2.collect")


class CollectionError(Exception):
    """메시지에 인증키나 요청 URL을 포함하지 않는 오류."""


class BudgetExhausted(CollectionError):
    pass


class ApiError(CollectionError):
    def __init__(self, code):
        self.code = code
        super().__init__(f"API 결과 코드 {code}")


def parse_xml(raw):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise CollectionError("API 응답이 유효한 XML이 아닙니다") from None
    # 네임스페이스가 붙은 XML도 같은 필드로 처리한다.
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    code = root.findtext(".//returnReasonCode") or root.findtext(".//resultCode")
    if code is None:
        raise CollectionError("API 응답에 결과 코드가 없습니다")
    if code.strip() not in {"0", "00", "0000"}:
        raise ApiError(code.strip())
    return root


def xml_value(node):
    if not len(node):
        return (node.text or "").strip()
    result = {}
    for child in node:
        value = xml_value(child)
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(value)
        else:
            result[child.tag] = value
    return result


def parse_list(root):
    try:
        total = int(root.findtext(".//totalCount", ""))
        if total < 0:
            raise ValueError
    except ValueError:
        raise CollectionError("목록 응답의 totalCount가 잘못되었습니다") from None
    items = [xml_value(node) for node in root.findall(".//servList")]
    for item in items:
        if not isinstance(item, dict) or not item.get("servId") or not item.get("servNm"):
            raise CollectionError("목록 항목에 서비스 ID 또는 이름이 없습니다")
    return total, items


def parse_detail(root, service_id):
    # 공식 응답은 response 바로 아래 필드. body 래퍼가 있는 경우도 지원한다.
    container = root if root.find("servId") is not None else root.find(".//body")
    if container is None or container.findtext("servId") != service_id:
        raise CollectionError("상세 응답의 서비스 ID가 요청과 다릅니다")
    payload = xml_value(container)
    if not payload.get("servNm"):
        raise CollectionError("상세 응답에 서비스 이름이 없습니다")
    return payload


def parse_date(value):
    if not value or value in {"00000000", "99999999"}:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise CollectionError("사업 시행일 형식이 잘못되었습니다")


class WelfareApi:
    def __init__(self, key, reserve, interval=0.3, retries=2, session=None):
        self.key = unquote(key.strip())  # requests가 인코딩하므로 이중 인코딩 방지
        self.reserve = reserve
        self.interval = interval
        self.retries = retries
        self.session = session or requests.Session()
        self.last_request = None

    def get(self, operation, **params):
        for attempt in range(self.retries + 1):
            if not self.reserve():
                raise BudgetExhausted("오늘의 API 호출 예산을 모두 사용했습니다")
            if self.last_request is not None:
                time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.session.get(f"{ENDPOINT}/{operation}",
                    params={"serviceKey": self.key, **params}, timeout=(10, 45))
                if response.status_code == 429 or response.status_code >= 500:
                    raise ApiError(f"HTTP_{response.status_code}")
                if response.status_code != 200:
                    raise ApiError(f"HTTP_{response.status_code}")
                # XML 선언 인코딩에 따라 파싱한다. 원문은 UTF-8 API 응답 그대로 보관한다.
                root = parse_xml(response.content)
                return root, response.content.decode("utf-8-sig")
            except ApiError as exc:
                retryable = exc.code in {"01", "04", "05", "23", "HTTP_429"} or exc.code.startswith("HTTP_5")
                if not retryable or attempt == self.retries:
                    raise
            except (requests.Timeout, requests.ConnectionError):
                if attempt == self.retries:
                    raise CollectionError("API 연결 실패 또는 응답 시간 초과") from None
            except requests.RequestException:
                raise CollectionError("API 요청 실패") from None
            if attempt < self.retries:
                time.sleep(2 ** attempt)
        raise CollectionError("API 요청 실패")


def collect(store, api, run_id, province="", district="", rows=100,
            refresh_days=7, max_details=900, max_pages=None):
    lists = details = errors = 0
    total = None
    status = "failed"
    error = None
    try:
        page = 1
        seen = set()
        while True:
            params = dict(pageNo=page, numOfRows=rows)
            if province:
                params["ctpvNm"] = province
            if district:
                params["sggNm"] = district
            root, raw = api.get("LcgvWelfarelist", **params)
            page_total, items = parse_list(root)
            if total is not None and page_total != total:
                raise CollectionError("수집 중 전체 건수가 변경되었습니다. 다음 실행에서 다시 확인합니다")
            total = page_total
            for item in items:
                if province and item.get("ctpvNm") != province:
                    raise CollectionError("목록 응답의 시도명이 검색 조건과 다릅니다")
                if district and item.get("sggNm") != district:
                    raise CollectionError("목록 응답의 시군구명이 검색 조건과 다릅니다")
                if item["servId"] in seen:
                    raise CollectionError("목록 페이지에 중복 서비스 ID가 있습니다")
                seen.add(item["servId"])
            if not items and len(seen) < total:
                raise CollectionError("목록 수집 중 예상보다 일찍 빈 페이지가 반환되었습니다")
            store.save_list(run_id, items, raw)
            lists += len(items)
            LOG.info("목록 %s페이지 저장: %s건 / 전체 %s건", page, len(items), total)
            if len(seen) >= total or (max_pages and page >= max_pages):
                break
            page += 1
        for service_id in store.candidates(province, district, refresh_days, max_details):
            try:
                root, raw = api.get("LcgvWelfaredetailed", servId=service_id)
                payload = parse_detail(root, service_id)
                dates = (parse_date(payload.get("enfcBgngYmd")), parse_date(payload.get("enfcEndYmd")))
                if dates[0] and dates[1] and dates[0] > dates[1]:
                    raise CollectionError("사업 시행 시작일이 종료일보다 늦습니다")
                store.save_detail(run_id, service_id, payload, raw, dates)
                details += 1
            except BudgetExhausted:
                raise
            except CollectionError as exc:
                errors += 1
                store.detail_failed(service_id, str(exc))
                LOG.warning("상세 실패 %s: %s", service_id, exc)
                # 인증·호출한도 오류는 나머지 서비스에 반복하지 않는다.
                if isinstance(exc, ApiError) and exc.code in {"20", "22", "29", "30", "31", "12", "HTTP_401", "HTTP_403"}:
                    raise
        status = "partial" if errors else "completed"
    except BudgetExhausted as exc:
        status, error = "budget_exhausted", str(exc)
    except CollectionError as exc:
        error = str(exc)
        errors += 1
    except Exception:
        error = "DB 저장 또는 수집 처리 실패. 연결 설정과 테이블 권한을 확인하세요"
        errors += 1
    finally:
        store.finish_run(run_id, status, lists, details, errors, total, error)
    LOG.info("수집 결과: %s, 목록 %s, 상세 %s, 오류 %s", status, lists, details, errors)
    if error:
        LOG.warning("%s", error)
    return status


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("1 이상이어야 합니다")
    return number


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "collect"])
    parser.add_argument("--province", default=os.getenv("DB2_WELFARE_PROVINCE", ""))
    parser.add_argument("--district", default=os.getenv("DB2_WELFARE_DISTRICT", ""))
    parser.add_argument("--rows", type=positive, default=100)
    parser.add_argument("--daily-budget", type=positive, default=int(os.getenv("DB2_WELFARE_DAILY_BUDGET", "900")))
    parser.add_argument("--refresh-days", type=positive, default=7)
    parser.add_argument("--max-details", type=positive, default=900)
    parser.add_argument("--max-pages", type=positive, help="검증용 목록 페이지 제한")
    args = parser.parse_args()
    if args.district and not args.province:
        parser.error("--district 지정 시 --province도 필요합니다")
    key = os.getenv("DB2_WELFARE_API_KEY") or os.getenv("DATA_API_KEY", "")
    if args.command == "collect" and not key.strip():
        parser.error(".env에 DB2_WELFARE_API_KEY 또는 DATA_API_KEY를 설정하세요")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from db.connection import engine
    try:
        # 세션 advisory lock: 별도 프로세스와 스케줄의 중복 실행을 방지한다.
        with engine.connect() as lock:
            acquired = lock.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}).scalar_one()
            lock.commit()
            if not acquired:
                LOG.info("다른 DB2 수집기가 실행 중이므로 종료합니다")
                return 0
            try:
                store = WelfareStore(engine)
                store.initialize()
                if args.command == "init":
                    LOG.info("DB2 복지 수집 테이블 준비 완료")
                    return 0
                scope = f"{args.province}/{args.district}" if args.province else "nationwide"
                run_id = store.start_run(scope, args.daily_budget)
                with requests.Session() as session:
                    api = WelfareApi(key, lambda: store.reserve_call(run_id, args.daily_budget), session=session)
                    status = collect(store, api, run_id, args.province, args.district,
                        args.rows, args.refresh_days, args.max_details, args.max_pages)
                return 0 if status in {"completed", "budget_exhausted"} else 1
            finally:
                lock.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
                lock.commit()
    except Exception:
        LOG.error("DB2 실행 실패. DB 연결 설정과 테이블 권한을 확인하세요")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
