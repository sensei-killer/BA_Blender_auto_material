"""Small RNA adapters for Blender 4.2 through 5.3."""

import bpy


def set_image_color_space(image, non_color=False):
    settings = image.colorspace_settings
    if hasattr(settings, "interop_id"):
        try:
            settings.interop_id = 'data' if non_color else 'srgb_rec709_display'
            return
        except (TypeError, ValueError):
            pass
    settings.name = 'Non-Color' if non_color else 'sRGB'


def configure_alpha_material(material):
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = 'BLENDED'
    else:
        material.blend_method = 'BLEND'
    if hasattr(material, "show_transparent_back"):
        material.show_transparent_back = False


def modifier_socket(modifier, identifier):
    properties = getattr(modifier, "properties", None)
    inputs = getattr(properties, "inputs", None)
    return getattr(inputs, identifier, None) if inputs is not None else None


def set_modifier_input(modifier, identifier, value=None, attribute=None):
    socket = modifier_socket(modifier, identifier)
    if socket is not None:
        if attribute is not None:
            socket.type = 'ATTRIBUTE'
            socket.attribute_name = attribute
        else:
            socket.type = 'VALUE'
            socket.value = value
        return
    if attribute is not None:
        modifier[identifier + "_use_attribute"] = True
        modifier[identifier + "_attribute_name"] = attribute
    else:
        modifier[identifier] = value
        if identifier + "_use_attribute" in modifier:
            modifier[identifier + "_use_attribute"] = False


def get_modifier_input(modifier, identifier, default=None):
    socket = modifier_socket(modifier, identifier)
    if socket is not None:
        if socket.type == 'ATTRIBUTE':
            return {"attribute": socket.attribute_name}
        value = socket.value
        if hasattr(value, '__len__') and not isinstance(value, (str, bpy.types.ID)):
            value = tuple(value)
        return {"value": value}
    if modifier.get(identifier + "_use_attribute", False):
        return {"attribute": modifier.get(identifier + "_attribute_name", "")}
    value = modifier.get(identifier, default)
    if hasattr(value, '__len__') and not isinstance(value, (str, bpy.types.ID)):
        value = tuple(value)
    return {"value": value}


def action_fcurves(owner):
    animation = owner.animation_data
    if animation is None:
        return []
    actions = [(animation.action, getattr(animation, 'action_slot', None))]

    def collect_strips(strips):
        for strip in strips:
            actions.append((strip.action, getattr(strip, 'action_slot', None)))
            collect_strips(getattr(strip, 'strips', ()))

    for track in animation.nla_tracks:
        collect_strips(track.strips)
    curves = set()
    for action, slot in actions:
        if action is None:
            continue
        if hasattr(action, "layers") and len(action.layers):
            for layer in action.layers:
                for strip in layer.strips:
                    for bag in getattr(strip, "channelbags", ()):
                        if slot is None or bag.slot_handle == slot.handle:
                            curves.update(bag.fcurves)
        else:
            curves.update(getattr(action, "fcurves", ()))
    return list(curves)
