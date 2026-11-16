"""Explicit, reversible upgrades for bundled shader and outline groups."""

import re

import bpy

from .ba_compat import action_fcurves, get_modifier_input, set_modifier_input


ASSET_REVISION = '0.2.3'
GROUP_NAMES = (
    'ba_alpha', 'ba_body_shader', 'ba_face_shader', 'ba_hair_shader', 'ba_halo',
    'ba_light_color', 'ba_light_color_inner', 'BA_MASK', 'ba_metallic_shader',
    'ba_no_shadow', 'ba_outline', 'ba_outline_shader',
    'BA_SPEC', 'ba_weapon_outline', 'ba_weapon_shader', 'Dot for Specular',
    'eyebrow_in_front', 'Kajiya-Kay', 'MatCap', 'ShadowClamp',
)


def plain(value):
    if isinstance(value, bpy.types.ID):
        return value
    if hasattr(value, '__len__') and not isinstance(value, str):
        return tuple(value)
    return value


def interface_sockets(group, direction):
    return [s for s in group.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == direction]


def socket_mapping(old_sockets, new_sockets):
    remaining = list(new_sockets)
    result = {}
    for old in old_sockets:
        compatible = [s for s in remaining if s.name == old.name and s.bl_socket_idname == old.bl_socket_idname]
        match = next((s for s in compatible if s.identifier == old.identifier), None)
        if match is None and len(compatible) == 1:
            match = compatible[0]
        if match is None:
            raise RuntimeError(f'Incompatible socket: {old.name} ({old.bl_socket_idname}); old resources retained')
        result[old.identifier] = match.identifier
        remaining.remove(match)
    return result


def all_trees():
    result = list(bpy.data.node_groups)
    for collection in (bpy.data.materials, bpy.data.worlds, bpy.data.lights, bpy.data.scenes):
        result.extend(d.node_tree for d in collection if getattr(d, 'node_tree', None))
    return result


