from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_outline_modifiers_are_poked_after_setup():
    outline = (ROOT / "ba_outline.py").read_text(encoding="utf-8")
    prop_outline = (ROOT / "ba_props_outline.py").read_text(encoding="utf-8")

    for source in (outline, prop_outline):
        assert "def refresh_modifier_viewport(obj, mod)" in source
        assert "mod.show_viewport = False" in source
        assert "mod.show_viewport = True" in source
        assert "obj.update_tag()" in source
        assert "refresh_modifier_viewport(obj, mod)" in source


if __name__ == "__main__":
    test_outline_modifiers_are_poked_after_setup()
