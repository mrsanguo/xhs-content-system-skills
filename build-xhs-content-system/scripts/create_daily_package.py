#!/usr/bin/env python3
import argparse
from datetime import date
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="创建小红书每日待审核内容包")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--format", required=True, choices=["图文", "视频"])
    return parser.parse_args()


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    if not (project_root / "project.yaml").is_file():
        raise SystemExit(f"不是有效项目目录：{project_root}")

    day_dir = project_root / "输出" / args.date
    if day_dir.exists() and any(day_dir.iterdir()):
        raise SystemExit(f"停止：日期目录已有内容，不覆盖：{day_dir}")

    for relative in ["成品/封面", "成品/图文", "成品/视频"]:
        (day_dir / relative).mkdir(parents=True, exist_ok=True)

    write(
        day_dir / "当天选题.md",
        f"# {args.date} 当天选题\n\n- 状态：待审核\n- 内容形式：{args.format}\n- 标题：待生成\n- 栏目：待生成\n- 核心观点：待生成\n- 目标用户：待生成\n- 素材引用：待生成\n- 行动指令：待生成\n",
    )
    write(
        day_dir / "自动生产记录.md",
        f"# 自动生产记录\n\n- 目标日期：{args.date}\n- 状态：待审核\n- 读取文件：待记录\n- 去重依据：待记录\n- 素材引用：待记录\n- 生成文件：待记录\n- 校验结果：待运行\n",
    )
    write(
        day_dir / "成品" / "发布记录.md",
        f"# 发布记录\n\n- 标题：待填写\n- 平台：小红书\n- 内容形式：{args.format}\n- 状态：待审核\n- 计划发布时间：待确认\n- 实际发布时间：\n- 发布链接：\n- 点赞：\n- 收藏：\n- 评论：\n- 私信：\n- 继续沟通：\n- 符合条件：\n- 到访：\n- 付费：\n- 说明：未自动发布\n",
    )
    print(day_dir)


if __name__ == "__main__":
    main()
