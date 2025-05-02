#!/bin/bash

# kill_previous_instances.sh
# This script identifies and terminates any running instances of the Nodeice Board application
# before starting a new instance to avoid conflicts.

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Checking for previous Nodeice Board instances...${NC}"

# Get the PID of the current script
CURRENT_PID=$$

# Get the parent PID (the process that called this script)
PARENT_PID=$PPID

# Find all Python processes running main.py for Nodeice Board
# Exclude the current process and its parent
PIDS=$(pgrep -f "python.*main\.py" | grep -v -e "^$CURRENT_PID$" -e "^$PARENT_PID$")

if [ -z "$PIDS" ]; then
    echo -e "${GREEN}No previous instances found.${NC}"
else
    # Count the number of instances found
    NUM_INSTANCES=$(echo "$PIDS" | wc -l)
    echo -e "${YELLOW}Found $NUM_INSTANCES previous instance(s) running. Terminating...${NC}"
    
    # Log the PIDs being terminated
    echo "Terminating PIDs: $PIDS" >> nodeice_board_kill.log
    
    # Terminate each process gracefully first (SIGTERM)
    for PID in $PIDS; do
        echo -e "Sending SIGTERM to PID ${YELLOW}$PID${NC}"
        kill $PID 2>/dev/null
    done
    
    # Wait a moment for processes to terminate gracefully
    sleep 2
    
    # Check if any processes are still running and force kill if necessary
    REMAINING_PIDS=$(pgrep -f "python.*main\.py" | grep -v -e "^$CURRENT_PID$" -e "^$PARENT_PID$")
    if [ -n "$REMAINING_PIDS" ]; then
        echo -e "${YELLOW}Some processes did not terminate gracefully. Forcing termination...${NC}"
        for PID in $REMAINING_PIDS; do
            echo -e "Sending SIGKILL to PID ${YELLOW}$PID${NC}"
            kill -9 $PID 2>/dev/null
        done
    fi
    
    echo -e "${GREEN}All previous instances terminated.${NC}"
    
    # Log the termination time
    echo "$(date): Terminated $NUM_INSTANCES instance(s) before starting new instance" >> nodeice_board_kill.log
fi

# Also check for any zombie Meshtastic interface processes that might be orphaned
MESH_PIDS=$(pgrep -f "meshtastic" | grep -v -e "^$CURRENT_PID$" -e "^$PARENT_PID$")
if [ -n "$MESH_PIDS" ]; then
    echo -e "${YELLOW}Found orphaned Meshtastic processes. Terminating...${NC}"
    
    # Log the PIDs being terminated
    echo "Terminating Meshtastic PIDs: $MESH_PIDS" >> nodeice_board_kill.log
    
    # Terminate each process
    for PID in $MESH_PIDS; do
        echo -e "Sending SIGTERM to Meshtastic PID ${YELLOW}$PID${NC}"
        kill $PID 2>/dev/null
    done
    
    # Force kill any remaining after a short wait
    sleep 1
    REMAINING_MESH_PIDS=$(pgrep -f "meshtastic" | grep -v -e "^$CURRENT_PID$" -e "^$PARENT_PID$")
    if [ -n "$REMAINING_MESH_PIDS" ]; then
        for PID in $REMAINING_MESH_PIDS; do
            echo -e "Sending SIGKILL to Meshtastic PID ${YELLOW}$PID${NC}"
            kill -9 $PID 2>/dev/null
        done
    fi
    
    echo -e "${GREEN}All orphaned Meshtastic processes terminated.${NC}"
fi

# If running as a systemd service, also check for other nodeice-board service instances
if systemctl list-units --type=service | grep -q "nodeice-board"; then
    # Get the current service instance (if any)
    CURRENT_UNIT=$(systemctl status | grep -o "nodeice-board.*\.service" | head -n 1)
    
    # Find all nodeice-board service instances
    SERVICE_UNITS=$(systemctl list-units --type=service | grep "nodeice-board" | awk '{print $1}')
    
    for UNIT in $SERVICE_UNITS; do
        # Skip the current unit
        if [ "$UNIT" != "$CURRENT_UNIT" ]; then
            echo -e "${YELLOW}Found other nodeice-board service: $UNIT. Stopping...${NC}"
            systemctl stop "$UNIT" 2>/dev/null
            echo "$(date): Stopped service unit $UNIT before starting new instance" >> nodeice_board_kill.log
        fi
    done
fi

echo -e "${GREEN}System ready for new Nodeice Board instance.${NC}"
exit 0
