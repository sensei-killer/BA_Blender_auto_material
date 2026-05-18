import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def module_tree(name):
    return ast.parse((ROOT / name).read_text(encoding="utf-8"))


def top_level_defs(tree, kind):
    return [
        node.name
        for node in tree.body
        if isinstance(node, kind)
    ]


def test_common_blender_helpers_live_in_utils_module():
    utils = module_tree("ba_utils.py")
    functions = set(top_level_defs(utils, ast.FunctionDef))

    assert {
        "nodegroup_blend_path",
        "import_node_group",
        "ensure_node_group",
        "ensure_output",
        "clear_nodes",
        "new_tex",
        "safe_link",
        "add_light_color_node",
        "add_alpha_node",
        "add_lit_alpha_node",
        "link_alpha_to_output",
        "configure_alpha_material",
        "import_material",
        "ensure_socket_is_attribute",
    }.issubset(functions)


def test_init_only_registers_one_character_setup_operator():
    init_tree = module_tree("__init__.py")
    class_names = top_level_defs(init_tree, ast.ClassDef)

    assert "BA_OT_setup_materials" not in class_names


def test_init_declares_blender_42_minimum_version():
    init_tree = module_tree("__init__.py")
    bl_info = ast.literal_eval(init_tree.body[0].value)

    assert bl_info["blender"] == (4, 2, 0)


def test_init_exposes_color_management_operator_below_add_mouth():
    source = (ROOT / "__init__.py").read_text(encoding="utf-8")

    assert "class BA_OT_set_color_management" in source
    assert 'bl_idname = "ba.set_color_management"' in source
    assert "scene.display_settings.display_device = 'sRGB'" in source
    assert "scene.view_settings.view_transform = 'Standard'" in source
    assert "BA_OT_set_color_management" in source[source.index("classes = ("):]

    mouth_pos = source.index('layout.operator("ba.setup_mouth"')
    color_pos = source.index('layout.operator("ba.set_color_management"')
    assert mouth_pos < color_pos


def test_init_exposes_convert_to_rigify_below_add_mouth():
    source = (ROOT / "__init__.py").read_text(encoding="utf-8")

    assert "class BA_OT_convert_to_rigify" in source
    assert 'bl_idname = "ba.convert_to_rigify"' in source
    assert "ba_rigify.run_convert_to_rigify()" in source
    assert "BA_OT_convert_to_rigify" in source[source.index("classes = ("):]

    mouth_pos = source.index('layout.operator("ba.setup_mouth"')
    rigify_pos = source.index('layout.operator("ba.convert_to_rigify"')
    color_pos = source.index('layout.operator("ba.set_color_management"')
    assert mouth_pos < rigify_pos < color_pos


def test_duplicate_helpers_are_not_redeclared_in_feature_modules():
    duplicate_helpers = {
        "ensure_node_group",
        "import_node_group",
        "ensure_output",
        "clear_nodes",
        "new_tex",
        "safe_link",
        "import_material",
        "ensure_socket_is_attribute",
    }

    for module_name in [
        "ba_ch_materials.py",
        "ba_props.py",
        "ba_halo.py",
        "ba_outline.py",
        "ba_props_outline.py",
    ]:
        tree = module_tree(module_name)
        functions = set(top_level_defs(tree, ast.FunctionDef))

        assert not (functions & duplicate_helpers), module_name


def test_prop_outline_node_group_name_is_spelled_correctly():
    source = (ROOT / "ba_props_outline.py").read_text(encoding="utf-8")

    assert "ba_weapon_outline" in source
    assert "ba_weapeon_ouline" not in source


def test_shader_controls_expose_shared_head_control_helper():
    source = (ROOT / "ba_shader_controls.py").read_text(encoding="utf-8")

    assert "def ensure_head_control" in source
    assert "def ensure_hair_spec_control" in source
    assert "def ensure_face_light_dot_control" in source
    assert "RIGIFY_HEAD_BONE_CANDIDATES" in source
    assert '"head"' in source
    assert '"DEF-spine.006"' in source
    assert "IGNORED_RIG_NAME_TOKENS" in source
    assert '"mouthre"' in source
    assert "def is_ignored_rig" in source
    assert "mod.type == 'ARMATURE'" in source
    assert "def retarget_shader_controls_to_rig" in source


def test_rotation_driver_helpers_guard_against_missing_empty():
    source = (ROOT / "ba_shader_controls.py").read_text(encoding="utf-8")

    assert "if empty is None:" in source