def upgrade_resources():
    from .ba_utils import nodegroup_blend_path
    old_groups = {name: bpy.data.node_groups.get(name) for name in GROUP_NAMES}
    old_groups = {name: group for name, group in old_groups.items() if group is not None}
    if any(group.library for group in old_groups.values()):
        raise RuntimeError('Linked node resources must be made local before upgrading')
    old_names = {group: name for name, group in old_groups.items()}
    backup_flags = {group: (group.use_fake_user, group.get('_ba_backup')) for group in old_names}
    before = set(bpy.data.node_groups)
    states = []
    for tree in all_trees():
        if tree in old_names or tree.get('_ba_backup'):
            continue
        for node in tree.nodes:
            if node.type != 'GROUP' or node.node_tree not in old_names:
                continue
            if tree.library:
                raise RuntimeError(f'Cannot upgrade linked node tree: {tree.name}')
            curves = list(tree.animation_data.drivers) if tree.animation_data else []
            curves.extend(action_fcurves(tree))
            states.append({
                'tree': tree, 'node': node, 'group': node.node_tree,
                'inputs': [(i, s.identifier, plain(s.default_value)) for i, s in enumerate(node.inputs) if hasattr(s, 'default_value')],
                'curves': [(c, c.data_path) for c in curves],
            })
    affected_nodes = {s['node']: s for s in states}
    links = {tree: [(l.from_node, l.from_socket.identifier, l.to_node, l.to_socket.identifier) for l in tree.links if l.from_node in affected_nodes or l.to_node in affected_nodes] for tree in {s['tree'] for s in states}}
    modifiers = []
    for obj in bpy.data.objects:
        for mod in obj.modifiers:
            if mod.type == 'NODES' and mod.node_group in old_names:
                if obj.library:
                    raise RuntimeError(f'Cannot upgrade linked modifier owner: {obj.name}')
                values = {s.identifier: get_modifier_input(mod, s.identifier, plain(getattr(s, 'default_value', None))) for s in interface_sockets(mod.node_group, 'INPUT') if s.bl_socket_idname != 'NodeSocketGeometry'}
                modifiers.append((mod, mod.node_group, values))
    applied = []
    applied_modifiers = []
    mappings = {}

    def restore_links(upgraded):
        for tree, rows in links.items():
            for source, sid, target, tid in rows:
                if upgraded and source in affected_nodes:
                    sid = mappings[affected_nodes[source]['group']][1][sid]
                if upgraded and target in affected_nodes:
                    tid = mappings[affected_nodes[target]['group']][0][tid]
                out = next(s for s in source.outputs if s.identifier == sid)
                inp = next(s for s in target.inputs if s.identifier == tid)
                if not any(l.from_socket == out and l.to_socket == inp for l in tree.links):
                    tree.links.new(out, inp)

    try:
        with bpy.data.libraries.load(nodegroup_blend_path(), link=False) as (source, target):
            missing = set(GROUP_NAMES) - set(source.node_groups)
            if missing:
                raise RuntimeError('Bundled resources missing: ' + ', '.join(sorted(missing)))
            target.node_groups = list(GROUP_NAMES)
        fresh = dict(zip(GROUP_NAMES, target.node_groups))
        for name, old in old_groups.items():
            if old.bl_idname != fresh[name].bl_idname:
                raise RuntimeError(f'Incompatible node tree type: {name}; old resources retained')
            mappings[old] = tuple(socket_mapping(interface_sockets(old, d), interface_sockets(fresh[name], d)) for d in ('INPUT', 'OUTPUT'))
        for state in states:
            node, old = state['node'], state['group']
            input_map = mappings[old][0]
            node.node_tree = fresh[old_names[old]]
            applied.append(state)
            for _, identifier, value in state['inputs']:
                next(s for s in node.inputs if s.identifier == input_map[identifier]).default_value = value
            prefix = re.escape(node.path_from_id()) + r'\.inputs\[(\d+)\]'
            for curve, path in state['curves']:
                match = re.match(prefix, path)
                if match:
                    identifier = next(identifier for index, identifier, _ in state['inputs'] if index == int(match.group(1)))
                    index = next(i for i, socket in enumerate(node.inputs) if socket.identifier == input_map[identifier])
                    curve.data_path = re.sub(prefix, lambda _: node.path_from_id() + f'.inputs[{index}]', path, count=1)
        restore_links(True)
        for mod, old, values in modifiers:
            mod.node_group = fresh[old_names[old]]
            applied_modifiers.append((mod, old, values))
            for identifier, value in values.items():
                set_modifier_input(mod, mappings[old][0][identifier], **value)
        for name, old in old_groups.items():
            old.name = name + '__backup_' + old.get('_ba_asset_revision', 'legacy')
            old['_ba_backup'] = True
            old.use_fake_user = True
        for name, group in fresh.items():
            group.name = name
            group['_ba_asset_revision'] = ASSET_REVISION
        bpy.context.view_layer.update()
        return len(states), len(modifiers)
    except Exception:
        for state in reversed(applied):
            state['node'].node_tree = state['group']
            for _, identifier, value in state['inputs']:
                next(s for s in state['node'].inputs if s.identifier == identifier).default_value = value
            for curve, path in state['curves']:
                curve.data_path = path
        restore_links(False)
        for mod, old, values in applied_modifiers:
            mod.node_group = old
            for identifier, value in values.items():
                set_modifier_input(mod, identifier, **value)
        new_groups = set(bpy.data.node_groups) - before
        for group in new_groups:
            group.name = '__BA_failed_update'
        for group, name in old_names.items():
            group.name = name
            group.use_fake_user, flag = backup_flags[group]
            if flag is None:
                if '_ba_backup' in group:
                    del group['_ba_backup']
            else:
                group['_ba_backup'] = flag
        if new_groups:
            bpy.data.batch_remove(ids=new_groups)
        raise


class BA_OT_update_resources(bpy.types.Operator):
    bl_idname = 'ba.update_resources'
    bl_label = 'Update Node Resources'
    bl_description = 'Update shader and outline groups, preserving instance values and retaining old groups as backups'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            nodes, modifiers = upgrade_resources()
        except Exception as exc:
            # Keep a boundary even if exception recovery itself was incomplete.
            self.report({'WARNING'}, f'Resource update failed: {exc}; use Undo to restore the previous state')
            return {'FINISHED'}
        self.report({'INFO'}, f'Updated {nodes} group nodes and {modifiers} modifiers; backups retained')
        return {'FINISHED'}
