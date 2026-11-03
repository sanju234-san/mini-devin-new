"""
Regression tests for Chainlit console clipboard paste fix.
"""

from pathlib import Path
import subprocess
try:
    import tomllib
except ImportError:
    import tomli as tomllib


def test_custom_js_configured():
    config_path = Path(__file__).parent / ".chainlit" / "config.toml"
    assert config_path.exists(), "config.toml should exist"
    
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    
    assert "UI" in data, "[UI] section must be in config.toml"
    assert data["UI"].get("custom_js") == "/public/paste_fix.js", (
        "custom_js must point to /public/paste_fix.js"
    )


def test_paste_fix_script_exists():
    script_path = Path(__file__).parent / "public" / "paste_fix.js"
    assert script_path.exists(), "paste_fix.js must exist in chainlit_console/public"
    content = script_path.read_text(encoding="utf-8")
    assert "addEventListener('paste'" in content or 'addEventListener("paste"' in content
    assert "stopImmediatePropagation" in content
    assert "execCommand" in content
    assert "insertText" in content


def test_node_dom_regression_suite():
    test_js = Path(__file__).parent / "test_clipboard_paste.js"
    assert test_js.exists(), "test_clipboard_paste.js must exist"
    
    res = subprocess.run(
        ["node", str(test_js)],
        cwd=str(Path(__file__).parent),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Node regression test failed: {res.stderr}\n{res.stdout}"
    assert "ALL 5 REGRESSION TESTS PASSED SUCCESSFULLY!" in res.stdout
