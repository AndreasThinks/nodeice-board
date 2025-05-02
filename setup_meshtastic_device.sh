#!/bin/bash

# Meshtastic Device Setup Script for Raspberry Pi
# This script helps detect and configure Meshtastic devices for use with Nodeice Board

set -e  # Exit on error

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== Meshtastic Device Setup for Raspberry Pi =====${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${YELLOW}Note: Some operations may require root privileges.${NC}"
  echo -e "Consider running with sudo if you encounter permission issues."
  echo
fi

# Get the current user
CURRENT_USER=$(whoami)

# Function to detect Meshtastic devices
detect_devices() {
  echo -e "${YELLOW}Detecting USB devices that might be Meshtastic devices...${NC}"
  
  # Check for USB devices
  echo -e "\n${BLUE}USB devices:${NC}"
  lsusb
  
  # Check for ttyUSB devices
  echo -e "\n${BLUE}ttyUSB devices:${NC}"
  if ls /dev/ttyUSB* &> /dev/null; then
    ls -l /dev/ttyUSB*
    USB_DEVICES=1
  else
    echo "No ttyUSB devices found."
    USB_DEVICES=0
  fi
  
  # Check for ttyACM devices
  echo -e "\n${BLUE}ttyACM devices:${NC}"
  if ls /dev/ttyACM* &> /dev/null; then
    ls -l /dev/ttyACM*
    ACM_DEVICES=1
  else
    echo "No ttyACM devices found."
    ACM_DEVICES=0
  fi
  
  # Return if any devices were found
  if [ $USB_DEVICES -eq 1 ] || [ $ACM_DEVICES -eq 1 ]; then
    return 0
  else
    return 1
  fi
}

# Function to set up udev rules
setup_udev_rules() {
  echo -e "\n${YELLOW}Setting up udev rules for Meshtastic devices...${NC}"
  
  if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Setting up udev rules requires root privileges.${NC}"
    echo -e "Please run this script with sudo to set up udev rules."
    return 1
  fi
  
  # Create a udev rules file for common Meshtastic devices
  echo -e "Creating udev rules file..."
  cat > /etc/udev/rules.d/99-meshtastic.rules << EOF
# T-Beam, T-Watch, and other ESP32 based devices (CP210x USB to UART bridge)
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", SYMLINK+="meshtastic"

# Heltec and LILYGO devices with CH9102 USB to UART bridge
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", MODE="0666", SYMLINK+="meshtastic"

# Devices with CH340 USB to UART bridge
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", SYMLINK+="meshtastic"

# RAK devices with CP210x USB to UART bridge
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", SYMLINK+="meshtastic"

# Generic rule for ACM devices (some ESP32 boards)
SUBSYSTEM=="tty", KERNEL=="ttyACM*", MODE="0666", SYMLINK+="meshtastic%n"
EOF
  
  # Reload udev rules
  echo -e "Reloading udev rules..."
  udevadm control --reload-rules
  udevadm trigger
  
  echo -e "${GREEN}Udev rules set up successfully.${NC}"
  echo -e "Your Meshtastic device should now be accessible at /dev/meshtastic"
  echo -e "You may need to reconnect your device for the rules to take effect."
  
  return 0
}

# Function to add user to dialout group
add_to_dialout() {
  echo -e "\n${YELLOW}Adding user to dialout group...${NC}"
  
  if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Adding user to dialout group requires root privileges.${NC}"
    echo -e "Please run this script with sudo to add user to dialout group."
    return 1
  fi
  
  # Add user to dialout group
  usermod -a -G dialout $CURRENT_USER
  
  echo -e "${GREEN}User $CURRENT_USER added to dialout group.${NC}"
  echo -e "You will need to log out and log back in for this change to take effect."
  
  return 0
}

# Function to test device connection
test_device() {
  echo -e "\n${YELLOW}Testing device connection...${NC}"
  
  # Check if python3 and pip are installed
  if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed.${NC}"
    echo -e "Please install python3 and try again."
    return 1
  fi
  
  if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}Error: pip3 is not installed.${NC}"
    echo -e "Please install pip3 and try again."
    return 1
  fi
  
  # Check if meshtastic-python is installed
  if ! pip3 list | grep -q meshtastic; then
    echo -e "${YELLOW}Meshtastic Python library not found. Installing...${NC}"
    pip3 install meshtastic
  fi
  
  # Try to connect to the device
  echo -e "Attempting to connect to Meshtastic device..."
  if python3 -c "import meshtastic; meshtastic.serial_interface.SerialInterface()"; then
    echo -e "${GREEN}Successfully connected to Meshtastic device!${NC}"
    return 0
  else
    echo -e "${RED}Failed to connect to Meshtastic device.${NC}"
    return 1
  fi
}

# Main menu
while true; do
  echo
  echo -e "${BLUE}===== Meshtastic Device Setup Menu =====${NC}"
  echo -e "1. Detect Meshtastic devices"
  echo -e "2. Set up udev rules (requires sudo)"
  echo -e "3. Add user to dialout group (requires sudo)"
  echo -e "4. Test device connection"
  echo -e "5. Exit"
  echo
  read -p "Enter your choice (1-5): " choice
  
  case $choice in
    1)
      detect_devices
      ;;
    2)
      setup_udev_rules
      ;;
    3)
      add_to_dialout
      ;;
    4)
      test_device
      ;;
    5)
      echo -e "${GREEN}Exiting...${NC}"
      exit 0
      ;;
    *)
      echo -e "${RED}Invalid choice. Please enter a number between 1 and 5.${NC}"
      ;;
  esac
done
