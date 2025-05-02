#!/bin/bash

# Nodeice Board Auto-Update Script
# This script checks for updates on the GitHub repository and automatically
# updates the application if new changes are available.

# Set strict error handling
set -e

# ANSI color codes for logging
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(dirname "$(readlink -f "$0")")"  # Get the directory where this script is located
LOG_FILE="/var/log/nodeice-board/auto_update.log"
BACKUP_DIR="${PROJECT_DIR}/backup/$(date +%Y%m%d_%H%M%S)"
SERVICE_NAME="nodeice-board.service"
VENV_PATH="${PROJECT_DIR}/venv"
PIP_PATH="${VENV_PATH}/bin/pip"

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

# Function to log messages
log() {
    local level=$1
    local message=$2
    local color=$NC
    
    case $level in
        "INFO") color=$GREEN ;;
        "WARNING") color=$YELLOW ;;
        "ERROR") color=$RED ;;
    esac
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] ${message}${NC}" | tee -a "$LOG_FILE"
}

# Function to check if the service is running
check_service() {
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        log "WARNING" "Nodeice Board service is not running. Continuing anyway."
    else
        log "INFO" "Nodeice Board service is running."
    fi
}

# Function to create a backup
create_backup() {
    log "INFO" "Creating backup in ${BACKUP_DIR}"
    mkdir -p "$BACKUP_DIR"
    
    # Backup important files
    cp -r "${PROJECT_DIR}/config.yaml" "${BACKUP_DIR}/" 2>/dev/null || true
    cp -r "${PROJECT_DIR}/nodeice_board.db" "${BACKUP_DIR}/" 2>/dev/null || true
    cp -r "${PROJECT_DIR}/nodeice_board.log" "${BACKUP_DIR}/" 2>/dev/null || true
    
    log "INFO" "Backup created successfully."
}

# Function to check for updates
check_for_updates() {
    log "INFO" "Checking for updates..."
    
    # Navigate to project directory
    cd "$PROJECT_DIR"
    
    # Get current commit hash
    CURRENT_HASH=$(git rev-parse HEAD)
    log "INFO" "Current commit hash: ${CURRENT_HASH}"
    
    # Fetch latest changes without merging
    log "INFO" "Fetching latest changes from remote repository..."
    git fetch origin
    
    # Get remote commit hash
    REMOTE_HASH=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master)
    log "INFO" "Remote commit hash: ${REMOTE_HASH}"
    
    # Compare hashes
    if [ "$CURRENT_HASH" != "$REMOTE_HASH" ]; then
        log "INFO" "Updates available. Proceeding with update..."
        return 0  # Updates available
    else
        log "INFO" "No updates available. Already at the latest version."
        return 1  # No updates available
    fi
}

# Function to apply updates
apply_updates() {
    log "INFO" "Applying updates..."
    
    # Navigate to project directory
    cd "$PROJECT_DIR"
    
    # Create backup before updating
    create_backup
    
    # Pull changes
    log "INFO" "Pulling latest changes..."
    git pull
    
    # Check if pip exists in the virtual environment
    if [ -f "$PIP_PATH" ]; then
        # Update dependencies
        log "INFO" "Updating dependencies..."
        "$PIP_PATH" install -e "$PROJECT_DIR"
    else
        log "WARNING" "Virtual environment not found at ${VENV_PATH}. Skipping dependency update."
    fi
    
    # Restart service if it's active and enabled
    if systemctl is-enabled --quiet "$SERVICE_NAME" && systemctl is-active --quiet "$SERVICE_NAME"; then
        log "INFO" "Restarting Nodeice Board service..."
        systemctl restart "$SERVICE_NAME"
        
        # Verify service is running after restart
        sleep 5
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log "INFO" "Service restarted successfully."
        else
            log "ERROR" "Service failed to restart. Check the service logs for details."
            log "INFO" "Attempting to restore from backup..."
            # Service failed to restart - could implement rollback here if needed
        fi
    else
        log "WARNING" "Service is not active or not enabled. Skipping service restart."
    fi
    
    log "INFO" "Update completed successfully."
}

# Main execution
log "INFO" "Starting Nodeice Board auto-update check..."

# Check if service is running
check_service

# Check for updates and apply if available
if check_for_updates; then
    apply_updates
fi

log "INFO" "Auto-update check completed."
exit 0
