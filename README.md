# Nodeice Board

A Meshtastic-based notice board application for creating a public message board on your Meshtastic mesh network.

## Overview

Nodeice Board turns a Meshtastic device connected to a Raspberry Pi (or any computer) into a central notice board for your mesh network. Users can send messages to add posts to the board, view recent posts, and leave comments on existing posts.

Features:
- Post creation and listing
- Commenting on posts
- Subscription system for notifications about new posts and comments
- Configurable automatic post expiration (default: 7 days)
- Simple command-based interaction
- Automatic prevention of multiple instances running simultaneously

## Requirements

- Python 3.9 or higher
- A Meshtastic device connected to your computer (via USB)
- Meshtastic network with other nodes

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/nodeice-board.git
   cd nodeice-board
   ```

2. Install the package and dependencies:
   ```bash
   pip install -e .
   ```

## Usage

### Starting the Nodeice Board Server

Run the application with:

```bash
python main.py
```

Options:
- `--device_path`: Specify the path to your Meshtastic device (optional, auto-detects if not provided)
- `--db_path`: Specify the path to the SQLite database file (default: nodeice_board.db)

Example:
```bash
python main.py --device_path /dev/ttyUSB0 --db_path /path/to/database.db
```

### Using the Nodeice Board from Meshtastic Nodes

Once the Nodeice Board server is running, other Meshtastic nodes can interact with it using the following commands:

| Command | Description | Example |
|---------|-------------|---------|
| `!help` | Show available commands and board information | `!help` |
| `!post <message>` | Create a new post | `!post Lost cat in sector 7` |
| `!list [n]` | Show n recent posts (default: 5) | `!list` or `!list 10` |
| `!view <post_id>` | View a specific post and its comments | `!view 42` |
| `!comment <post_id> <message>` | Add a comment to a post | `!comment 42 I saw that cat yesterday` |
| `!subscribe all` | Subscribe to notifications for all new posts | `!subscribe all` |
| `!subscribe <post_id>` | Subscribe to notifications for a specific post | `!subscribe 42` |
| `!unsubscribe all` | Unsubscribe from all notifications | `!unsubscribe all` |
| `!unsubscribe <post_id>` | Unsubscribe from notifications for a specific post | `!unsubscribe 42` |
| `!subscriptions` | List your current subscriptions | `!subscriptions` |

### Setup as a Service on Raspberry Pi

For detailed instructions on setting up Nodeice Board to run automatically at boot on a Raspberry Pi, see the [Raspberry Pi Setup Guide](raspberry_pi_setup.md).

#### Quick Setup

Use the provided installation script:

```bash
chmod +x install_service.sh
sudo ./install_service.sh  # sudo is REQUIRED
```

**Why sudo is required:** This script needs root privileges to:
- Install system packages with apt-get
- Create a systemd service file in /etc/systemd/system/
- Create a log directory in /var/log/
- Reload systemd daemon
- Enable and start the systemd service

This script will:
- Check prerequisites
- Install dependencies
- Create a systemd service
- Enable the service to start at boot

#### Meshtastic Device Setup

If you're having issues with your Meshtastic device, use the device setup script:

```bash
chmod +x setup_meshtastic_device.sh
sudo ./setup_meshtastic_device.sh  # sudo recommended for full functionality
```

**Sudo requirements:**
- Full functionality requires sudo
- Some options (device detection, connection testing) will work without sudo
- Critical functions (udev rules, adding user to dialout group) require sudo

This script helps with:
- Detecting Meshtastic devices
- Setting up udev rules (requires sudo)
- Adding your user to the dialout group (requires sudo)
- Testing device connection

#### Instance Management

The Nodeice Board application includes a mechanism to prevent multiple instances from running simultaneously, which helps avoid conflicts and resource issues:

```bash
# This happens automatically when you run the application
python main.py  # Will automatically check for and terminate any previous instances
```

When deploying on a Raspberry Pi or other Linux system, make sure the script is executable:

```bash
chmod +x kill_previous_instances.sh
```

This feature:
- Detects any running instances of Nodeice Board
- Safely terminates them before starting a new instance
- Logs termination events for monitoring
- Works with both manual execution and systemd service
- Prevents potential database conflicts and resource contention

#### Monitoring and Status Check

To check the status of your Nodeice Board service and get basic monitoring information:

```bash
chmod +x check_nodeice_status.sh
sudo ./check_nodeice_status.sh  # sudo recommended for full access
```

**Sudo requirements:**
- Works best with sudo for full access to service status and logs
- Can run without sudo but with limited functionality
- Some systemctl commands require sudo privileges

This script provides information about:
- Service status and uptime
- Instance management status
- Meshtastic device detection
- Log file status and recent entries
- Database statistics
- System information (memory, disk usage, CPU temperature)

#### Manual Setup

For manual setup instructions, see the [Raspberry Pi Setup Guide](raspberry_pi_setup.md) or follow these basic steps:

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/nodeice-board.service
   ```

2. Add the following content (adjust paths as needed):
   ```
   [Unit]
   Description=Nodeice Board Meshtastic Notice Board
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /home/pi/nodeice-board/main.py
   WorkingDirectory=/home/pi/nodeice-board
   StandardOutput=inherit
   StandardError=inherit
   Restart=always
   User=pi

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl enable nodeice-board
   sudo systemctl start nodeice-board
   ```

4. Check the status:
   ```bash
   sudo systemctl status nodeice-board
   ```

## Configuration

The application can be configured using the `config.yaml` file:

```yaml
Nodeice_board:
  Long_Name: "Nodeice Board📌Msg me !help"  # Long name for the Meshtastic device
  Short_Name: "NDB"                         # Short name for the Meshtastic device
  Info_URL: "https://github.com/AndreasThinks/nodeice-board"  # URL for more information
  Expiration_Days: 7                        # Number of days after which posts are deleted
```

## Architecture

The application consists of several components:

- **Database**: SQLite database for storing posts, comments, and subscriptions
- **Meshtastic Interface**: Handles communication with the Meshtastic device
- **Command Handler**: Processes incoming messages and executes commands
- **Post Expiration Handler**: Automatically removes posts older than 7 days
- **Config**: Handles loading and accessing configuration settings
- **Instance Management**: Prevents conflicts by ensuring only one instance runs at a time

## Development

### Project Structure

```
nodeice-board/
├── nodeice_board/
│   ├── __init__.py
│   ├── database.py
│   ├── meshtastic_interface.py
│   ├── command_handler.py
│   └── post_expiration.py
├── main.py
├── install_service.sh
├── setup_meshtastic_device.sh
├── check_nodeice_status.sh
├── kill_previous_instances.sh
├── pyproject.toml
├── config.yaml
└── README.md
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
