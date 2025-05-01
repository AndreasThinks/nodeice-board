# Nodeice Board

A Meshtastic-based notice board application for creating a public message board on your Meshtastic mesh network.

## Overview

Nodeice Board turns a Meshtastic device connected to a Raspberry Pi (or any computer) into a central notice board for your mesh network. Users can send messages to add posts to the board, view recent posts, and leave comments on existing posts.

Features:
- Post creation and listing
- Commenting on posts
- Automatic post expiration (deletion after 7 days)
- Simple command-based interaction

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
| `!help` | Show available commands | `!help` |
| `!post <message>` | Create a new post | `!post Lost cat in sector 7` |
| `!list [n]` | Show n recent posts (default: 5) | `!list` or `!list 10` |
| `!view <post_id>` | View a specific post and its comments | `!view 42` |
| `!comment <post_id> <message>` | Add a comment to a post | `!comment 42 I saw that cat yesterday` |

### Setup as a Service on Raspberry Pi

To run Nodeice Board as a service on your Raspberry Pi:

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

## Architecture

The application consists of several components:

- **Database**: SQLite database for storing posts and comments
- **Meshtastic Interface**: Handles communication with the Meshtastic device
- **Command Handler**: Processes incoming messages and executes commands
- **Post Expiration Handler**: Automatically removes posts older than 7 days

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
├── pyproject.toml
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
