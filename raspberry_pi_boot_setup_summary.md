# Nodeice Board Raspberry Pi Boot Setup

This document provides an overview of the files created to help set up Nodeice Board to run automatically at boot on a Raspberry Pi.

## Files Overview

| File | Purpose |
|------|---------|
| `install_service.sh` | Main installation script that sets up Nodeice Board as a systemd service |
| `setup_meshtastic_device.sh` | Helper script for detecting and configuring Meshtastic devices |
| `check_nodeice_status.sh` | Status check script that provides monitoring information |
| `raspberry_pi_setup.md` | Comprehensive documentation for Raspberry Pi setup |

## Installation Script (`install_service.sh`)

This script automates the process of setting up Nodeice Board as a systemd service that runs automatically at boot.

**Key Features:**
- Checks prerequisites (Python version, Meshtastic device)
- Installs required dependencies
- Sets up a Python virtual environment
- Creates and configures a systemd service
- Enables the service to start at boot
- Creates a log directory and symlink

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
- Advanced Configuration

## Systemd Service File

The installation script creates a systemd service file at `/etc/systemd/system/nodeice-board.service` with the following features:

- Proper service dependencies
- Automatic restart on failure
- Security hardening
- Environment variable configuration
- Standard logging to the journal

## Getting Started

1. Transfer all files to your Raspberry Pi
2. Make the scripts executable:
   ```bash
   chmod +x install_service.sh setup_meshtastic_device.sh check_nodeice_status.sh
   ```
3. Run the installation script (sudo REQUIRED):
   ```bash
   sudo ./install_service.sh
   ```
   **Why sudo is required:** This script needs root privileges to install system packages, create systemd service files, create log directories, and manage systemd services.

4. If you have issues with the Meshtastic device (sudo recommended for full functionality):
   ```bash
   sudo ./setup_meshtastic_device.sh
   ```
   **Sudo requirements:** Full functionality requires sudo. Some options (device detection, connection testing) will work without sudo, but critical functions (udev rules, adding user to dialout group) require sudo.

5. Check the status (sudo recommended for full access):
   ```bash
   sudo ./check_nodeice_status.sh
   ```
   **Sudo requirements:** Works best with sudo for full access to service status and logs. Can run without sudo but with limited functionality.

## Additional Notes

- The scripts are designed to be run on a Raspberry Pi or similar Linux system
- All scripts include color-coded output for better readability
- The installation script preserves the ownership of files
- The service is configured to restart automatically if it crashes
- Log rotation is recommended to prevent logs from filling up disk space

For more detailed information, refer to the [Raspberry Pi Setup Guide](raspberry_pi_setup.md).
