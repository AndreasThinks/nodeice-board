# Running Nodeice Board on Raspberry Pi

This guide provides detailed instructions for setting up Nodeice Board to run automatically at boot on a Raspberry Pi.

## Table of Contents

1. [Automatic Installation](#automatic-installation)
2. [Manual Installation](#manual-installation)
3. [Configuration Options](#configuration-options)
4. [RGB LED Matrix Setup](#rgb-led-matrix-setup)
5. [Monitoring and Maintenance](#monitoring-and-maintenance)
6. [Troubleshooting](#troubleshooting)
7. [Updating](#updating)
8. [Advanced Configuration](#advanced-configuration)

## Automatic Installation

For a quick and easy setup, use the provided installation script:

1. Make all scripts executable:
   ```bash
   chmod +x install_service.sh setup_meshtastic_device.sh check_nodeice_status.sh kill_previous_instances.sh
   ```

2. Run the installation script with sudo (REQUIRED):
   ```bash
   sudo ./install_service.sh
   ```
   
   **Why sudo is required:** This script needs root privileges to:
   - Install system packages with apt-get
   - Create a systemd service file in /etc/systemd/system/
   - Create a log directory in /var/log/
   - Reload systemd daemon
   - Enable and start the systemd service

3. Follow the prompts to complete the installation.

The script will:
- Check prerequisites (Python version, Meshtastic device)
- Install required dependencies
- Set up a Python virtual environment
- Install Nodeice Board and its dependencies
- Create and configure a systemd service
- Enable the service to start at boot
- Optionally start the service immediately

## Manual Installation

If you prefer to set up the service manually, follow these steps:

### 1. Install Dependencies

```bash
sudo apt-get update                           # sudo required - system package management
sudo apt-get install -y python3-pip python3-venv  # sudo required - system package management
```

### 2. Set Up the Project

Clone the repository (if you haven't already):
```bash
git clone https://github.com/yourusername/nodeice-board.git
cd nodeice-board
```

Create a virtual environment:
```bash
python3 -m venv venv
```

Activate the virtual environment and install dependencies:
```bash
source venv/bin/activate
pip install -e .
```

### 3. Create a Systemd Service File

Create a new service file:
```bash
sudo nano /etc/systemd/system/nodeice-board.service  # sudo required - writing to system directory
```

Add the following content (adjust paths as needed):
```
[Unit]
Description=Nodeice Board Meshtastic Notice Board
Documentation=https://github.com/AndreasThinks/nodeice-board
After=network.target
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=pi  # Change to your username
WorkingDirectory=/home/pi/nodeice-board  # Change to your project path
ExecStart=/home/pi/nodeice-board/venv/bin/python /home/pi/nodeice-board/main.py
Environment="PYTHONUNBUFFERED=1"
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

# Security hardening
ProtectSystem=full
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

### 4. Enable and Start the Service

```bash
sudo systemctl daemon-reload      # sudo required - managing systemd
sudo systemctl enable nodeice-board.service   # sudo required - managing systemd
sudo systemctl start nodeice-board.service    # sudo required - managing systemd
```

### 5. Verify the Service is Running

```bash
sudo systemctl status nodeice-board.service   # sudo required - accessing systemd service status
```

## Configuration Options

### Command Line Arguments

When running Nodeice Board, you can specify several command-line arguments:

- `--device_path`: Path to the Meshtastic device (optional, auto-detects if not provided)
- `--db_path`: Path to the database file (default: nodeice_board.db)
- `--config_path`: Path to the configuration file (default: config.yaml)

To use these with the systemd service, modify the `ExecStart` line in the service file:

```
ExecStart=/home/pi/nodeice-board/venv/bin/python /home/pi/nodeice-board/main.py --device_path=/dev/ttyUSB0 --db_path=/path/to/database.db --config_path=/path/to/config.yaml
```

### Configuration File

The `config.yaml` file allows you to customize various aspects of Nodeice Board:

```yaml
Nodeice_board:
  Long_Name: "Nodeice Board📌Msg me !help"  # Long name for the Meshtastic device
  Short_Name: "NDB"                         # Short name for the Meshtastic device
  Info_URL: "https://github.com/AndreasThinks/nodeice-board"  # URL for more information
  Expiration_Days: 7                        # Number of days after which posts are deleted
  LED_Matrix:                               # RGB LED Matrix configuration (optional)
    Enabled: true                           # Enable/disable the LED matrix
    Hardware_Mapping: "adafruit-hat"        # Hardware mapping for your setup
    Rows: 32                                # Number of rows in the matrix
    Cols: 32                                # Number of columns in the matrix
    Chain_Length: 1                         # Number of matrices chained together
    Parallel: 1                             # Number of parallel chains
    Brightness: 50                          # Brightness level (0-100)
    GPIO_Slowdown: 2                        # GPIO slowdown factor for older Pis
    Display_Mode: "standard"                # Display mode (minimal, standard, colorful)
    Status_Cycle_Seconds: 5                 # Seconds between status screen changes
    Message_Effect: "rainbow"               # Default effect for messages
    Interactive: true                       # Enable button controls (if implemented)
    Auto_Brightness: true                   # Adjust brightness based on time of day
```

## RGB LED Matrix Setup

Nodeice Board supports displaying status information and messages on a 32x32 RGB LED Matrix panel connected to your Raspberry Pi.

### Hardware Requirements

- Raspberry Pi (3 or 4 recommended for best performance)
- 32x32 RGB LED Matrix panel
- Adafruit RGB Matrix HAT or compatible hardware
- Power supply appropriate for your LED matrix (5V, typically 2-4A depending on brightness)

### Automatic Installation

The RGB LED Matrix support is included in the main Nodeice Board installation script. When running `install_service.sh`, you'll be prompted to enable RGB LED Matrix support:

```bash
sudo ./install_service.sh
```

When prompted, select 'y' to install the RGB LED Matrix support. The script will:

1. Install required dependencies
2. Clone and build the rpi-rgb-led-matrix library
3. Set up proper permissions for GPIO access
4. Update the configuration to enable the LED matrix
5. Make the test scripts executable

### Manual Installation

If you prefer to set up the RGB LED Matrix support manually:

1. Install required dependencies:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-dev python3-pillow libgraphicsmagick++-dev libwebp-dev
   ```

2. Clone the rpi-rgb-led-matrix repository:
   ```bash
   git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
   cd rpi-rgb-led-matrix
   make
   cd bindings/python
   make build-python
   sudo make install-python
   ```

3. Set up permissions for GPIO access:
   ```bash
   # Add user to gpio group if it exists
   if getent group gpio > /dev/null; then
       sudo usermod -a -G gpio $USER
   fi
   
   # Make sure /dev/gpiomem is accessible
   if [ -e /dev/gpiomem ]; then
       sudo chmod a+rw /dev/gpiomem
   fi
   
   # Add user to i2c and spi groups if they exist
   if getent group i2c > /dev/null; then
       sudo usermod -a -G i2c $USER
   fi
   
   if getent group spi > /dev/null; then
       sudo usermod -a -G spi $USER
   fi
   ```

4. Update your config.yaml to enable the LED matrix:
   ```yaml
   Nodeice_board:
     # Other settings...
     LED_Matrix:
       Enabled: true
       Hardware_Mapping: "adafruit-hat"
       # Other LED matrix settings...
   ```

### Testing the LED Matrix

Two test scripts are provided to verify your LED matrix setup:

1. Permission Test:
   ```bash
   ./test_led_permissions.sh
   ```
   This script checks if your system is properly configured for the LED matrix.

2. Display Test:
   ```bash
   ./test_led_matrix.py
   ```
   This script tests various display functions.

You can test specific features with the `--test` option:
```bash
./test_led_matrix.py --test logo
./test_led_matrix.py --test text
./test_led_matrix.py --test status
./test_led_matrix.py --test message
```

### Troubleshooting

If you encounter issues with the LED matrix:

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

For more detailed information about the RGB LED Matrix functionality, see the [LED Matrix Documentation](LED_MATRIX_README.md).

## Monitoring and Maintenance

### Checking Service Status

```bash
sudo systemctl status nodeice-board.service  # sudo required
```

**Note:** All systemctl commands require sudo privileges because they interact with system services.

### Viewing Logs

View all logs:
```bash
sudo journalctl -u nodeice-board.service  # sudo required
```

Follow logs in real-time:
```bash
sudo journalctl -u nodeice-board.service -f  # sudo required
```

View logs since the last boot:
```bash
sudo journalctl -u nodeice-board.service -b  # sudo required
```

### Common Service Commands

- Start the service: `sudo systemctl start nodeice-board.service`
- Stop the service: `sudo systemctl stop nodeice-board.service`
- Restart the service: `sudo systemctl restart nodeice-board.service`
- Disable auto-start at boot: `sudo systemctl disable nodeice-board.service`
- Re-enable auto-start at boot: `sudo systemctl enable nodeice-board.service`

### Setting Up Log Rotation

To prevent logs from filling up your disk space, set up log rotation:

```bash
sudo nano /etc/logrotate.d/nodeice-board
```

Add the following content:

```
/var/log/nodeice-board/nodeice_board.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 pi pi
}
```

## Troubleshooting

### Service Fails to Start

1. Check the logs:
   ```bash
   sudo journalctl -u nodeice-board.service -n 50  # sudo required - accessing system logs
   ```

2. Verify the Meshtastic device is connected:
   ```bash
   ls -l /dev/ttyUSB*  # no sudo needed for listing devices
   ```
   or
   ```bash
   ls -l /dev/ttyACM*  # no sudo needed for listing devices
   ```

3. Check Python version:
   ```bash
   python3 --version  # no sudo needed
   ```
   Ensure it's 3.9 or higher.

4. Test running the application manually:
   ```bash
   cd /path/to/nodeice-board
   source venv/bin/activate
   python main.py  # no sudo needed for testing
   ```

### USB Device Permission Issues

If the service can't access the USB device:

1. Add your user to the `dialout` group:
   ```bash
   sudo usermod -a -G dialout $USER  # sudo required - modifying system groups
   ```
   (Log out and back in for this to take effect)

2. Create a udev rule for the Meshtastic device:
   ```bash
   sudo nano /etc/udev/rules.d/99-meshtastic.rules  # sudo required - writing to system directory
   ```
   
   Add:
   ```
   SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", SYMLINK+="meshtastic"
   ```
   (Adjust vendor and product IDs as needed for your specific device)

3. Reload udev rules:
   ```bash
   sudo udevadm control --reload-rules  # sudo required - managing system services
   sudo udevadm trigger  # sudo required - managing system services
   ```

## Instance Management

Nodeice Board includes a mechanism to prevent multiple instances from running simultaneously, which helps avoid conflicts and resource issues:

1. Make the instance management script executable:
   ```bash
   chmod +x kill_previous_instances.sh
   ```

2. The script is automatically called when starting the application:
   ```bash
   # This happens automatically when you run the application
   python main.py  # Will automatically check for and terminate any previous instances
   ```

This feature:
- Detects any running instances of Nodeice Board
- Safely terminates them before starting a new instance
- Logs termination events for monitoring
- Works with both manual execution and systemd service
- Prevents potential database conflicts and resource contention

## Updating

To update Nodeice Board:

1. Pull the latest changes:
   ```bash
   cd /path/to/nodeice-board
   git pull  # no sudo needed for git operations
   ```

2. Update dependencies:
   ```bash
   source venv/bin/activate
   pip install -e .  # no sudo needed when using virtualenv
   ```

3. Make sure the instance management script is executable:
   ```bash
   chmod +x kill_previous_instances.sh
   ```

4. Restart the service:
   ```bash
   sudo systemctl restart nodeice-board.service  # sudo required - managing systemd
   ```

Note: You don't need to manually stop the service before restarting it. The application will automatically detect and terminate any previous instances when it starts.

## Advanced Configuration

### Running on a Different Port

If you need to modify how the application connects to the Meshtastic device, you can specify the device path in the service file:

```
ExecStart=/home/pi/nodeice-board/venv/bin/python /home/pi/nodeice-board/main.py --device_path=/dev/ttyUSB0
```

### Auto-Restart on Failure

The service is configured to restart automatically on failure. You can adjust the restart behavior by modifying these lines in the service file:

```
Restart=on-failure
RestartSec=30
```

Options for `Restart` include:
- `no`: Don't restart (default)
- `on-success`: Restart only when the service exits successfully
- `on-failure`: Restart when the service exits with a non-zero exit code
- `on-abnormal`: Restart when the service is terminated by a signal
- `on-abort`: Restart when the service is aborted
- `on-watchdog`: Restart when the watchdog timeout expires
- `always`: Always restart regardless of exit code

### Setting Up Automatic Updates

Nodeice Board includes an automatic update mechanism that checks for updates on the GitHub repository every 24 hours and applies them if available.

#### Automatic Setup (Recommended)

Use the provided installation script:

```bash
chmod +x install_auto_update.sh
sudo ./install_auto_update.sh  # sudo required
```

**Why sudo is required:** This script needs root privileges to:
- Set up a cron job for automatic updates
- Create log directories
- Restart the service after updates

The script will:
- Make the auto_update.sh script executable
- Set up a cron job to check for updates daily at 3 AM
- Create necessary log directories
- Optionally run an initial update check

#### Manual Setup

If you prefer to set up the auto-update mechanism manually:

1. Make the auto-update script executable:
   ```bash
   chmod +x auto_update.sh
   ```

2. Create a cron job to run the script daily:
   ```bash
   sudo crontab -e  # sudo required - editing system crontab
   ```

   Add the following line to check for updates daily at 3 AM:
   ```
   0 3 * * * /path/to/nodeice-board/auto_update.sh >> /var/log/nodeice-board/auto_update.log 2>&1
   ```

#### How It Works

The auto-update mechanism:
1. Checks for updates on the GitHub repository
2. Compares the local version with the remote version
3. If updates are available:
   - Creates a backup of important files
   - Pulls the latest changes
   - Updates dependencies
   - Restarts the service
4. Logs all actions to `/var/log/nodeice-board/auto_update.log`

#### Manual Update Check

To manually check for and apply updates:

```bash
sudo ./auto_update.sh  # sudo required for service restart
```

#### Viewing Update Logs

To view the auto-update logs:

```bash
cat /var/log/nodeice-board/auto_update.log
```

Or to follow the logs in real-time during an update:

```bash
tail -f /var/log/nodeice-board/auto_update.log
```

### Monitoring with Healthchecks

To monitor the health of your Nodeice Board service, you can set up a simple healthcheck script:

1. Create a healthcheck script:
   ```bash
   nano /home/pi/nodeice-board/healthcheck.sh  # no sudo needed if in your home directory
   ```

2. Add the following content:
   ```bash
   #!/bin/bash
   
   if systemctl is-active --quiet nodeice-board.service; then
     curl -fsS -m 10 --retry 5 https://hc-ping.com/YOUR-UUID-HERE > /dev/null
   else
     curl -fsS -m 10 --retry 5 https://hc-ping.com/YOUR-UUID-HERE/fail > /dev/null
   fi
   ```

3. Make it executable:
   ```bash
   chmod +x /home/pi/nodeice-board/healthcheck.sh  # no sudo needed if you own the file
   ```

4. Add it to crontab to run every 15 minutes:
   ```bash
   (crontab -l 2>/dev/null; echo "*/15 * * * * /home/pi/nodeice-board/healthcheck.sh") | crontab -  # no sudo needed for user crontab
   ```

### Running Multiple Instances

If you need to run multiple instances of Nodeice Board (for different Meshtastic devices), you'll need to configure them to avoid the automatic instance management from terminating each other:

1. Create separate service files with different names:
   ```bash
   sudo cp /etc/systemd/system/nodeice-board.service /etc/systemd/system/nodeice-board-2.service  # sudo required - writing to system directory
   ```

2. Edit the new service file to use different paths and parameters:
   ```bash
   sudo nano /etc/systemd/system/nodeice-board-2.service  # sudo required - editing system file
   ```

3. Modify the ExecStart line to include a unique identifier that will prevent the instance management from terminating the other instance:
   ```
   ExecStart=/home/pi/nodeice-board/venv/bin/python /home/pi/nodeice-board/main.py --db_path=/path/to/nodeice_board_2.db
   ```

   By using different database paths, each instance will have its own unique command line, which the instance management script uses to differentiate between instances.

4. Make sure each instance uses:
   - Different database files (--db_path)
   - Different Meshtastic devices (--device_path) if applicable
   - Different working directories if running completely separate installations

This configuration ensures that each instance will only terminate previous versions of itself, not other configured instances.
