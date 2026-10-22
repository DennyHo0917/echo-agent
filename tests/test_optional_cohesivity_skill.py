"""Optional provider instructions never enter the default inventory or execute at import."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from echo_agent.agent.context import build_skills_context
from echo_agent.agent.tools import skill_install
from echo_agent.agent.tools.skills import SkillViewTool
from echo_agent.skills.store import SkillStore

ROOT = Path(__file__).resolve().parents[1]


def test_default_inventory_does_not_include_optional_cohesivity(tmp_path):
    store = SkillStore(user_dir=tmp_path / "skills", builtin_dir=ROOT / "skills")
    assert len(store.list_all()) >= 35
    assert "cohesivity" not in {skill.name for skill in store.list_all()}
    assert "cohesivity" not in build_skills_context(store).lower()
    assert store.read_skill("cohesivity") is None


@pytest.mark.asyncio
async def test_explicit_install_and_view_only_import_instructions(tmp_path, monkeypatch):
    run = AsyncMock(side_effect=AssertionError("optional instruction import must not run a process"))
    install_deps = AsyncMock(side_effect=AssertionError("optional instruction import must not install dependencies"))
    monkeypatch.setattr(skill_install, "_run", run)
    monkeypatch.setattr(skill_install, "install_authorized_async", install_deps)
    store = SkillStore(user_dir=tmp_path / "skills", builtin_dir=ROOT / "skills")
    tool = skill_install.SkillInstallTool(store)
    # The skill contains no install specs: even the tool's default cannot
    # bootstrap npm, configure MCP, or make a tenant just by importing it.
    result = await tool.execute({
        "source": "local", "location": str(ROOT / "optional-skills" / "cohesivity"),
    }, None)
    assert result.success, result.error
    assert "cohesivity" in {skill.name for skill in store.list_all()}
    view = await SkillViewTool(store).execute({"name": "cohesivity"}, None)
    assert view.success, view.error
    assert "@cohesivity/init@0.9.4 --no-plugin" in view.output
    run.assert_not_called()
    install_deps.assert_not_called()
    assert not (tmp_path / ".cohesivity").exists()
