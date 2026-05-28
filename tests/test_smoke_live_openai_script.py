from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_live_smoke_script_bootstraps_checkout_imports_without_api_key() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "smoke_live_openai.py"
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("PYTHONPATH", None)

    interpreter = Path("/usr/bin/python3")
    if not interpreter.exists():
        interpreter = Path(sys.executable)

    result = subprocess.run(
        [str(interpreter), str(script)],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload == {
        "ok": False,
        "error": "OPENAI_API_KEY is required for live OpenAI smoke workflow",
    }
