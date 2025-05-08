# Nodeice Matrix Display

A 32x32 RGB LED Matrix display service for the Nodeice Board Meshtastic notice board application.

## Overview

Nodeice Matrix Display is a companion service for the Nodeice Board application that displays information on a 32x32 RGB LED matrix. It shows the Meshtastic logo, the title "Nodice Board", rotating stats from the metrics collection table, and displays new messages in a visually striking way when they are posted.

## Features

- Always shows the Meshtastic logo and "Nodice Board" title
- Displays rotating stats from the metrics collection table
- Shows the current number of active posts at all times
- Displays new messages with eye-catching animations when they are posted
- Configurable display settings via config.yaml
- Runs as a systemd service that starts on boot
- Proper logging for easy troubleshooting

## Requirements

- Raspberry Pi (tested on Raspberry Pi 4)
- 32x32 RGB LED Matrix with Adafruit RGB Matrix HAT
- Python 3.7 or higher
- Nodeice Board application running on the same system
- Internet connection (for downloading dependencies during installation)

## Installation

1. Make sure the Nodeice Board application is installed and running.

2. Navigate to the nodeice-matrix directory:
   ```bash
   cd nodeice-matrix
   ```

3. Run the installation script with sudo:
   ```bash
   sudo ./install_matrix_service.sh
   ```

   This script will:
   - Install system dependencies
   - Install the uv package manager (a fast Python package manager written in Rust)
   - Install the rpi-rgb-led-matrix library
   - Set up a Python virtual environment using uv
   - Download required fonts
   - Create a systemd service
   - Configure logging
   - Start the service (if you choose to)

## Configuration

The display can be configured by editing the `config.yaml` file:

```yaml
display:
  # Hardware settings
  hardware_mapping: "adafruit-hat"  # Default for Adafruit RGB HAT
  rows: 32
  cols: 32
  chain_length: 1
  parallel: 1
  brightness: 70  # 0-100
  gpio_slowdown: 2  # Adjust based on your Raspberry Pi model
  
  # Visual settings
  title_color: [255, 255, 255]  # RGB values
  logo_position: "top-left"     # top-left, top-right, bottom-left, bottom-right
  background_color: [0, 0, 0]   # RGB values
  
  # Animation settings
  rotation_interval: 5          # Seconds between rotating stats
  message_display_time: 15      # Seconds to show a new message
  scroll_speed: 2               # Pixels per frame
  
  # Message counter
  counter_position: "bottom-right"
  counter_color: [0, 255, 0]    # Green
  
database:
  path: "../nodeice_board.db"   # Path to the Nodeice Board database
  poll_interval: 2              # Seconds between database checks
  
logging:
  level: "INFO"                 # DEBUG, INFO, WARNING, ERROR
  file: "/var/log/nodeice-matrix/matrix.log"
```

## Usage

The service will start automatically at boot. You can control it using systemd commands:

```bash
# Start the service
sudo systemctl start nodeice-matrix.service

# Stop the service
sudo systemctl stop nodeice-matrix.service

# Restart the service
sudo systemctl restart nodeice-matrix.service

# Check the status
sudo systemctl status nodeice-matrix.service

# View logs
sudo journalctl -u nodeice-matrix.service

# Follow logs in real-time
sudo journalctl -u nodeice-matrix.service -f
```

## Troubleshooting

If you encounter issues:

1. Check the logs:
   ```bash
   sudo journalctl -u nodeice-matrix.service -n 100
   ```

2. Verify the database path in config.yaml points to the correct Nodeice Board database.

3. Ensure the RGB matrix is properly connected to the Raspberry Pi.

4. Check that the Adafruit RGB Matrix HAT is properly configured.

5. If the display is not working correctly, try adjusting the gpio_slowdown value in config.yaml.

### RGB Matrix Module Issues

If you encounter the error `ModuleNotFoundError: No module named 'rgbmatrix'`:

1. Verify the RGB matrix library installation:
   ```bash
   cd nodeice-matrix
   source .venv/bin/activate
   python -c "import rgbmatrix; print('RGB Matrix library is installed')"
   ```

2. If the import fails, manually install the library:
   ```bash
   cd nodeice-matrix
   source .venv/bin/activate
   cd rpi-rgb-led-matrix/bindings/python
   pip install -e .
   cd ../../../
   ```

3. If you're still having issues with uv, try using the full path:
   ```bash
   # Find the full path to uv
   which uv
   # Use the full path (replace /path/to/uv with the actual path)
   /path/to/uv pip install -e ./rpi-rgb-led-matrix/bindings/python
   ```

4. As a last resort, try reinstalling with the system Python:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-dev python3-pillow
   cd rpi-rgb-led-matrix
   make build-python PYTHON=$(which python3)
   sudo make install-python PYTHON=$(which python3)
   ```

## Architecture

The service consists of several components:

- **Database Monitor**: Monitors the SQLite database for new messages and updated metrics
- **Display Controller**: Manages the RGB LED matrix display and animations
- **Main Application**: Ties everything together and handles the service lifecycle

## License

This project is licensed under the MIT License - see the LICENSE file for details.
