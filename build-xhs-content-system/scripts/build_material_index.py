#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path


MEDIA_DIRECTORIES = ["图片素材", "视频素材", "参考资料"]


def main():
    parser = argparse.ArgumentParser(description="建立根目录素材索引")
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    if not (root / "project.yaml").is_file():
        raise SystemExit(f"不是有效项目目录：{root}")

    lines = ["# 素材索引", "", f"更新时间：{datetime.now().astimezone().isoformat(timespec='seconds')}", ""]
    for directory_name in MEDIA_DIRECTORIES:
        directory = root / directory_name
        lines.extend([f"## {directory_name}", ""])
        files = sorted(path for path in directory.rglob("*") if path.is_file()) if directory.is_dir() else []
        if not files:
            lines.extend(["- 暂无素材", ""])
            continue
        for path in files:
            relative = path.relative_to(root)
            lines.append(f"- `{relative.as_posix()}`｜{path.stat().st_size} bytes")
        lines.append("")

    output = root / "素材索引.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
