from .ba_rigify_state import ConversionRecoveryError


def run_convert_to_rigify(include_eye_controls=True, warnings=None):
    from . import auto_rigify_bind_pipeline
    return auto_rigify_bind_pipeline.main(include_eye_controls, warnings)

