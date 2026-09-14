#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "project.yaml",
    "当前进度.md",
    "账号定位与商业方案.md",
    "账号包装方案.md",
    "内容策划方案.md",
    "视觉规范.md",
    "私信与评论话术.md",
    "输出/README.md",
    "数据复盘/发布数据.csv",
    "视觉模板/cover-theme.json",
]
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
REQUIRED_KEYS = [
    "project_name",
    "platform",
    "industry",
    "account_name",
    "current_positioning",
    "long_term_direction",
    "target_audience",
    "offer",
    "content_pillars",
    "cta",
    "public_boundaries",
    "visual_status",
    "visual_generation",
    "daily_producer",
]


def main():
    parser = argparse.ArgumentParser(description="校验小红书内容项目结构")
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    errors = []

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"缺少文件：{relative}")
    for relative in REQUIRED_DIRECTORIES:
        if not (root / relative).is_dir():
            errors.append(f"缺少目录：{relative}")

    config = root / "project.yaml"
    if config.is_file():
        content = config.read_text(encoding="utf-8")
        for key in REQUIRED_KEYS:
            if not re.search(rf"(?m)^{re.escape(key)}\s*:", content):
                errors.append(f"project.yaml 缺少字段：{key}")

        skill_path_match = re.search(
            r'(?m)^\s+skill_path\s*:\s*["\']?([^"\'\n]+)', content
        )
        if not skill_path_match:
            errors.append("project.yaml 缺少 daily_producer.skill_path")
        else:
            skill_path = skill_path_match.group(1).strip()
            skill_dir = (root / skill_path).resolve()
            if root != skill_dir and root not in skill_dir.parents:
                errors.append("daily_producer.skill_path 越出项目根目录")
                skill_dir = root / "__invalid_daily_skill_path__"
            required_skill_files = [
                "SKILL.md",
                "agents/openai.yaml",
                "scripts/build_material_index.py",
                "scripts/create_daily_package.py",
                "scripts/render_cover.py",
                "scripts/render_cover.sh",
                "scripts/run_daily.sh",
                "scripts/validate_daily_output.py",
            ]
            for relative in required_skill_files:
                if not (skill_dir / relative).is_file():
                    errors.append(f"项目专属 Skill 缺少文件：{skill_path}/{relative}")

        status_match = re.search(r'(?m)^visual_status\s*:\s*["\']?([^"\'\n]+)', content)
        method_match = re.search(
            r'(?ms)^visual_generation\s*:\s*\n(?P<body>(?:[ \t]+.*\n)*)', content
        )
        method_value = ""
        generator_skill_value = ""
        if method_match:
            nested_method = re.search(
                r'(?m)^\s+method\s*:\s*["\']?([^"\'\n]+)', method_match.group("body")
            )
            method_value = nested_method.group(1).strip() if nested_method else ""
            nested_generator_skill = re.search(
                r'(?m)^\s+generator_skill\s*:\s*["\']?([^"\'\n]*)',
                method_match.group("body"),
            )
            generator_skill_value = (
                nested_generator_skill.group(1).strip() if nested_generator_skill else ""
            )
        if not method_value:
            errors.append("project.yaml 缺少 visual_generation.method")
        elif method_value not in {"待确认", "pending", "external-skill", "local-renderer"}:
            errors.append(f"visual_generation.method 不支持：{method_value}")

        status_value = status_match.group(1).strip() if status_match else ""
        theme_path = root / "视觉模板" / "cover-theme.json"
        if theme_path.is_file():
            try:
                theme = json.loads(theme_path.read_text(encoding="utf-8"))
                theme_method = str(theme.get("generation", {}).get("method", "pending"))
                theme_generator_skill = str(
                    theme.get("generation", {}).get("generator_skill", "")
                ).strip()
                if status_value in {"confirmed", "已确认"}:
                    if method_value not in {"external-skill", "local-renderer"}:
                        errors.append("视觉已确认，但没有选择有效的封面生成方式")
                    if theme.get("status") != "confirmed":
                        errors.append("project.yaml 视觉已确认，但 cover-theme.json 尚未确认")
                    if theme_method != method_value:
                        errors.append("project.yaml 与 cover-theme.json 的封面生成方式不一致")
                    if theme.get("placeholder_only", True):
                        errors.append("视觉已确认，但 cover-theme.json 仍是测试占位模板")
                    if method_value == "external-skill":
                        if not generator_skill_value or not theme_generator_skill:
                            errors.append("选择 external-skill 时必须填写 generator_skill")
                        elif generator_skill_value != theme_generator_skill:
                            errors.append(
                                "project.yaml 与 cover-theme.json 的 generator_skill 不一致"
                            )
            except Exception as exc:
                errors.append(f"cover-theme.json 无法读取：{exc}")

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"PASS: {root}")


if __name__ == "__main__":
    main()
