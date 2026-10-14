"""File copy tool. Also runs by itself with CLI arguments."""
import argparse
import json
import shutil
from pathlib import Path

def run(source: str, destination: str, overwrite: bool = False):
    src, dst = Path(source), Path(destination)
    if not src.is_file():
        raise FileNotFoundError("Source file not found")
    if dst.exists() and not overwrite:
        raise FileExistsError("Destination exists; overwrite disabled")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"source": str(src), "destination": str(dst)}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--destination", required=True)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.source, a.destination, a.overwrite), ensure_ascii=False))
