# Nodeice Board Raspberry Pi Boot Setup

This document provides an overview of the files created to help set up Nodeice Board to run automatically at boot on a Raspberry Pi.

## Files Overview

| File | Purpose |
|------|---------|
| `install_service.sh` | Main installation script that sets up Nodeice Board as a systemd service |
| `setup_meshtastic_device.sh` | Helper script for detecting and configuring Meshtastic devices |
| `check_nodeice_status.sh` | Status check script that provides monitoring information |
| `auto_update.sh` | Script that checks for and applies updates from GitHub |
| `install_auto_update.sh` | Script that sets up the auto-update mechanism |
| `test_led_matrix.py` | Script to test the RGB LED Matrix display functionality |
| `test_led_permissions.sh` | Script to verify proper permissions for the LED matrix |
| `raspberry_pi_setup.md` | Comprehensive documentation for Raspberry Pi setup |
| `LED_MATRIX_README.md` | Detailed documentation for the RGB LED Matrix functionality |

## Installation Script (`install_service.sh`)

This script automates the process of setting up Nodeice Board as a systemd service that runs automatically at boot.

**Key Features:**
- Checks prerequisites (Python version, Meshtastic device)
- Installs required dependencies
- Sets up a Python virtual environment
- Creates and configures a systemd service
- Enables the service to start at boot
- Creates a log directory and symlink
- Optionally installs and configures RGB LED Matrix support

**Usage:**
```bash
chmod +x install_service.sh
sudo ./install_service.sh  # sudo REQUIRED
```

## Meshtastic Device Setup Script (`setup_meshtastic_device.sh`)

This script helps detect and configure Meshtastic devices for use with Nodeice Board.

**Key Features:**
- Detects connected USB devices that might be Meshtastic devices
- Sets up udev rules for persistent device naming
- Adds the user to the dialout group for device access
- Tests the connection to the Meshtastic device

**Usage:**
```bash
chmod +x setup_meshtastic_device.sh
sudo ./setup_meshtastic_device.sh  # sudo recommended for full functionality
```

## Status Check Script (`check_nodeice_status.sh`)

This script checks the status of the Nodeice Board service and provides basic monitoring information.

**Key Features:**
- Checks if the service is installed, enabled, and running
- Displays service uptime and resource usage
- Detects Meshtastic devices
- Shows log file status and recent entries
- Provides database statistics
- Displays system information

**Usage:**
```bash
chmod +x check_nodeice_status.sh
sudo ./check_nodeice_status.sh  # sudo recommended for full access
```

## Documentation (`raspberry_pi_setup.md`)

This comprehensive guide provides detailed instructions for setting up Nodeice Board on a Raspberry Pi.

**Key Sections:**
- Automatic Installation
- Manual Installation
- Configuration Options
- Monitoring and Maintenance
- Troubleshooting
- Updating
- Advanced Configuration (including Automatic Updates)

## Systemd Service File

The installation script creates a systemd service file at `/etc/systemd/system/nodeice-board.service` with the following features:

- Proper service dependencies
- Automatic restart on failure
- Security hardening
- Environment variable configuration
- Standard logging to the journal

## Auto-Update Script (`auto_update.sh`)

This script checks for updates on the GitHub repository and automatically applies them if available.

**Key Features:**
- Checks for updates by comparing local and remote Git commit hashes
- Creates backups of important files before updating
- Pulls the latest changes from GitHub
- Updates dependencies in the virtual environment
- Restarts the service after updating
- Provides detailed logging of all actions

**Usage:**
```bash
sudo ./auto_update.sh  # sudo required for service restart
```

## Auto-Update Installation Script (`install_auto_update.sh`)

This script sets up the auto-update mechanism to run automatically every 24 hours.

**Key Features:**
- Makes the auto_update.sh script executable
- Sets up a cron job to run the script daily at 3 AM
- Creates necessary log directories
- Optionally runs an initial update check

**Usage:**
```bash
chmod +x install_auto_update.sh
sudo ./install_auto_update.sh  # sudo required
```

## RGB LED Matrix Support

The installation script includes support for setting up an RGB LED Matrix display for the Nodeice Board.

**Key Features:**
- Installs the rpi-rgb-led-matrix library and dependencies
- Sets up proper permissions for GPIO access
- Configures the LED matrix in the config.yaml file
- Provides test scripts for verifying the setup

**Test Scripts:**
- `test_led_matrix.py`: Tests various display functions (logo, text, status screens, message effects)
- `test_led_permissions.sh`: Verifies proper permissions and configuration for the LED matrix

## Getting Started

1. Transfer all files to your Raspberry Pi
2. Make the scripts executable:
   ```bash
   chmod +x install_service.sh setup_meshtastic_device.sh check_nodeice_status.sh auto_update.sh install_auto_update.sh test_led_matrix.py test_led_permissions.sh
   ```
3. Run the installation script (sudo REQUIRED):
   ```bash
   sudo ./install_service.sh
   ```
   **Why sudo is required:** This script needs root privileges to install system packages, create systemd service files, create log directories, manage systemd services, and set up permissions for the RGB LED Matrix.

4. When prompted, choose whether to enable RGB LED Matrix support:
   ```
   Do you want to enable RGB LED Matrix support? (y/n)
   ```
   If you select 'y', the script will install and configure the RGB LED Matrix support.

5. If you have issues with the Meshtastic device (sudo recommended for full functionality):
   ```bash
   sudo ./setup_meshtastic_device.sh
   ```
   **Sudo requirements:** Full functionality requires sudo. Some options (device detection, connection testing) will work without sudo, but critical functions (udev rules, adding user to dialout group) require sudo.

6. Check the status (sudo recommended for full access):
   ```bash
   sudo ./check_nodeice_status.sh
   ```
   **Sudo requirements:** Works best with sudo for full access to service status and logs. Can run without sudo but with limited functionality.

7. Set up automatic updates (optional but recommended):
   ```bash
   sudo ./install_auto_update.sh
   ```
   **Why sudo is required:** This script needs root privileges to set up a cron job, create log directories, and restart the service after updates.

8. If you enabled RGB LED Matrix support, test it with:
   ```bash
   ./test_led_matrix.py
   ```
   And check permissions with:
   ```bash
   ./test_led_permissions.sh
   ```

## Additional Notes

- The scripts are designed to be run on a Raspberry Pi or similar Linux system
- All scripts include color-coded output for better readability
- The installation script preserves the ownership of files
- The service is configured to restart automatically if it crashes
- Log rotation is recommended to prevent logs from filling up disk space
- The RGB LED Matrix display requires a Raspberry Pi with GPIO pins and an RGB LED Matrix panel
- For detailed information about the RGB LED Matrix functionality, refer to the [LED Matrix Documentation](LED_MATRIX_README.md)

For more detailed information, refer to the [Raspberry Pi Setup Guide](raspberry_pi_setup.md).
