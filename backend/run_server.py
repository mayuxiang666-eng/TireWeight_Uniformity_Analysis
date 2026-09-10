# -*- coding: utf-8 -*-
import os
import sys

# Ensure UTF-8 output across all Windows consoles and NSSM service sessions
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure project root is always in sys.path
CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURR_DIR).lower() == "backend":
    ROOT_DIR = os.path.dirname(CURR_DIR)
else:
    ROOT_DIR = CURR_DIR

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import uvicorn

if __name__ == "__main__":
    is_service = os.environ.get("NSSM_SERVICE", "0") == "1"
    # When running interactively in local dev, reload defaults to True;
    # When running under NSSM production service, reload defaults to False (restart handled cleanly by NSSM)
    reload_env = os.environ.get("FASTAPI_RELOAD", "0" if is_service else "1")
    should_reload = reload_env.lower() in ("1", "true", "yes")

    print(f"[INFO] Starting FastAPI backend on 0.0.0.0:8000 (reload={should_reload}, service={is_service})...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=should_reload)