def test_shader_control_drivers_are_cleaned_from_shared_node_groups():
    shader_source = (ROOT / "ba_shader_controls.py").read_text(encoding="utf-8")
    material_source = (ROOT / "ba_ch_materials.py").read_text(encoding="utf-8")

    assert "SHARED_SHADER_DRIVER_NODE_GROUPS" in shader_source
    assert "def remove_shared_node_group_drivers" in shader_source
    assert "node_group.animation_data.drivers" in shader_source
    assert "node_group.driver_remove(fcurve.data_path, fcurve.array_index)" in shader_source

    driver_setup_pos = material_source.index("ba_shader_controls.add_face_rotation_drivers")
    cleanup_pos = material_source.index("ba_shader_controls.remove_shared_node_group_drivers()")
    assert cleanup_pos < driver_setup_pos


def test_rigify_migration_retargets_shader_control_empties():
    source = (ROOT / "migrate_body_to_rig_auto.py").read_text(encoding="utf-8")

    assert "ba_shader_controls.retarget_shader_controls_to_rig" in source
    assert "def retarget_shader_control_empties" in source
    assert "retarget_shader_control_empties(bpy.context, target, [mesh] + extra_meshes)" in source
    assert "IGNORED_RIG_NAME_TOKENS" in source
    assert "def is_ignored_rig" in source
    assert "not is_ignored_rig(obj)" in source


def test_rigify_migration_scores_body_mesh_without_selection_order():
    source = (ROOT / "migrate_body_to_rig_auto.py").read_text(encoding="utf-8")

    assert "def body_mesh_score" in source
    assert "def choose_body_mesh" in source
    assert "BODY_MESH_SCORE_TIE_MARGIN" in source
    assert "BODY_BONE_TO_DEF" in source[source.index("def body_mesh_score"):]
    assert "BODY_HELPER_TO_BODY" in source[source.index("def body_mesh_score"):]
    assert "body_candidates = sorted(" in source


def test_rigify_migration_skips_unbound_selected_meshes():
    source = (ROOT / "migrate_body_to_rig_auto.py").read_text(encoding="utf-8")

    assert '"skipped_unbound_meshes": []' in source
    assert "def has_source_armature_modifier" in source
    assert "modifier_extra_meshes" in source
    assert "parented_extra_meshes" in source
    assert "unbound_meshes" in source
    assert "for extra_mesh in modifier_extra_meshes:" in source
    assert "retarget_mesh_to_target(extra_mesh, source, target)" in source
    assert "for extra_mesh in extra_meshes:" not in source


def test_auto_rigify_pipeline_ignores_builtin_mouthre_rig():
    source = (ROOT / "auto_rigify_bind_pipeline.py").read_text(encoding="utf-8")

    assert "IGNORED_RIG_NAME_TOKENS" in source
    assert "def is_ignored_rig" in source
    assert "not is_ignored_rig(obj)" in source


def test_character_material_dispatch_uses_ordered_handler_table():
    source = (ROOT / "ba_ch_materials.py").read_text(encoding="utf-8")

    assert "CHARACTER_MATERIAL_HANDLERS" in source
    assert "def setup_character_material" in source

    expected_order = [
        '"_Body_Arms"',
        '"_Body"',
        '"_Hair_Alpha"',
        '"_Frill"',
        '"_Alpha"',
        '"_Face"',
        '"_Hair"',
        '"_EyeMouth"',
        '"_Eyebrow2"',
        '"_Eyebrow"',
    ]
    positions = [source.index(suffix) for suffix in expected_order]

    assert positions == sorted(positions)
    assert "setup_character_material(mat, images)" in source


def test_alpha_materials_use_named_alpha_inputs():
    utils_source = (ROOT / "ba_utils.py").read_text(encoding="utf-8")
    ch_source = (ROOT / "ba_ch_materials.py").read_text(encoding="utf-8")
    prop_source = (ROOT / "ba_props.py").read_text(encoding="utf-8")

    assert 'inputs.get("color")' in utils_source
    assert 'inputs.get("alpha")' in utils_source
    assert 'outputs.get("Shader", alpha_node.outputs[0])' in utils_source
    assert "def link_alpha_to_output" in utils_source

    assert "def setup_prop_alpha_material" in prop_source
    assert "add_lit_alpha_node" in prop_source
    assert "link_alpha_to_output" in prop_source
    assert 'weapon_node.outputs.get("Result")' in prop_source
    assert 'base_node.outputs.get("Alpha")' in prop_source

    assert "def setup_hair_alpha" in ch_source
    assert "def setup_frill_alpha" in ch_source
    assert "add_lit_alpha_node" in ch_source
    assert "link_alpha_to_output" in ch_source
    assert "alpha_shader.inputs[0]" not in ch_source


