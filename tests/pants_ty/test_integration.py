from __future__ import annotations

import hashlib
import http.server
import json
import os
import platform as py_platform
import shutil
import socketserver
import subprocess
import tarfile
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from typing import cast


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = ROOT / "pants-plugins"


def pants_launcher() -> str:
    configured = os.environ.get("PANTS_LAUNCHER")
    if configured:
        return configured

    default_launcher = Path.home() / ".local" / "bin" / "pants"
    if default_launcher.is_file():
        return str(default_launcher)

    path_launcher = shutil.which("pants")
    if path_launcher and "pex_root" not in path_launcher:
        return path_launcher

    raise AssertionError(
        "Could not locate a Pants launcher. Set PANTS_LAUNCHER to the launcher binary path."
    )


def current_platform() -> tuple[str, str]:
    system = py_platform.system().lower()
    machine = py_platform.machine().lower()
    if system == "linux" and machine in {"aarch64", "arm64"}:
        return "linux_arm64", "aarch64-unknown-linux-musl"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux_x86_64", "x86_64-unknown-linux-musl"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos_arm64", "aarch64-apple-darwin"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "macos_x86_64", "x86_64-apple-darwin"
    raise AssertionError(f"Unsupported test platform: {system} {machine}")


class AssetAndRecordServer:
    def __init__(self, asset_dir: Path) -> None:
        self.asset_dir = asset_dir
        self.calls: list[dict[str, list[str]]] = []
        self._httpd: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "AssetAndRecordServer":
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if not self.path.startswith("/asset/"):
                    self.send_error(404)
                    return
                asset_name = self.path.removeprefix("/asset/")
                asset_path = server.asset_dir / asset_name
                if not asset_path.is_file():
                    self.send_error(404)
                    return
                data = asset_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/record":
                    self.send_error(404)
                    return
                length = int(self.headers["Content-Length"])
                payload = cast(
                    dict[str, list[str]],
                    json.loads(self.rfile.read(length).decode()),
                )
                server.calls.append(payload)
                self.send_response(204)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True

        self._httpd = ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._httpd is not None
        self._httpd.shutdown()
        self._httpd.server_close()
        assert self._thread is not None
        self._thread.join()

    @property
    def base_url(self) -> str:
        assert self._httpd is not None
        host = str(self._httpd.server_address[0])
        port = int(self._httpd.server_address[1])
        return f"http://{host}:{port}"


