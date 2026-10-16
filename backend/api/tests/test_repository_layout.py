"""저장소 설정 파일은 루트 하나로 관리합니다. 하위 폴더에 같은 종류의 파일이 다시 올라오면 실패합니다."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# 루트에만 두는 파일: 무시 규칙, Git 속성(LFS 포함), 환경 변수 예시
ROOT_ONLY = {'.gitignore', '.gitattributes', '.env.example'}


class RepositoryLayoutTest(unittest.TestCase):
    def test_config_files_live_only_at_root(self):
        try:
            tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files'], capture_output=True, text=True,
                                     encoding='utf-8', check=True).stdout.splitlines()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('git 저장소가 아닌 환경(배포 이미지 등)')
        nested = [path for path in tracked if '/' in path and path.rsplit('/', 1)[1] in ROOT_ONLY]
        self.assertEqual(nested, [], '하위 폴더의 설정 파일은 루트 파일로 합쳐 주세요: ' + ', '.join(nested))


if __name__ == '__main__':
    unittest.main()
