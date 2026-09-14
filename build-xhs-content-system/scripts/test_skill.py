#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"
FORBIDDEN_PROJECT_TERMS = ["OPC", "郑州", "工位", "国哥"]


def run(*args, expect_success=True):
    result = subprocess.run(
        [str(arg) for arg in args],
        text=True,
        capture_output=True,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(f"命令失败：{' '.join(map(str, args))}\n{result.stdout}\n{result.stderr}")
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"命令本应失败：{' '.join(map(str, args))}")
    return result


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def assert_no_cross_project_terms(project: Path):
    suffixes = {".md", ".yaml", ".yml", ".json", ".py", ".sh", ".csv"}
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        content = path.read_text(encoding="utf-8")
        for term in FORBIDDEN_PROJECT_TERMS:
            if term in content:
                raise AssertionError(f"跨项目残留：{term} 出现在 {path}")


def main():
    test_root = Path(tempfile.mkdtemp(prefix="xhs-cross-industry-test-"))
    project = test_root / "pet-nutrition"
    skill_name = "pet-nutrition-xhs-daily-producer"
    target_date = "2026-09-15"

    run(
        sys.executable,
        SCRIPTS / "init_project.py",
        "--project-root",
        project,
        "--project-name",
        "小满宠物营养",
        "--industry",
        "宠物营养咨询",
        "--account-name",
        "小满讲猫饭",
        "--daily-skill-name",
        skill_name,
    )
    daily_skill = project / "skills" / skill_name
    if not daily_skill.is_dir() or (project / "skills" / "project-daily-producer").exists():
        raise AssertionError("没有正确生成项目专属每日生产 Skill")
    if f"name: {skill_name}" not in (daily_skill / "SKILL.md").read_text(encoding="utf-8"):
        raise AssertionError("项目专属 Skill 的 frontmatter 名称没有更新")
    agent_config = (daily_skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
    if f"${skill_name}" not in agent_config or "allow_implicit_invocation: true" not in agent_config:
        raise AssertionError("项目专属 Skill 的 UI 元数据没有完成实例化")

    run(sys.executable, daily_skill / "scripts" / "validate_project.py", "--project-root", project)
    assert_no_cross_project_terms(project)

    sample_image = project / "图片素材" / "cat-meal.jpg"
    sample_image.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 1600), (205, 221, 196)).save(sample_image, quality=90)
    run(sys.executable, daily_skill / "scripts" / "build_material_index.py", "--project-root", project)
    run(
        sys.executable,
        daily_skill / "scripts" / "create_daily_package.py",
        "--project-root",
        project,
        "--date",
        target_date,
        "--format",
        "图文",
    )

    day = project / "输出" / target_date
    write(
        day / "当天选题.md",
        "# 2026-09-15 当天选题\n\n- 状态：待审核\n- 内容形式：图文\n- 标题：猫咪减肥别只减粮\n- 栏目：喂养误区\n- 核心观点：先判断热量来源再调整食量\n- 目标用户：正在控制猫咪体重的养宠人\n- 素材引用：图片素材/cat-meal.jpg\n- 行动指令：评论猫咪年龄和体重\n",
    )
    write(
        day / "自动生产记录.md",
        "# 自动生产记录\n\n- 目标日期：2026-09-15\n- 状态：待审核\n- 读取文件：项目定位、内容方案、视觉规范\n- 去重依据：最近 14 天没有相同主题\n- 素材引用：图片素材/cat-meal.jpg\n- 生成文件：图文、封面、发布记录\n- 校验结果：完成后运行\n",
    )
    write(
        day / "成品" / "图文" / "01-猫咪减肥别只减粮.md",
        "# 猫咪减肥别只减粮\n\n猫咪体重超标时，直接把猫粮砍半并不稳妥。先记录一周主粮、零食和罐头，再根据年龄、体况和活动量逐步调整。真正需要控制的是总热量，不是让猫挨饿。\n\n#科学养宠 #猫咪饮食 #宠物营养 #养猫经验 #猫咪减肥\n",
    )
    write(
        day / "成品" / "发布记录.md",
        "# 发布记录\n\n- 标题：猫咪减肥别只减粮\n- 平台：小红书\n- 内容形式：图文\n- 状态：待审核\n- 计划发布时间：待确认\n- 实际发布时间：\n- 发布链接：\n- 数据：\n- 说明：未自动发布\n",
    )
    cover_spec = {
        "generator": "local-renderer",
        "title": "猫咪减肥别只减粮",
        "title_lines": ["猫咪减肥", "别只减粮"],
        "subtitle": "先看总热量，再调整食量",
        "source_image": "图片素材/cat-meal.jpg",
        "output": "成品/封面/01-猫咪减肥别只减粮.png",
        "layout": "editorial-cards",
    }
    write(day / "成品" / "封面" / "cover.json", json.dumps(cover_spec, ensure_ascii=False, indent=2))

    unconfirmed = run(
        sys.executable,
        daily_skill / "scripts" / "render_cover.py",
        "--spec",
        day / "成品" / "封面" / "cover.json",
        expect_success=False,
    )
    if "视觉尚未确认" not in unconfirmed.stderr:
        raise AssertionError("视觉未确认时没有正确停止")

    theme_path = project / "视觉模板" / "cover-theme.json"
    theme = json.loads(theme_path.read_text(encoding="utf-8"))
    theme["status"] = "confirmed"
    theme["placeholder_only"] = False
    theme["generation"]["method"] = "local-renderer"
    write(theme_path, json.dumps(theme, ensure_ascii=False, indent=2))
    project_config = project / "project.yaml"
    config_text = project_config.read_text(encoding="utf-8")
    config_text = config_text.replace('visual_status: "待确认"', 'visual_status: "confirmed"')
    config_text = config_text.replace('  method: "external-skill"', '  method: "local-renderer"')
    config_text = config_text.replace('  generator_skill: "gzh-cover-generator"', '  generator_skill: ""')
    write(project_config, config_text)
    run(sys.executable, daily_skill / "scripts" / "validate_project.py", "--project-root", project)
    run(
        sys.executable,
        daily_skill / "scripts" / "render_cover.py",
        "--spec",
        day / "成品" / "封面" / "cover.json",
    )
    run(
        sys.executable,
        daily_skill / "scripts" / "validate_daily_output.py",
        "--project-root",
        project,
        "--date",
        target_date,
    )

    theme["generation"]["method"] = "external-skill"
    theme["generation"]["generator_skill"] = "gzh-cover-generator"
    write(theme_path, json.dumps(theme, ensure_ascii=False, indent=2))
    external_method_block = run(
        sys.executable,
        daily_skill / "scripts" / "render_cover.py",
        "--spec",
        day / "成品" / "封面" / "cover.json",
        expect_success=False,
    )
    if "没有选择 local-renderer" not in external_method_block.stderr:
        raise AssertionError("选择外部 Skill 后，本地渲染器没有正确停止")
    theme["generation"]["method"] = "local-renderer"
    theme["generation"]["generator_skill"] = ""
    write(theme_path, json.dumps(theme, ensure_ascii=False, indent=2))

    no_overwrite = run(
        sys.executable,
        daily_skill / "scripts" / "create_daily_package.py",
        "--project-root",
        project,
        "--date",
        target_date,
        "--format",
        "图文",
        expect_success=False,
    )
    if "不覆盖" not in no_overwrite.stderr:
        raise AssertionError("已有日期目录时没有正确阻止覆盖")

    assert_no_cross_project_terms(project)
    print("PASS: 通用搭建器、项目专属 Skill、封面门槛、内容包校验和跨行业隔离均通过")
    print(f"TEST_ARTIFACT: {project}")


if __name__ == "__main__":
    main()