def create_stub_asset(asset_dir: Path, record_url: str) -> tuple[str, str, int]:
    platform_name, archive_platform = current_platform()
    asset_name = f"ty-{archive_platform}.tar.gz"
    staging_dir = asset_dir / f"ty-{archive_platform}"
    staging_dir.mkdir(parents=True)
    stub = staging_dir / "ty"
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            set -eu

            have_src_root=0
            have_lib_root=0
            python_path=""

            for arg in "$@"; do
              case "$arg" in
                --extra-search-path=src/python)
                  have_src_root=1
                  ;;
                --extra-search-path=libs)
                  have_lib_root=1
                  ;;
                --python=*)
                  if [ -n "$python_path" ]; then
                    echo "multiple --python args" >&2
                    exit 22
                  fi
                  python_path="${{arg#--python=}}"
                  ;;
              esac
            done

            if [ "$have_src_root" -ne 1 ] || [ "$have_lib_root" -ne 1 ]; then
              echo "missing source roots" >&2
              exit 21
            fi

            if [ -z "$python_path" ]; then
              echo "missing --python" >&2
              exit 22
            fi

            python_exec="$python_path"
            if [ -d "$python_exec" ]; then
              python_exec="$python_exec/bin/python"
            fi
            if [ ! -x "$python_exec" ]; then
              echo "unusable --python: $python_path" >&2
              exit 24
            fi

            if ! "$python_exec" -c "import colors"; then
              exit 23
            fi

            RECORD_URL="{record_url}" "$python_exec" - "$@" <<'PY'
            import json
            import os
            import sys
            import urllib.request

            urllib.request.urlopen(
                urllib.request.Request(
                    os.environ["RECORD_URL"],
                    data=json.dumps({{"args": sys.argv[1:]}}).encode(),
                    headers={{"Content-Type": "application/json"}},
                )
            ).read()
            PY
            echo "TY_STUB_OK"
            """
        )
    )
    stub.chmod(0o755)

    asset_path = asset_dir / asset_name
    with tarfile.open(asset_path, "w:gz") as tf:
        tf.add(staging_dir, arcname=staging_dir.name)

    return (
        platform_name,
        hashlib.sha256(asset_path.read_bytes()).hexdigest(),
        asset_path.stat().st_size,
    )


def write_fixture_repo(repo_root: Path, *, server_url: str, sha256: str, size: int, platform_name: str) -> None:
    (repo_root / "pants.toml").write_text(
        textwrap.dedent(
            f"""\
            [GLOBAL]
            pants_version = "2.31.0"
            backend_packages = [
              "pants.backend.python",
              "pants_ty",
            ]
            pythonpath = ["{PLUGIN_ROOT}"]

            [source]
            root_patterns = [
              "/src/python",
              "/libs",
            ]

            [python]
            interpreter_constraints = ["==3.11.*"]

            [ty]
            version = "test"
            known_versions = [
              "test|{platform_name}|{sha256}|{size}|{server_url}",
            ]
            """
        )
    )

    (repo_root / "BUILD").write_text(
        'python_requirement(name="ansicolors", requirements=["ansicolors==1.1.8"])\n'
    )

    (repo_root / "libs" / "shared").mkdir(parents=True)
    (repo_root / "libs" / "shared" / "BUILD").write_text('python_sources(name="lib")\n')
    (repo_root / "libs" / "shared" / "util.py").write_text(
        "from __future__ import annotations\n\n\ndef greeting() -> str:\n    return 'hi'\n"
    )

    (repo_root / "src" / "python" / "app").mkdir(parents=True)
    (repo_root / "src" / "python" / "app" / "BUILD").write_text(
        textwrap.dedent(
            """\
            python_sources(
              name="app",
              dependencies=[
                "//:ansicolors",
                "//libs/shared:lib",
              ],
            )
            """
        )
    )
    (repo_root / "src" / "python" / "app" / "main.py").write_text(
        "from __future__ import annotations\n\nimport colors\nfrom shared.util import greeting\n\nprint(colors.green(greeting()))\n"
    )

    (repo_root / "src" / "python" / "skipped").mkdir(parents=True)
    (repo_root / "src" / "python" / "skipped" / "BUILD").write_text(
        textwrap.dedent(
            """\
            python_source(
              name="skip_me",
              source="skip_me.py",
              dependencies=[
                "//:ansicolors",
                "//libs/shared:lib",
              ],
              skip_ty=True,
            )
            """
        )
    )
    (repo_root / "src" / "python" / "skipped" / "skip_me.py").write_text(
        "from __future__ import annotations\n\nimport colors\nfrom shared.util import greeting\n\nprint(colors.green(greeting()))\n"
    )


def run_pants(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PANTS_NO_PANTSD"] = "true"
    return subprocess.run(
        [pants_launcher(), *args],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
    )


class TyIntegrationTest(unittest.TestCase):
    def test_check_runs_ty_with_pants_known_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            asset_dir = tmpdir_path / "assets"
            asset_dir.mkdir()
            with AssetAndRecordServer(asset_dir) as server:
                platform_name, sha256, size = create_stub_asset(
                    asset_dir, f"{server.base_url}/record"
                )
                repo_root = tmpdir_path / "repo"
                repo_root.mkdir()
                write_fixture_repo(
                    repo_root,
                    server_url=f"{server.base_url}/asset/{next(asset_dir.glob('*.tar.gz')).name}",
                    sha256=sha256,
                    size=size,
                    platform_name=platform_name,
                )

                result = run_pants(
                    repo_root,
                    "check",
                    "--only=ty",
                    "src/python/app/main.py",
                )

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(server.calls), 1, result.stdout + result.stderr)
                args = server.calls[0]["args"]
                self.assertIn("--extra-search-path=src/python", args)
                self.assertIn("--extra-search-path=libs", args)
                self.assertTrue(any(arg.startswith("--python=") for arg in args))

    def test_skip_ty_prevents_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            asset_dir = tmpdir_path / "assets"
            asset_dir.mkdir()
            with AssetAndRecordServer(asset_dir) as server:
                platform_name, sha256, size = create_stub_asset(
                    asset_dir, f"{server.base_url}/record"
                )
                repo_root = tmpdir_path / "repo"
                repo_root.mkdir()
                write_fixture_repo(
                    repo_root,
                    server_url=f"{server.base_url}/asset/{next(asset_dir.glob('*.tar.gz')).name}",
                    sha256=sha256,
                    size=size,
                    platform_name=platform_name,
                )

                result = run_pants(
                    repo_root,
                    "check",
                    "--only=ty",
                    "src/python/skipped/skip_me.py",
                )

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(server.calls, [], result.stdout + result.stderr)
