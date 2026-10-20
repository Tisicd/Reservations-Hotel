import os
import pathlib
import subprocess
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.dev.yaml"]

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_RESTART") != "1",
    reason="requiere el stack arriba; ejecutar con RUN_RESTART=1 tras `make up`",
)


def _cid(service: str) -> str:
    r = subprocess.run([*COMPOSE, "ps", "-q", service], cwd=str(ROOT), capture_output=True, text=True)
    return r.stdout.strip()


def _inspect(cid: str, fmt: str) -> str:
    r = subprocess.run(["docker", "inspect", cid, "--format", fmt], capture_output=True, text=True)
    return r.stdout.strip()


def _wait_status(cid: str, status: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _inspect(cid, "{{.State.Health.Status}}") == status:
            return True
        time.sleep(1)
    return False


def _wait_healthy(cid: str, timeout: int = 120) -> bool:
    return _wait_status(cid, "healthy", timeout)


def _signal_matching(cid: str, needle: str, signum: int) -> None:
    code = (
        "import os,glob,sys\n"
        f"needle = {needle.encode()!r}\n"
        "for p in glob.glob('/proc/[0-9]*'):\n"
        "    if p == '/proc/1':\n"
        "        continue\n"
        "    try:\n"
        "        pid = int(p.rsplit('/',1)[1])\n"
        "        if pid == os.getpid():\n"
        "            continue\n"
        "        argv = open(p+'/cmdline','rb').read().split(b'\\0')\n"
        "        if any(needle in a for a in argv):\n"
        f"            os.kill(pid, {signum})\n"
        "    except Exception:\n"
        "        pass\n"
    )
    subprocess.run(["docker", "exec", cid, "python", "-c", code], check=False)


def test_worker_heartbeat_detecta_bloqueo():
    cid = _cid("availability-worker")
    assert cid, "availability-worker no está arriba"
    assert _wait_healthy(cid)
    _signal_matching(cid, "expire_holds", 19)  # SIGSTOP
    assert _wait_status(cid, "unhealthy", timeout=60), "el heartbeat no detectó el bloqueo"
    _signal_matching(cid, "expire_holds", 18)  # SIGCONT
    assert _wait_healthy(cid, timeout=60), "no se recuperó tras reanudar"


KILL_UVICORN = (
    "import os,glob\n"
    "for p in glob.glob('/proc/[0-9]*'):\n"
    "    if p == '/proc/1':\n"
    "        continue\n"
    "    try:\n"
    "        argv = open(p+'/cmdline','rb').read().split(b'\\0')\n"
    "        if any(a == b'uvicorn' or a.endswith(b'/uvicorn') for a in argv):\n"
    "            os.kill(int(p.rsplit('/',1)[1]),9)\n"
    "    except Exception:\n"
    "        pass\n"
)


def test_availability_reinicio_autonomo():
    cid = _cid("availability")
    assert cid, "availability no está arriba"
    assert _wait_healthy(cid)
    before = int(_inspect(cid, "{{.RestartCount}}"))
    subprocess.run(["docker", "exec", cid, "python", "-c", KILL_UVICORN], check=False)
    assert _wait_healthy(cid)
    after = int(_inspect(cid, "{{.RestartCount}}"))
    assert after > before, f"RestartCount no aumentó: {before} -> {after}"


def test_postgres_reinicio_autonomo():
    cid = _cid("postgres")
    assert cid, "postgres no está arriba"
    assert _wait_healthy(cid)
    before = int(_inspect(cid, "{{.RestartCount}}"))
    subprocess.run(["docker", "exec", cid, "pkill", "-9", "-x", "postgres"], check=False)
    assert _wait_healthy(cid)
    after = int(_inspect(cid, "{{.RestartCount}}"))
    assert after > before, f"RestartCount no aumentó: {before} -> {after}"
