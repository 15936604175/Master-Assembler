import sys
import os
import uvicorn

if __name__ == "__main__":
    basedir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(basedir)

    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")