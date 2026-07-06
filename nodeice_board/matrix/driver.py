"""
Backend loading for the RGB LED matrix.

Prefers the real ``rgbmatrix`` library (built from
https://github.com/hzeller/rpi-rgb-led-matrix, e.g. via Adafruit's
installer script) and falls back to the pip-installable
``RGBMatrixEmulator`` package, which mirrors the same API.
"""

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("NodeiceMatrix")


class BackendNotAvailable(RuntimeError):
    """Raised when neither the hardware library nor the emulator is installed."""


def load_backend(prefer_emulator: bool = False) -> Tuple[Any, Any, Any, bool]:
    """
    Import a matrix backend.

    Args:
        prefer_emulator: If True, skip the hardware library and use the
            emulator directly.

    Returns:
        Tuple of (RGBMatrix, RGBMatrixOptions, graphics, is_emulator).

    Raises:
        BackendNotAvailable: If no backend can be imported.
    """
    if not prefer_emulator:
        try:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
            logger.info("Using hardware rgbmatrix backend")
            return RGBMatrix, RGBMatrixOptions, graphics, False
        except ImportError:
            logger.info("Hardware rgbmatrix library not available, trying emulator")

    try:
        from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions, graphics
        logger.info("Using RGBMatrixEmulator backend")
        return RGBMatrix, RGBMatrixOptions, graphics, True
    except ImportError:
        raise BackendNotAvailable(
            "No matrix backend found. On the Raspberry Pi, install the "
            "rpi-rgb-led-matrix Python bindings (see install_matrix_service.sh). "
            "For desktop development, `pip install RGBMatrixEmulator`."
        )


def create_matrix(matrix_config: Dict[str, Any], prefer_emulator: bool = False,
                  brightness_override: Optional[int] = None):
    """
    Create and return (matrix, graphics, is_emulator) from a config dict.

    Args:
        matrix_config: Normalized matrix configuration (see
            nodeice_board.config.get_matrix_config).
        prefer_emulator: Force the emulator backend.
        brightness_override: If set, overrides the configured brightness.
    """
    RGBMatrix, RGBMatrixOptions, graphics, is_emulator = load_backend(prefer_emulator)

    options = RGBMatrixOptions()
    options.rows = matrix_config["rows"]
    options.cols = matrix_config["cols"]
    options.chain_length = matrix_config["chain_length"]
    options.parallel = matrix_config["parallel"]
    options.brightness = brightness_override if brightness_override is not None else matrix_config["brightness"]
    options.hardware_mapping = matrix_config["hardware_mapping"]
    if matrix_config["gpio_slowdown"] is not None:
        options.gpio_slowdown = matrix_config["gpio_slowdown"]
    # The bonnet cannot generate hardware PWM without the GPIO4-GPIO18 solder
    # jumper mod; drop_privileges stays on (the library handles root for us).
    options.drop_privileges = matrix_config["drop_privileges"]

    matrix = RGBMatrix(options=options)
    return matrix, graphics, is_emulator
