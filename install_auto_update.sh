#!/bin/bash

# Nodeice Board Auto-Update Installation Script
# This script sets up the auto-update mechanism for Nodeice Board

set -e  # Exit on error

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}===== Nodeice Board Auto-Update Setup =====${NC}"

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

# Check if auto_update.sh exists
if [ ! -f "${PROJECT_DIR}/auto_update.sh" ]; then
  echo -e "${RED}Error: auto_update.sh not found in the current directory.${NC}"
  exit 1
fi

# Make the auto_update.sh script executable
echo -e "${YELLOW}Making auto_update.sh executable...${NC}"
chmod +x "${PROJECT_DIR}/auto_update.sh"
echo -e "${GREEN}Done.${NC}"

# Create log directory if it doesn't exist
LOG_DIR="/var/log/nodeice-board"
echo -e "${YELLOW}Ensuring log directory exists at $LOG_DIR...${NC}"
mkdir -p $LOG_DIR
chown $CURRENT_USER:$CURRENT_USER $LOG_DIR
echo -e "${GREEN}Done.${NC}"

# Set up the cron job
echo -e "${YELLOW}Setting up cron job for daily updates...${NC}"
CRON_JOB="0 3 * * * ${PROJECT_DIR}/auto_update.sh >> ${LOG_DIR}/auto_update.log 2>&1"

# Check if the cron job already exists
if crontab -l 2>/dev/null | grep -q "${PROJECT_DIR}/auto_update.sh"; then
  echo -e "${YELLOW}Auto-update cron job already exists. Skipping...${NC}"
else
  # Add the cron job
  (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
  echo -e "${GREEN}Cron job added. Auto-update will run daily at 3 AM.${NC}"
fi

# Run the auto-update script once to verify it works
echo
read -p "Do you want to run the auto-update check now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${YELLOW}Running auto-update check...${NC}"
  "${PROJECT_DIR}/auto_update.sh"
  echo -e "${GREEN}Auto-update check completed.${NC}"
fi

echo
echo -e "${GREEN}${BOLD}===== Auto-Update Setup Complete! =====${NC}"
echo
echo -e "The Nodeice Board auto-update mechanism is now installed."
echo -e "The system will check for updates daily at 3 AM and automatically apply them if available."
echo
echo -e "${YELLOW}Auto-update log file:${NC} ${LOG_DIR}/auto_update.log"
echo
echo -e "${YELLOW}To manually trigger an update check, run:${NC}"
echo -e "  ${GREEN}sudo ${PROJECT_DIR}/auto_update.sh${NC}"
echo
echo -e "${YELLOW}To view the auto-update logs, run:${NC}"
echo -e "  ${GREEN}cat ${LOG_DIR}/auto_update.log${NC}"
echo
echo -e "For more information, see the updated documentation."
echo
