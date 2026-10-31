"""실제 인터프리터/가상환경으로 재사용·손상 환경 백업·재시도를 검사한다."""
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.setup_windows_env import compatible, ensure_environment, environment_python

pytestmark = pytest.mark.skipif(sys.version_info[:2] != (3, 14), reason='Python 3.14 environment migration checks')


def test_environment_is_created_and_reused_without_replacing_user_marker(tmp_path):
    project=tmp_path/'project with spaces';project.mkdir()
    target=ensure_environment(project)
    marker=target/'user-marker.txt';marker.write_text('preserve me')
    assert compatible(target)
    assert ensure_environment(project)==target
    assert marker.read_text()=='preserve me'
    assert not (project/'.venv-backups').exists()
    result=subprocess.run([str(environment_python(target)),'-c','import sys;print(sys.version_info[:2])'],capture_output=True,text=True,check=True)
    assert '(3, 14)' in result.stdout


def test_incompatible_environment_is_preserved_and_retry_reuses_new_environment(tmp_path):
    project=tmp_path/'project with spaces';project.mkdir()
    old=project/'.venv';old.mkdir();(old/'old-work.txt').write_text('do not delete')
    model=project/'.cache/model';model.mkdir(parents=True);(model/'weights').write_bytes(b'model fixture')
    target=ensure_environment(project)
    backups=list((project/'.venv-backups').iterdir())
    assert len(backups)==1 and (backups[0]/'old-work.txt').read_text()=='do not delete'
    assert compatible(target)
    ensure_environment(project)
    assert len(list((project/'.venv-backups').iterdir()))==1
    assert (model/'weights').read_bytes()==b'model fixture'
