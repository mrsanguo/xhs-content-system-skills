#!/usr/bin/env python3
import argparse
import re
import shutil
from datetime import date
from pathlib import Path


TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".csv", ".txt"}
REQUIRED_DIRECTORIES = [
    "图片素材",
    "视频素材",
    "参考资料",
    "参考资料/视觉对标",
    "视觉模板",
    "自动化日志",
    "输出",
    "数据复盘/周复盘",
]
PROJECT_SCRIPT_NAMES = [
    "build_material_index.py",
    "create_daily_package.py",
    "render_cover.py",
    "render_cover.sh",
    "validate_daily_output.py",
    "validate_project.py",
    "run_daily.sh",
]


def parse_args():
    parser = argparse.ArgumentParser(description="初始化通用小红书内容项目")
    parser.add_argument("--project-root", required=True, type=Path, help="新项目完整路径")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--industry", required=True)
    parser.add_argument("--account-name", default="待确认")
    parser.add_argument("--platform", default="小红书")
    parser.add_argument(
        "--daily-skill-name",
        default="project-daily-producer",
        help="项目专属每日生产 Skill 名称，只能使用小写字母、数字和连字符",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    target = args.project_root.expanduser().resolve()
    template = Path(__file__).resolve().parent.parent / "assets" / "project-template"
    daily_skill_name = args.daily_skill_name.strip()

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", daily_skill_name):
        raise SystemExit(f"每日生产 Skill 名称不合法：{daily_skill_name}")

    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"停止：目标目录非空，不覆盖已有内容：{target}")
    if not template.is_dir():
        raise SystemExit(f"模板不存在：{template}")

    target.mkdir(parents=True, exist_ok=True)
    for item in template.iterdir():
        if item.name == "skills":
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)

    for relative in REQUIRED_DIRECTORIES:
        (target / relative).mkdir(parents=True, exist_ok=True)

    daily_template = template / "skills" / "project-daily-producer"
    daily_skill_dir = target / "skills" / daily_skill_name
    if not daily_template.is_dir():
        raise SystemExit(f"每日生产模板不存在：{daily_template}")
    shutil.copytree(daily_template, daily_skill_dir)

    source_scripts = Path(__file__).resolve().parent
    project_scripts = daily_skill_dir / "scripts"
    project_scripts.mkdir(parents=True, exist_ok=True)
    for script_name in PROJECT_SCRIPT_NAMES:
        shutil.copy2(source_scripts / script_name, project_scripts / script_name)

    replacements = {
        "{{PROJECT_NAME}}": args.project_name.strip(),
        "{{INDUSTRY}}": args.industry.strip(),
        "{{ACCOUNT_NAME}}": args.account_name.strip(),
        "{{PLATFORM}}": args.platform.strip(),
        "{{CREATED_DATE}}": date.today().isoformat(),
        "{{DAILY_SKILL_NAME}}": daily_skill_name,
    }
    for path in target.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            content = path.read_text(encoding="utf-8")
            for source, value in replacements.items():
                content = content.replace(source, value)
            path.write_text(content, encoding="utf-8")

    skill_file = daily_skill_dir / "SKILL.md"
    skill_content = skill_file.read_text(encoding="utf-8")
    skill_content = re.sub(
        r"(?m)^name:\s*project-daily-producer\s*$",
        f"name: {daily_skill_name}",
        skill_content,
        count=1,
    )
    skill_file.write_text(skill_content, encoding="utf-8")

    agent_file = daily_skill_dir / "agents" / "openai.yaml"
    agent_content = agent_file.read_text(encoding="utf-8")
    agent_content = agent_content.replace(
        "allow_implicit_invocation: false", "allow_implicit_invocation: true"
    )
    agent_file.write_text(agent_content, encoding="utf-8")

    print(target)
    print(f"DAILY_SKILL: {daily_skill_dir}")


if __name__ == "__main__":
    main()
