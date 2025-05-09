# RGB LED Matrix Display for Nodeice Board

This document provides information about the RGB LED Matrix display functionality for the Nodeice Board application.

## Overview

The RGB LED Matrix display enhances the Nodeice Board by providing a visual interface that shows:

1. The Nodeice Board title and Meshtastic logo
2. Rotating status information (messages count, uptime, etc.)
3. Visual notifications when new messages are received

The display is designed to work with a 32x32 RGB LED matrix panel connected to a Raspberry Pi via the Adafruit RGB Matrix HAT or similar hardware.

## Hardware Requirements

- Raspberry Pi (3 or 4 recommended for best performance)
- 32x32 RGB LED Matrix panel
- Adafruit RGB Matrix HAT or compatible hardware
- Power supply appropriate for your LED matrix (5V, typically 2-4A depending on brightness)

## Installation

The LED Matrix support is included in the main Nodeice Board installation script. When running `install_service.sh`, you'll be prompted to enable RGB LED Matrix support:

```bash
sudo ./install_service.sh
```

When prompted, select 'y' to install the RGB LED Matrix support. The script will:

1. Install required dependencies
2. Clone and build the rpi-rgb-led-matrix library
3. Set up proper permissions for GPIO access
4. Update the configuration to enable the LED matrix
5. Make the test scripts executable

## Configuration

The LED Matrix settings can be configured in the `config.yaml` file under the `LED_Matrix` section:

```yaml
Nodeice_board:
  # Other Nodeice Board settings...
  LED_Matrix:
    Enabled: true                # Enable/disable the LED matrix
    Hardware_Mapping: "adafruit-hat"  # Hardware mapping (see below)
    Rows: 32                     # Number of rows in the matrix
    Cols: 32                     # Number of columns in the matrix
    Chain_Length: 1              # Number of matrices chained together
    Parallel: 1                  # Number of parallel chains
    Brightness: 50               # Brightness level (0-100)
    GPIO_Slowdown: 2             # GPIO slowdown factor for older Pis
    Display_Mode: "standard"     # Display mode (minimal, standard, colorful)
    Status_Cycle_Seconds: 5      # Seconds between status screen changes
    Message_Effect: "rainbow"    # Default effect for messages (rainbow, pulse, wipe, border)
    Interactive: true            # Enable button controls (if implemented)
    Auto_Brightness: true        # Adjust brightness based on time of day
```

### Hardware Mapping Options

The `Hardware_Mapping` setting should match your hardware setup:

- `"adafruit-hat"` - For the Adafruit RGB Matrix HAT
- `"adafruit-hat-pwm"` - For the Adafruit RGB Matrix HAT with PWM hardware
- `"regular"` - For direct GPIO wiring without a HAT
- `"regular-pi1"` - For direct GPIO wiring on a Raspberry Pi 1
- `"classic"` - For classic wiring (obsolete)

## Testing

Two test scripts are provided to verify your LED matrix setup:

### 1. Permission Test

```bash
./test_led_permissions.sh
```

This script checks if your system is properly configured for the LED matrix, including:
- GPIO access permissions
- Required Python modules
- Hardware detection

### 2. Display Test

```bash
./test_led_matrix.py
```

This script tests various display functions:
- Logo display
- Text rendering
- Status screen cycling
- Message effects

You can test specific features with the `--test` option:

```bash
./test_led_matrix.py --test logo
./test_led_matrix.py --test text
./test_led_matrix.py --test status
./test_led_matrix.py --test message
```

## Message Effects

The LED matrix can display messages with different visual effects:

1. **Rainbow** - Text scrolls across the screen with rainbow-colored letters
2. **Pulse** - The screen pulses with increasing brightness before displaying the message
3. **Wipe** - A colorful wipe transition clears the screen before showing the message
4. **Border** - A colorful border flashes around the edge while the message scrolls

## Status Screens

The LED matrix cycles through different status screens, showing:

1. Total message count
2. System uptime
3. Connected nodes information
4. Post expiration countdown
5. Current date and time

## Troubleshooting

### Display Not Working

1. Run the permission test script to check for configuration issues:
   ```bash
   ./test_led_permissions.sh
   ```

2. Verify that the RGB Matrix library is properly installed:
   ```bash
   python3 -c "import rgbmatrix"
   ```

3. Check the Nodeice Board logs for any errors:
   ```bash
   tail -f nodeice_board.log | grep "LED Matrix"
   ```

4. Verify that the LED matrix is enabled in the configuration:
   ```bash
   grep -A15 "LED_Matrix" config.yaml
   ```

### Permission Issues

If you encounter permission issues, you may need to:

1. Add your user to the required groups:
   ```bash
   sudo usermod -a -G gpio,i2c,spi $USER
   ```

2. Set permissions on GPIO devices:
   ```bash
   sudo chmod a+rw /dev/gpiomem
   sudo chmod a+rw /dev/i2c-1
   ```

3. Log out and log back in for group changes to take effect.

### Display Quality Issues

1. Adjust the `GPIO_Slowdown` setting in `config.yaml` (try values 1-4)
2. Reduce brightness if you see power-related issues
3. For Raspberry Pi 4, try setting `GPIO_Slowdown` to 1 or 2
4. For older Raspberry Pi models, try higher `GPIO_Slowdown` values (3-4)

## Advanced Configuration

### Multiple Panels

To chain multiple panels together, adjust these settings:

```yaml
Chain_Length: 2  # Number of panels chained horizontally
Parallel: 1      # Number of chains (for vertical stacking)
```

### Custom Fonts

The display uses BDF fonts from the rpi-rgb-led-matrix library. To use different fonts:

1. Find BDF fonts in the `rpi-rgb-led-matrix/fonts/` directory
2. Modify the font paths in `led_matrix_display.py` to use different fonts

## Resources

- [rpi-rgb-led-matrix GitHub Repository](https://github.com/hzeller/rpi-rgb-led-matrix)
- [Adafruit RGB Matrix HAT Documentation](https://learn.adafruit.com/adafruit-rgb-matrix-plus-real-time-clock-hat-for-raspberry-pi)
- [BDF Font Information](https://en.wikipedia.org/wiki/Glyph_Bitmap_Distribution_Format)
