#!/bin/bash

# Nodeice Board Status Check Script
# This script checks the status of the Nodeice Board service and provides basic monitoring information

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}===== Nodeice Board Status Check =====${NC}"
echo

# Check if the service is installed
if [ ! -f "/etc/systemd/system/nodeice-board.service" ]; then
    echo -e "${RED}Nodeice Board service is not installed.${NC}"
    echo -e "Run ${YELLOW}sudo ./install_service.sh${NC} to install the service."
    exit 1
fi

# Check if the service is enabled
echo -e "${BOLD}Service Status:${NC}"
if systemctl is-enabled --quiet nodeice-board.service; then
    echo -e "Service enabled at boot: ${GREEN}Yes${NC}"
else
    echo -e "Service enabled at boot: ${RED}No${NC}"
    echo -e "Run ${YELLOW}sudo systemctl enable nodeice-board.service${NC} to enable at boot."
fi

# Check if the service is active
if systemctl is-active --quiet nodeice-board.service; then
    echo -e "Service running: ${GREEN}Yes${NC}"
    
    # Get the service uptime
    start_time=$(systemctl show -p ActiveEnterTimestamp nodeice-board.service | cut -d= -f2)
    echo -e "Running since: ${GREEN}$start_time${NC}"
    
    # Get the service PID
    pid=$(systemctl show -p MainPID nodeice-board.service | cut -d= -f2)
    if [ "$pid" != "0" ]; then
        echo -e "Process ID: ${GREEN}$pid${NC}"
        
        # Get memory usage
        if command -v ps &> /dev/null; then
            mem_usage=$(ps -o rss= -p $pid 2>/dev/null)
            if [ -n "$mem_usage" ]; then
                mem_mb=$(echo "scale=2; $mem_usage/1024" | bc)
                echo -e "Memory usage: ${GREEN}${mem_mb} MB${NC}"
            fi
        fi
    fi
else
    echo -e "Service running: ${RED}No${NC}"
    echo -e "Run ${YELLOW}sudo systemctl start nodeice-board.service${NC} to start the service."
fi

echo

# Check for Meshtastic device
echo -e "${BOLD}Meshtastic Device:${NC}"
if ls /dev/ttyUSB* &> /dev/null || ls /dev/ttyACM* &> /dev/null; then
    echo -e "USB devices detected: ${GREEN}Yes${NC}"
    
    # Check if the symlink exists
    if [ -L "/dev/meshtastic" ]; then
        echo -e "Meshtastic symlink: ${GREEN}/dev/meshtastic${NC}"
    else
        echo -e "Meshtastic symlink: ${RED}Not found${NC}"
        echo -e "Run ${YELLOW}sudo ./setup_meshtastic_device.sh${NC} to set up udev rules."
    fi
    
    # List USB devices
    echo -e "\nUSB devices:"
    if ls /dev/ttyUSB* &> /dev/null; then
        ls -l /dev/ttyUSB*
    fi
    if ls /dev/ttyACM* &> /dev/null; then
        ls -l /dev/ttyACM*
    fi
else
    echo -e "USB devices detected: ${RED}No${NC}"
    echo -e "Make sure your Meshtastic device is connected."
fi

echo

# Check log file
echo -e "${BOLD}Log File:${NC}"
log_file="nodeice_board.log"
if [ -f "$log_file" ]; then
    echo -e "Log file: ${GREEN}$log_file${NC}"
    
    # Get log file size
    log_size=$(du -h "$log_file" | cut -f1)
    echo -e "Log size: ${GREEN}$log_size${NC}"
    
    # Get last modified time
    log_modified=$(stat -c %y "$log_file" 2>/dev/null || stat -f "%Sm" "$log_file" 2>/dev/null)
    echo -e "Last modified: ${GREEN}$log_modified${NC}"
    
    # Show last few log entries
    echo -e "\n${BOLD}Last 5 log entries:${NC}"
    tail -n 5 "$log_file"
else
    echo -e "Log file: ${RED}Not found${NC}"
    echo -e "The log file will be created when the service runs."
fi

echo

# Check database file
echo -e "${BOLD}Database:${NC}"
db_file="nodeice_board.db"
if [ -f "$db_file" ]; then
    echo -e "Database file: ${GREEN}$db_file${NC}"
    
    # Get database file size
    db_size=$(du -h "$db_file" | cut -f1)
    echo -e "Database size: ${GREEN}$db_size${NC}"
    
    # Get last modified time
    db_modified=$(stat -c %y "$db_file" 2>/dev/null || stat -f "%Sm" "$db_file" 2>/dev/null)
    echo -e "Last modified: ${GREEN}$db_modified${NC}"
    
    # Check if sqlite3 is installed
    if command -v sqlite3 &> /dev/null; then
        # Get post count
        post_count=$(sqlite3 "$db_file" "SELECT COUNT(*) FROM posts;" 2>/dev/null)
        if [ -n "$post_count" ]; then
            echo -e "Number of posts: ${GREEN}$post_count${NC}"
        fi
        
        # Get comment count
        comment_count=$(sqlite3 "$db_file" "SELECT COUNT(*) FROM comments;" 2>/dev/null)
        if [ -n "$comment_count" ]; then
            echo -e "Number of comments: ${GREEN}$comment_count${NC}"
        fi
        
        # Get subscription count
        sub_count=$(sqlite3 "$db_file" "SELECT COUNT(*) FROM subscriptions;" 2>/dev/null)
        if [ -n "$sub_count" ]; then
            echo -e "Number of subscriptions: ${GREEN}$sub_count${NC}"
        fi
    else
        echo -e "${YELLOW}Install sqlite3 to see database statistics.${NC}"
    fi
else
    echo -e "Database file: ${RED}Not found${NC}"
    echo -e "The database file will be created when the service runs."
fi

echo

# Show system information
echo -e "${BOLD}System Information:${NC}"
# Get hostname
hostname=$(hostname)
echo -e "Hostname: ${GREEN}$hostname${NC}"

# Get system uptime
uptime=$(uptime -p)
echo -e "System uptime: ${GREEN}$uptime${NC}"

# Get memory usage
free_output=$(free -h)
mem_usage=$(echo "$free_output" | grep "Mem:" | awk '{print $3 " / " $2}')
echo -e "Memory usage: ${GREEN}$mem_usage${NC}"

# Get disk usage
disk_usage=$(df -h . | tail -n 1 | awk '{print $3 " / " $2 " (" $5 ")"}')
echo -e "Disk usage: ${GREEN}$disk_usage${NC}"

# Get CPU temperature (Raspberry Pi specific)
if [ -f "/sys/class/thermal/thermal_zone0/temp" ]; then
    cpu_temp=$(cat /sys/class/thermal/thermal_zone0/temp)
    cpu_temp=$(echo "scale=1; $cpu_temp/1000" | bc)
    echo -e "CPU temperature: ${GREEN}${cpu_temp}°C${NC}"
fi

echo
echo -e "${BLUE}${BOLD}===== Status Check Complete =====${NC}"
echo
echo -e "${BOLD}Useful Commands:${NC}"
echo -e "  ${YELLOW}sudo systemctl start nodeice-board.service${NC}   - Start the service"
echo -e "  ${YELLOW}sudo systemctl stop nodeice-board.service${NC}    - Stop the service"
echo -e "  ${YELLOW}sudo systemctl restart nodeice-board.service${NC} - Restart the service"
echo -e "  ${YELLOW}sudo journalctl -u nodeice-board.service -n 50${NC} - View last 50 log entries"
echo -e "  ${YELLOW}sudo journalctl -u nodeice-board.service -f${NC}  - Follow logs in real-time"
echo
