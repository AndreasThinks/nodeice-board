#!/bin/bash

# Nodeice Board Service Installation Script

set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}===== Nodeice Board Service Installation =====${NC}"

# Must be run as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
  exit 1
fi

# Get invoking user
if [ -n "$SUDO_USER" ]; then
  CURRENT_USER=$SUDO_USER
else
  CURRENT_USER=$(whoami)
fi

PROJECT_DIR=$(pwd)
echo -e "Installing from: ${PROJECT_DIR}"

# Python version check
echo -e "${YELLOW}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
python_major=$(echo $python_version | cut -d. -f1)
python_minor=$(echo $python_version | cut -d. -f2)

if [ "$python_major" -lt 3 ] || { [ "$python_major" -eq 3 ] && [ "$python_minor" -lt 9 ]; }; then
    echo -e "${RED}Error: Nodeice Board requires Python 3.9 or higher.${NC}"
    exit 1
fi
echo -e "Python version $python_version - ${GREEN}OK${NC}"

# Check for USB devices
echo -e "${YELLOW}Checking for Meshtastic device...${NC}"
if ! ls /dev/ttyUSB* &> /dev/null && ! ls /dev/ttyACM* &> /dev/null; then
    echo -e "${YELLOW}Warning: No USB devices detected.${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Installation aborted.${NC}"
        exit 1
    fi
else
    echo -e "USB devices detected - ${GREEN}OK${NC}"
fi

# System dependencies
echo -e "${YELLOW}Installing system dependencies...${NC}"
apt-get update
apt-get install -y python3-pip python3-venv

# Remove any old venv (created as root)
if [ -d "$PROJECT_DIR/venv" ]; then
    echo -e "${YELLOW}Removing old virtual environment...${NC}"
    rm -rf "$PROJECT_DIR/venv"
fi

# Create venv and install packages as the regular user
echo -e "${YELLOW}Creating virtual environment and installing dependencies...${NC}"
sudo -u "$CURRENT_USER" bash << EOF
set -e  # Exit on error
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools
pip install -e .
EOF

# Check if the subshell completed successfully
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to set up virtual environment or install dependencies.${NC}"
    exit 1
fi

# Ensure venv was created successfully
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo -e "${RED}Error: Failed to create virtual environment.${NC}"
    exit 1
fi

# Set executable permissions
echo -e "${YELLOW}Setting up instance management...${NC}"
chmod +x "$PROJECT_DIR/kill_previous_instances.sh"

# Create systemd service
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
KillMode=mixed
TimeoutStopSec=10
ProtectSystem=full
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Service file created at /etc/systemd/system/nodeice-board.service${NC}"

# Log directory
LOG_DIR="/var/log/nodeice-board"
echo -e "${YELLOW}Creating log directory at $LOG_DIR...${NC}"
mkdir -p $LOG_DIR
chown $CURRENT_USER:$CURRENT_USER $LOG_DIR
ln -sf "$PROJECT_DIR/nodeice_board.log" "$LOG_DIR/nodeice_board.log"

# Enable service
echo -e "${YELLOW}Reloading systemd...${NC}"
systemctl daemon-reload
systemctl enable nodeice-board.service

# Check for RGB LED Matrix support
echo
echo -e "${BLUE}===== RGB LED Matrix Support =====${NC}"
read -p "Do you want to enable RGB LED Matrix support? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Installing RGB LED Matrix library...${NC}"
    
    # Install required dependencies
    apt-get update
    apt-get install -y python3-dev python3-pillow libgraphicsmagick++-dev libwebp-dev
    
    # Clone the rpi-rgb-led-matrix repository if it doesn't exist
    if [ ! -d "rpi-rgb-led-matrix" ]; then
        echo -e "${YELLOW}Cloning rpi-rgb-led-matrix repository...${NC}"
        sudo -u "$CURRENT_USER" git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
    else
        echo -e "${YELLOW}Updating existing rpi-rgb-led-matrix repository...${NC}"
        cd rpi-rgb-led-matrix
        sudo -u "$CURRENT_USER" git pull
        cd ..
    fi
    
    # Build and install the library
    echo -e "${YELLOW}Building and installing the RGB Matrix library...${NC}"
    cd rpi-rgb-led-matrix
    sudo -u "$CURRENT_USER" make
    cd bindings/python
    sudo -u "$CURRENT_USER" bash << EOF
