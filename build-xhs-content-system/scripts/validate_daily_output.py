#!/usr/bin/env python3
import argparse
import json
import struct
from pathlib import Path


REQUIRED_FILES = ["当天选题.md", "自动生产记录.md", "成品/发布记录.md"]
REQUIRED_DIRECTORIES = ["成品/封面", "成品/图文", "成品/视频"]


def png_size(path: Path):
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"不是有效 PNG：{path}")
    return struct.unpack(">II", header[16:24])


def validate_cover(project_root: Path, day_dir: Path, errors: list[str]):
    spec_path = day_dir / "成品" / "封面" / "cover.json"
    if not spec_path.is_file():
        errors.append("图文内容缺少成品/封面/cover.json")
        return
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"cover.json 无法读取：{exc}")
        return

    title = str(spec.get("title", "")).strip()
    if not title or len(title) > 20:
        errors.append("封面标题必须为 1—20 个字符")
    generator = str(spec.get("generator", "local-renderer"))
    if generator not in {"local-renderer", "external-skill"}:
        errors.append(f"不支持的封面生成方式：{generator}")
    theme_path = (project_root / str(spec.get("theme", "视觉模板/cover-theme.json"))).resolve()
    if project_root != theme_path and project_root not in theme_path.parents:
        errors.append("封面视觉配置路径越出项目根目录")
    elif not theme_path.is_file():
        errors.append(f"封面视觉配置不存在：{theme_path}")
    else:
        try:
            theme = json.loads(theme_path.read_text(encoding="utf-8"))
            if theme.get("status") != "confirmed":
                errors.append("封面视觉配置尚未确认")
            configured_generator = str(theme.get("generation", {}).get("method", "pending"))
            if configured_generator != generator:
                errors.append("cover.json 与项目视觉配置的生成方式不一致")
            if generator == "external-skill":
                expected_skill = str(theme.get("generation", {}).get("generator_skill", "")).strip()
                actual_skill = str(spec.get("generator_skill", "")).strip()
                if not actual_skill:
                    errors.append("外部封面缺少 generator_skill")
                elif expected_skill and expected_skill != actual_skill:
                    errors.append("cover.json 使用的外部 Skill 与项目视觉配置不一致")
        except Exception as exc:
            errors.append(f"封面视觉配置无法读取：{exc}")
    if generator == "local-renderer":
        source = (project_root / str(spec.get("source_image", ""))).resolve()
        if project_root != source and project_root not in source.parents:
            errors.append("封面引用的素材路径越出项目根目录")
        elif not source.is_file():
            errors.append(f"封面引用的根目录素材不存在：{source}")
    output = (day_dir / str(spec.get("output", ""))).resolve()
    if day_dir != output and day_dir not in output.parents:
        errors.append("封面输出路径越出当天日期目录")
    elif not output.is_file():
        errors.append(f"封面 PNG 不存在：{output}")
    else:
        try:
            size = png_size(output)
            if generator == "local-renderer" and size != (1080, 1440):
                errors.append(f"本地模板封面尺寸不是 1080×1440：{size}")
            if generator == "external-skill":
                width, height = size
                if width * 4 != height * 3 or width < 900 or height < 1200:
                    errors.append(f"外部 Skill 封面不是清晰的 3:4 竖版：{size}")
        except ValueError as exc:
            errors.append(str(exc))


def main():
    parser = argparse.ArgumentParser(description="校验每日小红书内容包")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--date", required=True)
    parser.add_argument("--scaffold-only", action="store_true")
    args = parser.parse_args()
    project_root = args.project_root.expanduser().resolve()
    day_dir = project_root / "输出" / args.date
    errors = []

    for relative in REQUIRED_FILES:
        if not (day_dir / relative).is_file():
            errors.append(f"缺少文件：{relative}")
    for relative in REQUIRED_DIRECTORIES:
        if not (day_dir / relative).is_dir():
            errors.append(f"缺少目录：{relative}")

    selection = day_dir / "当天选题.md"
    production_record = day_dir / "自动生产记录.md"
    publish_record = day_dir / "成品" / "发布记录.md"
    selection_text = selection.read_text(encoding="utf-8") if selection.is_file() else ""
    production_text = production_record.read_text(encoding="utf-8") if production_record.is_file() else ""
    publish_text = publish_record.read_text(encoding="utf-8") if publish_record.is_file() else ""

    if "待审核" not in selection_text or "待审核" not in publish_text:
        errors.append("选题或发布记录缺少“待审核”状态")
    if "未自动发布" not in publish_text:
        errors.append("发布记录缺少“未自动发布”说明")

    if not args.scaffold_only:
        if "待生成" in selection_text or "待生成" in production_text or "待填写" in publish_text:
            errors.append("选题、自动生产记录或发布记录仍包含未完成占位")

        graphic_files = list((day_dir / "成品" / "图文").glob("*.md"))
        video_files = list((day_dir / "成品" / "视频").glob("*.md"))
        if "内容形式：图文" in selection_text:
            if len(graphic_files) != 1 or video_files:
                errors.append(
                    f"图文任务应有且只有一个图文成品、没有视频成品；当前图文 {len(graphic_files)}，视频 {len(video_files)}"
                )
            validate_cover(project_root, day_dir, errors)
        elif "内容形式：视频" in selection_text:
            if len(video_files) != 1 or graphic_files:
                errors.append(
                    f"视频任务应有且只有一个视频成品、没有图文成品；当前视频 {len(video_files)}，图文 {len(graphic_files)}"
                )
            if (day_dir / "成品" / "封面" / "cover.json").is_file():
                validate_cover(project_root, day_dir, errors)
        else:
            errors.append("无法识别内容形式")

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"PASS: {day_dir}")


if __name__ == "__main__":
    main()
