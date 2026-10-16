"""Retired importer: never discard steps or silently relabel database evidence."""
import sys


def main() -> int:
    print('사용 중지: 기존 가져오기는 steps를 버리고 DB 해시만 변경했습니다. 파일은 변경하지 않았습니다. 같은 폴더의 prepare_dataset32.py를 실행하여 DB 근거 검증과 모든 단계 보존을 수행하세요.', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
