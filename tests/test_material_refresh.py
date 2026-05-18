from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_material_setup_refreshes_view_layer_after_node_and_outline_changes():
    utils = (ROOT / "ba_utils.py").read_text(encoding="utf-8")
    ch = (ROOT / "ba_ch_materials.py").read_text(encoding="utf-8")
    init = (ROOT / "__init__.py").read_text(encoding="utf-8")

    assert "def refresh_view_layer(context)" in utils
    assert "context.view_layer.update()" in utils

    assert "refresh_view_layer(context)" in ch
    assert ch.index("ba_outline.add_ba_outline(context)") < ch.index("refresh_view_layer(context)")

    assert "refresh_view_layer(context)" in init
    assert init.index("ba_props_outline.add_ba_props_outline(context)") < init.index("refresh_view_layer(context)")


if __name__ == "__main__":
    test_material_setup_refreshes_view_layer_after_node_and_outline_changes()
