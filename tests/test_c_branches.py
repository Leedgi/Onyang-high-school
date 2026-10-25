import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_three_branches_publish_and_idempotence(tmp_path):
    project = tmp_path / "new project"
    (project / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/bootstrap_branches.py", project / "scripts/bootstrap_branches.py")
    (project / "README.md").write_text("Student project", encoding="utf-8")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="Branch Test", GIT_AUTHOR_EMAIL="test@example.invalid",
               GIT_COMMITTER_NAME="Branch Test", GIT_COMMITTER_EMAIL="test@example.invalid")

    def run(*args):
        return subprocess.run([sys.executable, "scripts/bootstrap_branches.py", *args], cwd=project,
                              env=env, capture_output=True, text=True)

    first = run("--remote", str(remote), "--publish")
    assert first.returncode == 0, first.stdout + first.stderr
    refs = subprocess.run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"],
                          cwd=remote, capture_output=True, text=True, check=True).stdout.splitlines()
    assert sorted(refs) == ["feature/a-recognition", "feature/b-analysis", "feature/c-web", "main"]
    assert run("--remote", str(remote), "--publish").returncode == 0
    assert run("--remote", str(tmp_path / "other.git")).returncode == 1
    (project / "README.md").write_text("Uncommitted work", encoding="utf-8")
    assert run().returncode == 1