set -e
cd "$PROJECT_DIR/rpi-rgb-led-matrix/bindings/python"
source "$PROJECT_DIR/venv/bin/activate"
make build-python
make install-python
EOF
    
    # Set up permissions for GPIO access
    echo -e "${YELLOW}Setting up permissions for GPIO access...${NC}"
    
    # Add current user to gpio group if it exists
    if getent group gpio > /dev/null; then
        usermod -a -G gpio "$CURRENT_USER"
        echo -e "Added user to gpio group"
    fi
    
    # Make sure /dev/gpiomem is accessible
    if [ -e /dev/gpiomem ]; then
        chmod a+rw /dev/gpiomem
        echo -e "Set permissions on /dev/gpiomem"
    fi
    
    # Add user to i2c and spi groups if they exist
    if getent group i2c > /dev/null; then
        usermod -a -G i2c "$CURRENT_USER"
        echo -e "Added user to i2c group"
    fi
    
    if getent group spi > /dev/null; then
        usermod -a -G spi "$CURRENT_USER"
        echo -e "Added user to spi group"
    fi
    
    # Update config.yaml to enable LED matrix if not already enabled
    echo -e "${YELLOW}Updating configuration...${NC}"
    if grep -q "LED_Matrix:" "$PROJECT_DIR/config.yaml"; then
        # LED_Matrix section exists, make sure it's enabled
        sed -i 's/Enabled: false/Enabled: true/' "$PROJECT_DIR/config.yaml"
    else
        # LED_Matrix section doesn't exist, add it
        cat >> "$PROJECT_DIR/config.yaml" << EOF

  LED_Matrix:
    Enabled: true
    Hardware_Mapping: "adafruit-hat"
    Rows: 32
    Cols: 32
    Chain_Length: 1
    Parallel: 1
    Brightness: 50
    GPIO_Slowdown: 2
    Display_Mode: "standard"
    Status_Cycle_Seconds: 5
    Message_Effect: "rainbow"
    Interactive: true
    Auto_Brightness: true
EOF
    fi
    
    # Make test scripts executable
    chmod +x "$PROJECT_DIR/test_led_matrix.py"
    chmod +x "$PROJECT_DIR/test_led_permissions.sh"
    
    echo -e "${GREEN}RGB LED Matrix support installed!${NC}"
    echo -e "You can test the LED matrix with: ${YELLOW}./test_led_matrix.py${NC}"
    echo -e "You can check permissions with: ${YELLOW}./test_led_permissions.sh${NC}"
    
    # Return to project directory
    cd "$PROJECT_DIR"
else
    echo -e "${YELLOW}Skipping RGB LED Matrix installation.${NC}"
fi

# Prompt to start
echo
read -p "Do you want to start the Nodeice Board service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Starting Nodeice Board service...${NC}"
    systemctl start nodeice-board.service
    sleep 2
    if systemctl is-active --quiet nodeice-board.service; then
        echo -e "${GREEN}Nodeice Board service started successfully!${NC}"
    else
        echo -e "${RED}Failed to start Nodeice Board service.${NC}"
        echo -e "Check logs with: ${YELLOW}sudo journalctl -u nodeice-board.service${NC}"
    fi
fi

# Final info
echo
echo -e "${GREEN}===== Installation Complete! =====${NC}"
echo
echo -e "The Nodeice Board service is now installed and will start automatically at boot."
echo
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  ${GREEN}sudo systemctl start nodeice-board.service${NC}"
echo -e "  ${GREEN}sudo systemctl stop nodeice-board.service${NC}"
echo -e "  ${GREEN}sudo systemctl restart nodeice-board.service${NC}"
echo -e "  ${GREEN}sudo systemctl status nodeice-board.service${NC}"
echo -e "  ${GREEN}sudo journalctl -u nodeice-board.service${NC}"
echo -e "  ${GREEN}sudo journalctl -u nodeice-board.service -f${NC}"
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}RGB LED Matrix commands:${NC}"
    echo -e "  ${GREEN}./test_led_matrix.py${NC} - Test the LED matrix display"
    echo -e "  ${GREEN}./test_led_permissions.sh${NC} - Check LED matrix permissions"
    echo
fi
echo -e "For more information, visit:"
echo -e "${GREEN}https://github.com/AndreasThinks/nodeice-board${NC}"
