from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_guard_module():
    module_path = Path("scripts/ci/check_localization_literals.py")
    spec = importlib.util.spec_from_file_location("check_localization_literals", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_collect_violations_flags_direct_response_literal(tmp_path):
    module = _load_guard_module()
    target = tmp_path / "sample.py"
    target.write_text("from app.whatsapp.response_templates import success_response\nresult = success_response('Hello member')\n", encoding="utf-8")

    module.TARGET_GLOBS = (str(target),)

    violations = module.collect_violations()

    assert len(violations) == 1
    assert violations[0].literal == "Hello member"
    assert violations[0].call_name == "success_response"


def test_collect_violations_ignores_translate_keys(tmp_path):
    module = _load_guard_module()
    target = tmp_path / "sample.py"
    target.write_text(
        "from app.i18n.catalog import translate\n"
        "from app.whatsapp.response_templates import success_response\n"
        "result = success_response(translate('public.help.title', 'en'))\n",
        encoding="utf-8",
    )

    module.TARGET_GLOBS = (str(target),)

    violations = module.collect_violations()

    assert violations == []


def test_collect_violations_ignores_internal_tokens(tmp_path):
    module = _load_guard_module()
    target = tmp_path / "sample.py"
    target.write_text(
        "def send_list_response(*args, **kwargs):\n"
        "    return None\n"
        "send_list_response(cta='ui::menu')\n",
        encoding="utf-8",
    )

    module.TARGET_GLOBS = (str(target),)

    violations = module.collect_violations()

    assert violations == []