def test_alpha_materials_disable_transparency_overlap_and_support_no_texture_props():
    utils_source = (ROOT / "ba_utils.py").read_text(encoding="utf-8")
    ch_source = (ROOT / "ba_ch_materials.py").read_text(encoding="utf-8")
    prop_source = (ROOT / "ba_props.py").read_text(encoding="utf-8")

    assert "show_transparent_back = False" in utils_source
    assert "mat.surface_render_method = 'BLENDED'" in utils_source
    assert "has_useful_alpha" not in prop_source
    assert ".pixels" not in prop_source

    assert "configure_alpha_material(mat)" in prop_source
    assert "configure_alpha_material(mat)" in ch_source

    assert "if base_node:" in prop_source
    assert "else:" in prop_source
    assert 'ensure_node_group("ba_weapon_shader")' in prop_source
    assert 'alpha_default=0.3733333349227905' in prop_source
    assert 'set_input_default(alpha_node, "Fresnel", 1)' in prop_source
    assert 'set_input_default(alpha_node, "fresnelcolor_factor", 0.35)' in prop_source
    assert 'set_input_default(alpha_node, "Spec", 1)' in prop_source


def test_car_alpha_uses_no_texture_prop_alpha_branch():
    prop_source = (ROOT / "ba_props.py").read_text(encoding="utf-8")

    assert "def is_car_alpha_material" in prop_source
    assert 'mat.name.lower().endswith("_car_alpha")' in prop_source
    assert "def setup_car_alpha_material" in prop_source
    assert "setup_prop_alpha_material(mat, images, use_textures=False)" in prop_source


def test_prop_material_uses_metallic_shader_pipeline():
    source = (ROOT / "ba_props.py").read_text(encoding="utf-8")

    assert "safe_link" in source
    assert '"ba_weapon_shader"' in source
    assert '"ba_metallic_shader"' in source
    assert 'inputs.get("Base_Color")' in source
    assert 'inputs.get("Mask")' in source
    assert 'inputs.get("Color")' in source
    assert 'outputs.get("Result")' in source
    assert 'output_node.inputs.get("Surface")' in source
    assert "shader_node.outputs[0]" not in source


def test_feature_modules_use_safe_link_for_node_links():
    for module_name in [
        "ba_ch_materials.py",
        "ba_halo.py",
        "ba_props.py",
    ]:
        source = (ROOT / module_name).read_text(encoding="utf-8")

        assert ".links.new(" not in source, module_name


def test_material_setups_route_through_light_color_node():
    utils_source = (ROOT / "ba_utils.py").read_text(encoding="utf-8")
    ch_source = (ROOT / "ba_ch_materials.py").read_text(encoding="utf-8")
    prop_source = (ROOT / "ba_props.py").read_text(encoding="utf-8")

    assert '"ba_light_color"' in utils_source
    assert "def add_light_color_node" in utils_source
    assert 'inputs.get("Color")' in utils_source
    assert 'inputs.get("basecolor")' in utils_source
    assert "return node" in utils_source

    assert "add_light_color_node" in ch_source
    assert "light_color" in ch_source

    assert "add_light_color_node" in prop_source
    assert "light_color" in prop_source
    assert "weapon_node.outputs.get(\"Result\"), metallic_node.inputs.get(\"Color\")" not in prop_source


if __name__ == "__main__":
    test_common_blender_helpers_live_in_utils_module()
    test_init_only_registers_one_character_setup_operator()
    test_init_declares_blender_42_minimum_version()
    test_init_exposes_color_management_operator_below_add_mouth()
    test_duplicate_helpers_are_not_redeclared_in_feature_modules()
    test_prop_outline_node_group_name_is_spelled_correctly()
    test_shader_controls_expose_shared_head_control_helper()
    test_rotation_driver_helpers_guard_against_missing_empty()
    test_shader_control_drivers_are_cleaned_from_shared_node_groups()
    test_rigify_migration_retargets_shader_control_empties()
    test_rigify_migration_scores_body_mesh_without_selection_order()
    test_rigify_migration_skips_unbound_selected_meshes()
    test_character_material_dispatch_uses_ordered_handler_table()
    test_alpha_materials_use_named_alpha_inputs()
    test_alpha_materials_disable_transparency_overlap_and_support_no_texture_props()
    test_car_alpha_uses_no_texture_prop_alpha_branch()
    test_prop_material_uses_metallic_shader_pipeline()
    test_feature_modules_use_safe_link_for_node_links()
    test_material_setups_route_through_light_color_node()
