#!/bin/bash

# Nodeice Board Matrix Display - Service Installation Script
#
# Sets up the optional RGB LED matrix display (nodeice_board/matrix) as a
# systemd service. Designed for a HUB75 panel on an Adafruit RGB Matrix
# Bonnet, driven by the rpi-rgb-led-matrix library.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}===== Nodeice Board Matrix Display Installation =====${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
  exit 1
fi

PROJECT_DIR=$(pwd)
echo -e "Installing from: ${PROJECT_DIR}"

if [ ! -f "$PROJECT_DIR/nodeice_board/matrix/main.py" ]; then
  echo -e "${RED}Error: run this script from the nodeice-board repository root.${NC}"
  exit 1
fi

# --- Onboard audio conflicts with the matrix hardware -----------------------
# The RGB matrix library and the Pi's onboard sound (snd_bcm2835) fight over
# the same hardware timing peripheral; the display will glitch badly unless
# sound is disabled.
if lsmod | grep -q snd_bcm2835; then
  echo -e "${YELLOW}Onboard audio (snd_bcm2835) is loaded. It conflicts with the matrix.${NC}"
  read -p "Blacklist onboard audio now? (recommended; requires reboot) (y/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    cat > /etc/modprobe.d/blacklist-rgb-matrix.conf << 'EOF'
blacklist snd_bcm2835
EOF
    if [ -f /boot/firmware/config.txt ]; then
      BOOT_CONFIG=/boot/firmware/config.txt
    else
      BOOT_CONFIG=/boot/config.txt
    fi
    sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$BOOT_CONFIG" || true
    echo -e "${YELLOW}Onboard audio disabled. Reboot before starting the display.${NC}"
  fi
fi

# --- The rgbmatrix Python bindings ------------------------------------------
# These must be compiled from source (they are not on PyPI). As of Feb 2026
# upstream builds this with scikit-build-core/cmake via pip rather than the
# old `make build-python` / `make install-python` targets.
if python3 -c "import rgbmatrix" 2>/dev/null; then
  echo -e "rgbmatrix Python bindings - ${GREEN}already installed${NC}"
else
  echo -e "${YELLOW}Building the rpi-rgb-led-matrix Python bindings...${NC}"
  apt-get update
  apt-get install -y git curl cmake gcc g++ python3-dev python3-pillow cython3

  BUILD_DIR=$(mktemp -d)
  git clone --depth 1 https://github.com/hzeller/rpi-rgb-led-matrix.git "$BUILD_DIR/rpi-rgb-led-matrix"

  # The bindings compile a Pillow shim that includes Pillow's private C
  # header (Imaging.h). It only ships in Pillow's source tarball -- not in
  # wheels or apt packages -- so fetch the headers that match the installed
  # Pillow and put them on the compiler's include path.
  PILLOW_VERSION=$(python3 -c "import PIL; print(PIL.__version__)" 2>/dev/null || echo "12.3.0")
  PILLOW_HEADERS="$BUILD_DIR/pillow-headers"
  mkdir -p "$PILLOW_HEADERS"
  # Releases before 10.3 spell the sdist "Pillow-x.y.z", newer ones "pillow-x.y.z".
  for name in "pillow-$PILLOW_VERSION" "Pillow-$PILLOW_VERSION"; do
    if curl -fsL -o "$PILLOW_HEADERS/src.tar.gz" "https://pypi.org/packages/source/p/pillow/$name.tar.gz"; then
      tar -xzf "$PILLOW_HEADERS/src.tar.gz" -C "$PILLOW_HEADERS" --strip-components=3 \
          --wildcards "*illow-$PILLOW_VERSION/src/libImaging/*.h"
      rm -f "$PILLOW_HEADERS/src.tar.gz"
      break
    fi
  done

  C_INCLUDE_PATH="$PILLOW_HEADERS" python3 -m pip install --break-system-packages "$BUILD_DIR/rpi-rgb-led-matrix"
  rm -rf "$BUILD_DIR"

  python3 -c "import rgbmatrix" || {
    echo -e "${RED}Error: rgbmatrix build failed. See https://github.com/hzeller/rpi-rgb-led-matrix${NC}"
    exit 1
  }
  echo -e "rgbmatrix Python bindings - ${GREEN}installed${NC}"
fi

# --- Python dependency for the display (PyYAML only) ------------------------
# The display runs on the system python3 because rgbmatrix is installed
# system-wide; it only needs PyYAML beyond the standard library.
apt-get install -y python3-yaml

# --- systemd service ---------------------------------------------------------
echo -e "${YELLOW}Creating systemd service file...${NC}"
cat > /etc/systemd/system/nodeice-matrix.service << EOF
[Unit]
Description=Nodeice Board RGB LED Matrix Display
Documentation=https://github.com/AndreasThinks/nodeice-board
After=nodeice-board.service
Wants=nodeice-board.service

[Service]
Type=simple
# Root is required for GPIO access; the matrix library drops privileges
# itself once the hardware is initialized.
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PYTHONPATH=$PROJECT_DIR"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -m nodeice_board.matrix.main --db_path $PROJECT_DIR/nodeice_board.db --config_path $PROJECT_DIR/config.yaml
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nodeice-matrix.service
echo -e "${GREEN}Service installed and enabled at boot.${NC}"

echo
read -p "Start the matrix display now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  systemctl start nodeice-matrix.service
  sleep 2
  if systemctl is-active --quiet nodeice-matrix.service; then
    echo -e "${GREEN}Matrix display started!${NC}"
  else
    echo -e "${RED}Failed to start. Check: sudo journalctl -u nodeice-matrix.service${NC}"
  fi
fi

echo
echo -e "${GREEN}===== Matrix Display Installation Complete =====${NC}"
echo
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  ${GREEN}sudo systemctl status nodeice-matrix.service${NC}"
echo -e "  ${GREEN}sudo systemctl restart nodeice-matrix.service${NC}"
echo -e "  ${GREEN}sudo journalctl -u nodeice-matrix.service -f${NC}"
echo
echo -e "Display settings (brightness, panel size) live in config.yaml"
echo -e "under the ${YELLOW}Matrix_display${NC} section."
