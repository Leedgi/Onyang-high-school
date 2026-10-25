"""새 프로젝트 루트에서 실행. --publish를 지정했을 때만 원격에 올린다."""
import argparse
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BRANCHES = ("feature/a-recognition", "feature/b-analysis", "feature/c-web")


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, encoding="utf-8",
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", help="새 빈 저장소 URL")
    parser.add_argument("--publish", action="store_true", help="main과 세 브랜치를 origin으로 push")
    args = parser.parse_args()
    try:
        if args.remote and (urlsplit(args.remote).username or urlsplit(args.remote).password):
            # SSH의 git@host는 URL 사용자명 검사 대상이 아니다.
            raise ValueError("HTTPS 주소에 토큰·사용자 정보를 넣지 마세요. Git 로그인을 사용하세요.")
        if not (ROOT / ".git").exists():
            git("init", "-b", "main")
        actual_root = Path(git("rev-parse", "--show-toplevel").stdout.strip()).resolve()
        if actual_root != ROOT:
            raise ValueError("독립 프로젝트 폴더에서 실행해 주세요.")
        origin = git("remote", "get-url", "origin", check=False)
        existing_url = origin.stdout.strip() if origin.returncode == 0 else None
        if args.remote and existing_url and args.remote != existing_url:
            raise ValueError("다른 origin이 이미 있습니다. 자동 변경하지 않습니다. 새 프로젝트의 원격을 확인하세요.")
        if args.publish and not (args.remote or existing_url):
            raise ValueError("--publish에는 새 저장소 --remote 주소 또는 기존 origin이 필요합니다.")
        if git("rev-parse", "--verify", "HEAD", check=False).returncode:
            if git("var", "GIT_AUTHOR_IDENT", check=False).returncode:
                raise ValueError("Git 작성자 이름·메일을 먼저 설정하고 다시 실행하세요.")
            git("add", "--", ".")
            git("commit", "-m", "Start student ingredient website with shared contracts")
        elif git("status", "--porcelain").stdout.strip():
            raise ValueError("미커밋 변경이 있습니다. 검토·커밋 후 main에서 다시 실행하세요.")
        if git("branch", "--show-current").stdout.strip() != "main":
            raise ValueError("초기 브랜치 준비는 main에서 실행하세요. 현재 브랜치를 자동 전환하지 않습니다.")
        for branch in BRANCHES:
            if git("show-ref", "--verify", f"refs/heads/{branch}", check=False).returncode:
                git("branch", branch, "main")
        if args.remote and not existing_url:
            git("remote", "add", "origin", args.remote)
        if args.publish:
            git("push", "--atomic", "-u", "origin", "main", *BRANCHES)
        print("준비 완료: main, " + ", ".join(BRANCHES))
        print("원격 저장 완료." if args.publish else "로컬만 준비했습니다. 원격 저장은 --remote URL --publish를 지정하세요.")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        # Git stderr는 자격 증명 포함 URL이 있을 수 있어 그대로 출력하지 않는다.
        message = str(exc) if isinstance(exc, ValueError) else "Git 명령에 실패했습니다. 설치·작성자·로그인·원격 권한·원격 이력을 확인하세요. 강제 푸시는 하지 않았습니다."
        print(message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
