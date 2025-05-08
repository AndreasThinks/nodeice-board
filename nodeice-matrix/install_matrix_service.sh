#!/bin/bash

# Nodeice Matrix Display Service Installation Script

set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}===== Nodeice Matrix Display Service Installation =====${NC}"

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

if [ "$python_major" -lt 3 ] || { [ "$python_major" -eq 3 ] && [ "$python_minor" -lt 7 ]; }; then
    echo -e "${RED}Error: Nodeice Matrix Display requires Python 3.7 or higher.${NC}"
    exit 1
fi
echo -e "Python version $python_version - ${GREEN}OK${NC}"

# Install system dependencies
echo -e "${YELLOW}Installing system dependencies...${NC}"
apt-get update
apt-get install -y python3-pip git build-essential python3-dev python3-pillow curl

# Install uv for the current user (not root)
echo -e "${YELLOW}Installing uv package manager for $CURRENT_USER...${NC}"
sudo -u "$CURRENT_USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

# Add the user's cargo bin to PATH temporarily for the which command
USER_CARGO_BIN="/home/$CURRENT_USER/.cargo/bin"
export PATH="$USER_CARGO_BIN:$PATH"

# Find the full path to uv using which
UV_PATH=$(which uv)
if [ -z "$UV_PATH" ]; then
    echo -e "${RED}Error: Could not find uv executable. Please check the installation.${NC}"
    exit 1
fi
echo -e "uv found at $UV_PATH - ${GREEN}OK${NC}"
echo -e "uv version $($UV_PATH --version) - ${GREEN}OK${NC}"

# Create requirements.txt file
echo -e "${YELLOW}Creating requirements.txt file...${NC}"
cat > requirements.txt << EOF
pillow>=9.0.0
pyyaml>=6.0
EOF

# Create virtual environment using uv
echo -e "${YELLOW}Creating virtual environment with uv...${NC}"
sudo -u "$CURRENT_USER" "$UV_PATH" venv

# Install dependencies using uv
echo -e "${YELLOW}Installing dependencies with uv...${NC}"
sudo -u "$CURRENT_USER" "$UV_PATH" pip install -r requirements.txt

# Install rpi-rgb-led-matrix library
echo -e "${YELLOW}Installing rpi-rgb-led-matrix library...${NC}"
if [ ! -d "rpi-rgb-led-matrix" ]; then
  git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
fi

# Build and install the RGB matrix library into the virtual environment
echo -e "${YELLOW}Building and installing RGB matrix library into virtual environment...${NC}"
cd rpi-rgb-led-matrix
make build-python PYTHON=$(which python3)
cd ..

# Install the RGB matrix library into the virtual environment
echo -e "${YELLOW}Installing RGB matrix library into virtual environment...${NC}"
sudo -u "$CURRENT_USER" "$UV_PATH" pip install -e ./rpi-rgb-led-matrix/bindings/python

# Verify installation
echo -e "${YELLOW}Verifying RGB matrix library installation...${NC}"
sudo -u "$CURRENT_USER" bash -c "source .venv/bin/activate && python -c \"import rgbmatrix; print('RGB Matrix library installed successfully')\""

# Create fonts directory and download fonts
echo -e "${YELLOW}Downloading fonts...${NC}"
mkdir -p fonts
cd fonts

# Download fonts from the rpi-rgb-led-matrix repository
if [ ! -f "4x6.bdf" ]; then
  wget -q https://raw.githubusercontent.com/hzeller/rpi-rgb-led-matrix/master/fonts/4x6.bdf
fi
if [ ! -f "6x9.bdf" ]; then
  wget -q https://raw.githubusercontent.com/hzeller/rpi-rgb-led-matrix/master/fonts/6x9.bdf
fi
if [ ! -f "8x13.bdf" ]; then
  wget -q https://raw.githubusercontent.com/hzeller/rpi-rgb-led-matrix/master/fonts/8x13.bdf
fi

cd ..

# Make the main script executable
echo -e "${YELLOW}Making scripts executable...${NC}"
chmod +x matrix_display.py

# Create systemd service
echo -e "${YELLOW}Creating systemd service file...${NC}"
cat > /etc/systemd/system/nodeice-matrix.service << EOF
[Unit]
Description=Nodeice Board Matrix Display
Documentation=https://github.com/AndreasThinks/nodeice-board
After=network.target
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/matrix_display.py
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

echo -e "${GREEN}Service file created at /etc/systemd/system/nodeice-matrix.service${NC}"

# Create log directory
LOG_DIR="/var/log/nodeice-matrix"
echo -e "${YELLOW}Creating log directory at $LOG_DIR...${NC}"
mkdir -p $LOG_DIR
chown $CURRENT_USER:$CURRENT_USER $LOG_DIR

# Enable service
echo -e "${YELLOW}Reloading systemd...${NC}"
systemctl daemon-reload
systemctl enable nodeice-matrix.service

# Prompt to start
echo
read -p "Do you want to start the Nodeice Matrix Display service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Starting Nodeice Matrix Display service...${NC}"
    systemctl start nodeice-matrix.service
    sleep 2
    if systemctl is-active --quiet nodeice-matrix.service; then
        echo -e "${GREEN}Nodeice Matrix Display service started successfully!${NC}"
    else
        echo -e "${RED}Failed to start Nodeice Matrix Display service.${NC}"
        echo -e "Check logs with: ${YELLOW}sudo journalctl -u nodeice-matrix.service${NC}"
    fi
fi

# Final info
echo
echo -e "${GREEN}===== Installation Complete! =====${NC}"
echo
echo -e "The Nodeice Matrix Display service is now installed and will start automatically at boot."
echo
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  ${GREEN}sudo systemctl start nodeice-matrix.service${NC}"
echo -e "  ${GREEN}sudo systemctl stop nodeice-matrix.service${NC}"
echo -e "  ${GREEN}sudo systemctl restart nodeice-matrix.service${NC}"
echo -e "  ${GREEN}sudo systemctl status nodeice-matrix.service${NC}"
echo -e "  ${GREEN}sudo journalctl -u nodeice-matrix.service${NC}"
echo -e "  ${GREEN}sudo journalctl -u nodeice-matrix.service -f${NC}"
echo
echo -e "For more information, visit:"
echo -e "${GREEN}https://github.com/AndreasThinks/nodeice-board${NC}"
