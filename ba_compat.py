"""Small RNA adapters for Blender 4.2 through 5.3."""

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
    if inputs is None:
        return None
    socket = getattr(inputs, identifier, None)
    if socket is None:
        raise RuntimeError(f'Geometry Nodes input {identifier!r} is unavailable on {modifier.name!r}; check the node group interface')
    return socket


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
