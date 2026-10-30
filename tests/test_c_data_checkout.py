"""Windows autocrlf checkout에서도 검토 데이터 바이트를 보존한다."""
import subprocess
from core.database import ROOT


def test_reviewed_csv_json_checkout_uses_lf_even_with_autocrlf():
    files = sorted(str(p.relative_to(ROOT)).replace('\\', '/')
                   for suffix in ('*.csv', '*.json') for p in (ROOT/'data').rglob(suffix))
    result = subprocess.run(['git', '-c', 'core.autocrlf=true', 'check-attr', 'eol', '--', *files],
                            cwd=ROOT, check=True, capture_output=True, text=True)
    assert len(result.stdout.splitlines()) == len(files)
    assert all(line.endswith(': eol: lf') for line in result.stdout.splitlines())
    assert all(b'\r\n' not in (ROOT/file).read_bytes() for file in files)
