from pathlib import Path

import bpy


def run_convert_to_rigify():
    script_path = Path(__file__).resolve().parent / "auto_rigify_bind_pipeline.py"
    script = script_path.read_text(encoding="utf-8")
    namespace = {
        "__name__": "__main__",
        "__file__": str(script_path),
    }
    exec(compile(script, str(script_path), "exec"), namespace)

