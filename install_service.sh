#!/bin/bash

# Nodeice Board Service Installation Script
# This script installs Nodeice Board as a systemd service on Raspberry Pi
# to run automatically at boot.

set -e  # Exit on error

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== Nodeice Board Service Installation =====${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
  exit 1
fi

# Get the current user (the one who invoked sudo)
if [ -n "$SUDO_USER" ]; then
  CURRENT_USER=$SUDO_USER
else
  CURRENT_USER=$(whoami)
fi

# Get the absolute path of the project directory
PROJECT_DIR=$(pwd)
echo -e "Installing from: ${PROJECT_DIR}"

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
python_major=$(echo $python_version | cut -d. -f1)
python_minor=$(echo $python_version | cut -d. -f2)

if [ "$python_major" -lt 3 ] || [ "$python_major" -eq 3 -a "$python_minor" -lt 9 ]; then
    echo -e "${RED}Error: Nodeice Board requires Python 3.9 or higher.${NC}"
    echo -e "Current Python version: $python_version"
    echo -e "Please upgrade Python and try again."
    exit 1
fi

echo -e "Python version $python_version - ${GREEN}OK${NC}"

# Check if Meshtastic device is connected
echo -e "${YELLOW}Checking for Meshtastic device...${NC}"
if ! ls /dev/ttyUSB* &> /dev/null && ! ls /dev/ttyACM* &> /dev/null; then
    echo -e "${YELLOW}Warning: No USB devices detected that might be Meshtastic devices.${NC}"
    echo -e "Make sure your Meshtastic device is connected before starting the service."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Installation aborted.${NC}"
        exit 1
    fi
else
    echo -e "USB devices detected - ${GREEN}OK${NC}"
fi

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
apt-get update
apt-get install -y python3-pip python3-venv

# Create a virtual environment if it doesn't exist
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$PROJECT_DIR/venv"
fi

# Install the package in development mode
echo -e "${YELLOW}Installing Nodeice Board and dependencies...${NC}"
sudo -u $CURRENT_USER "$PROJECT_DIR/venv/bin/pip" install -e "$PROJECT_DIR"

# Create the systemd service file
echo -e "${YELLOW}Creating systemd service file...${NC}"
cat > /etc/systemd/system/nodeice-board.service << EOF
[Unit]
Description=Nodeice Board Meshtastic Notice Board
Documentation=https://github.com/AndreasThinks/nodeice-board
After=network.target
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/main.py
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
EOF

echo -e "${GREEN}Service file created at /etc/systemd/system/nodeice-board.service${NC}"

# Create a log directory
LOG_DIR="/var/log/nodeice-board"
echo -e "${YELLOW}Creating log directory at $LOG_DIR...${NC}"
mkdir -p $LOG_DIR
chown $CURRENT_USER:$CURRENT_USER $LOG_DIR

# Create a symlink to the log file
ln -sf $PROJECT_DIR/nodeice_board.log $LOG_DIR/nodeice_board.log

# Reload systemd to recognize the new service
echo -e "${YELLOW}Reloading systemd...${NC}"
systemctl daemon-reload

# Enable the service to start at boot
echo -e "${YELLOW}Enabling service to start at boot...${NC}"
systemctl enable nodeice-board.service

# Ask if the user wants to start the service now
echo
read -p "Do you want to start the Nodeice Board service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Starting Nodeice Board service...${NC}"
    systemctl start nodeice-board.service
    
    # Check if the service started successfully
    sleep 2
    if systemctl is-active --quiet nodeice-board.service; then
        echo -e "${GREEN}Nodeice Board service started successfully!${NC}"
    else
        echo -e "${RED}Failed to start Nodeice Board service.${NC}"
        echo -e "Check the logs with: ${YELLOW}sudo journalctl -u nodeice-board.service${NC}"
    fi
fi

echo
echo -e "${GREEN}===== Installation Complete! =====${NC}"
echo
echo -e "The Nodeice Board service is now installed and will start automatically at boot."
echo
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  ${GREEN}sudo systemctl start nodeice-board.service${NC}   - Start the service"
echo -e "  ${GREEN}sudo systemctl stop nodeice-board.service${NC}    - Stop the service"
echo -e "  ${GREEN}sudo systemctl restart nodeice-board.service${NC} - Restart the service"
echo -e "  ${GREEN}sudo systemctl status nodeice-board.service${NC}  - Check service status"
echo -e "  ${GREEN}sudo journalctl -u nodeice-board.service${NC}     - View service logs"
echo -e "  ${GREEN}sudo journalctl -u nodeice-board.service -f${NC}  - Follow service logs"
echo
echo -e "For more information, see the README.md file or visit:"
echo -e "${GREEN}https://github.com/AndreasThinks/nodeice-board${NC}"
echo
