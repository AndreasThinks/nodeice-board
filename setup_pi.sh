#!/bin/bash
#
# Nodeice Board - one-command Raspberry Pi installer
#
# Installs everything needed to run Nodeice Board on a Raspberry Pi:
#   - uv (https://docs.astral.sh/uv/) if not already installed
#   - the repository itself (cloned to ~/nodeice-board if run outside a checkout)
#   - the notice board as a systemd service (nodeice-board.service)
#   - the optional RGB LED matrix display as a systemd service
#     (nodeice-matrix.service), including the rpi-rgb-led-matrix bindings
#
# Designed to be run remotely in one command:
#
#   curl -fsSL https://raw.githubusercontent.com/AndreasThinks/nodeice-board/main/setup_pi.sh | sudo bash
#
# Pass flags after `-s --`, e.g.:
#
#   curl -fsSL .../setup_pi.sh | sudo bash -s -- --no-matrix
#
# The script is non-interactive: it never prompts, so it is safe to pipe.

set -euo pipefail

REPO_URL="https://github.com/AndreasThinks/nodeice-board.git"
MATRIX_LIB_URL="https://github.com/hzeller/rpi-rgb-led-matrix.git"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}$*${NC}"; }
warn()  { echo -e "${YELLOW}$*${NC}"; }
fail()  { echo -e "${RED}$*${NC}" >&2; exit 1; }

usage() {
    cat << 'EOF'
Usage: sudo ./setup_pi.sh [options]
   or: curl -fsSL https://raw.githubusercontent.com/AndreasThinks/nodeice-board/main/setup_pi.sh | sudo bash -s -- [options]

Options:
  --dir DIR       Install location (default: <user home>/nodeice-board, or the
                  current directory when run from inside a checkout)
  --user USER     User to own the install and run the board service
                  (default: the user who invoked sudo)
  --branch NAME   Git branch to install (default: main)
  --no-matrix     Skip the RGB LED matrix display entirely
  --no-start      Install and enable the services but do not start them now
  --keep-audio    Do not disable onboard audio (the matrix display will
                  glitch while snd_bcm2835 is loaded)
  -h, --help      Show this help
EOF
}

main() {
    local BRANCH="main"
    local INSTALL_MATRIX=1
    local START_SERVICES=1
    local DISABLE_AUDIO=1
    local PROJECT_DIR=""
    local TARGET_USER="${SUDO_USER:-}"

    while [ $# -gt 0 ]; do
        case "$1" in
            --dir)        PROJECT_DIR="$2"; shift 2 ;;
            --user)       TARGET_USER="$2"; shift 2 ;;
            --branch)     BRANCH="$2"; shift 2 ;;
            --no-matrix)  INSTALL_MATRIX=0; shift ;;
            --no-start)   START_SERVICES=0; shift ;;
            --keep-audio) DISABLE_AUDIO=0; shift ;;
            -h|--help)    usage; exit 0 ;;
            *) fail "Unknown option: $1 (see --help)" ;;
        esac
    done

    info "===== Nodeice Board One-Command Setup ====="

    if [ "$EUID" -ne 0 ]; then
        fail "Error: this script must be run as root (use sudo)."
    fi

    if [ -z "$TARGET_USER" ]; then
        TARGET_USER="root"
        warn "No sudo user detected; installing as root. Use --user to override."
    fi
    if ! id "$TARGET_USER" >/dev/null 2>&1; then
        fail "Error: user '$TARGET_USER' does not exist."
    fi
    local TARGET_HOME
    TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)

    # The matrix display only makes sense on real Raspberry Pi hardware.
    local ON_PI=0
    if [ -f /proc/device-tree/model ] && grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null; then
        ON_PI=1
    fi
    if [ "$INSTALL_MATRIX" -eq 1 ] && [ "$ON_PI" -eq 0 ]; then
        warn "This does not look like a Raspberry Pi; skipping the matrix display."
        warn "(Use 'uv run nodeice-board-matrix --emulator' for desktop preview.)"
        INSTALL_MATRIX=0
    fi

    # --- System packages ------------------------------------------------------
    info "Installing system packages..."
    export DEBIAN_FRONTEND=noninteractive
    local APT_PACKAGES=(git curl ca-certificates python3-dev)
    if [ "$INSTALL_MATRIX" -eq 1 ]; then
        # Needed to compile the rpi-rgb-led-matrix Python bindings.
        APT_PACKAGES+=(build-essential cmake)
    fi
    apt-get update
    apt-get install -y "${APT_PACKAGES[@]}"

    # --- uv ---------------------------------------------------------------------
    local UV_BIN
    UV_BIN=$(sudo -u "$TARGET_USER" -H sh -c 'command -v uv' 2>/dev/null || true)
    if [ -z "$UV_BIN" ]; then
        for candidate in "$TARGET_HOME/.local/bin/uv" "$TARGET_HOME/.cargo/bin/uv"; do
            if [ -x "$candidate" ]; then
                UV_BIN="$candidate"
                break
            fi
        done
    fi
    if [ -z "$UV_BIN" ]; then
        info "Installing uv for user $TARGET_USER..."
        sudo -u "$TARGET_USER" -H sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
        UV_BIN="$TARGET_HOME/.local/bin/uv"
        [ -x "$UV_BIN" ] || UV_BIN="$TARGET_HOME/.cargo/bin/uv"
        [ -x "$UV_BIN" ] || fail "Error: uv installation failed."
    fi
    info "uv: $UV_BIN ($(sudo -u "$TARGET_USER" -H "$UV_BIN" --version))"

    # --- Get the code -----------------------------------------------------------
    # If run from inside a checkout, install in place; otherwise clone.
    if [ -z "$PROJECT_DIR" ]; then
        if [ -f "$PWD/pyproject.toml" ] && [ -f "$PWD/nodeice_board/matrix/main.py" ]; then
            PROJECT_DIR="$PWD"
        else
            PROJECT_DIR="$TARGET_HOME/nodeice-board"
        fi
    fi

    if [ -f "$PROJECT_DIR/pyproject.toml" ]; then
        info "Using existing checkout at $PROJECT_DIR"
        if [ -d "$PROJECT_DIR/.git" ]; then
            sudo -u "$TARGET_USER" -H git -C "$PROJECT_DIR" pull --ff-only 2>/dev/null \
                || warn "Could not fast-forward $PROJECT_DIR; continuing with the current checkout."
        fi
    else
        info "Cloning nodeice-board (branch: $BRANCH) to $PROJECT_DIR..."
        sudo -u "$TARGET_USER" -H git clone --branch "$BRANCH" "$REPO_URL" "$PROJECT_DIR"
    fi
    chmod +x "$PROJECT_DIR/kill_previous_instances.sh"

    # --- Python environment (uv) -------------------------------------------------
    info "Creating the Python environment with uv..."
    sudo -u "$TARGET_USER" -H env -C "$PROJECT_DIR" "$UV_BIN" sync --frozen --no-dev
    local VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
    [ -x "$VENV_PYTHON" ] || fail "Error: uv sync did not create $VENV_PYTHON."

    # --- Meshtastic device access -------------------------------------------------
    if [ "$TARGET_USER" != "root" ] && getent group dialout >/dev/null; then
        usermod -a -G dialout "$TARGET_USER"
        info "Added $TARGET_USER to the dialout group (takes effect on next login)."
    fi
    if ! ls /dev/ttyUSB* /dev/ttyACM* >/dev/null 2>&1; then
        warn "No USB serial device detected. Plug in your Meshtastic device before"
        warn "starting the service, or it will retry until one appears."
    fi

    # --- RGB LED matrix display ----------------------------------------------------
    local MATRIX_OK=0
    local REBOOT_NEEDED=0
    if [ "$INSTALL_MATRIX" -eq 1 ]; then
        MATRIX_OK=1

        # The matrix library and onboard audio (snd_bcm2835) fight over the same
        # timing peripheral; the display glitches badly unless audio is disabled.
        if lsmod | grep -q snd_bcm2835; then
            if [ "$DISABLE_AUDIO" -eq 1 ]; then
                info "Disabling onboard audio (conflicts with the matrix display)..."
                cat > /etc/modprobe.d/blacklist-rgb-matrix.conf << 'EOF'
blacklist snd_bcm2835
EOF
                local BOOT_CONFIG=/boot/config.txt
                [ -f /boot/firmware/config.txt ] && BOOT_CONFIG=/boot/firmware/config.txt
                sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$BOOT_CONFIG" || true
                REBOOT_NEEDED=1
            else
                warn "--keep-audio set: onboard audio stays enabled; expect display glitches."
            fi
        fi

        if "$VENV_PYTHON" -c "import rgbmatrix" 2>/dev/null; then
            info "rgbmatrix Python bindings - already installed"
        else
            info "Building the rpi-rgb-led-matrix Python bindings (this takes a few minutes)..."
            local BUILD_DIR
            BUILD_DIR=$(mktemp -d)
            chown "$TARGET_USER" "$BUILD_DIR"
            if sudo -u "$TARGET_USER" -H git clone --depth 1 "$MATRIX_LIB_URL" "$BUILD_DIR/rpi-rgb-led-matrix" \
                && sudo -u "$TARGET_USER" -H "$UV_BIN" pip install --python "$VENV_PYTHON" "$BUILD_DIR/rpi-rgb-led-matrix" \
                && "$VENV_PYTHON" -c "import rgbmatrix" 2>/dev/null; then
                info "rgbmatrix Python bindings - installed"
            else
                warn "rgbmatrix build failed; skipping the matrix display service."
                warn "You can retry later with: sudo ./install_matrix_service.sh"
                MATRIX_OK=0
            fi
            rm -rf "$BUILD_DIR"
        fi
    fi

    # --- systemd: notice board -------------------------------------------------------
    info "Creating nodeice-board.service..."
    cat > /etc/systemd/system/nodeice-board.service << EOF
[Unit]
Description=Nodeice Board Meshtastic Notice Board
Documentation=https://github.com/AndreasThinks/nodeice-board
After=network.target
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$TARGET_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_PYTHON $PROJECT_DIR/main.py
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

    # --- systemd: matrix display -------------------------------------------------------
    if [ "$MATRIX_OK" -eq 1 ]; then
        info "Creating nodeice-matrix.service..."
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
Environment="PYTHONUNBUFFERED=1"
ExecStart=$VENV_PYTHON -m nodeice_board.matrix.main --db_path $PROJECT_DIR/nodeice_board.db --config_path $PROJECT_DIR/config.yaml
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    fi

    # --- Logs, enable, start ---------------------------------------------------------
    local LOG_DIR="/var/log/nodeice-board"
    mkdir -p "$LOG_DIR"
    chown "$TARGET_USER" "$LOG_DIR"
    ln -sf "$PROJECT_DIR/nodeice_board.log" "$LOG_DIR/nodeice_board.log"

    systemctl daemon-reload
    systemctl enable nodeice-board.service
    [ "$MATRIX_OK" -eq 1 ] && systemctl enable nodeice-matrix.service

    if [ "$START_SERVICES" -eq 1 ]; then
        info "Starting nodeice-board.service..."
        systemctl restart nodeice-board.service
        if [ "$MATRIX_OK" -eq 1 ]; then
            if lsmod | grep -q snd_bcm2835; then
                warn "Not starting the matrix display: onboard audio is still loaded."
                warn "It will start automatically after you reboot."
            else
                info "Starting nodeice-matrix.service..."
                systemctl restart nodeice-matrix.service
            fi
        fi
        sleep 2
        if systemctl is-active --quiet nodeice-board.service; then
            info "Nodeice Board service is running."
        else
            warn "nodeice-board.service is not active yet."
            warn "Check logs with: sudo journalctl -u nodeice-board.service -f"
        fi
    fi

    # --- Summary ------------------------------------------------------------------------
    echo
    info "===== Setup Complete! ====="
    echo
    echo -e "Installed to:    ${GREEN}$PROJECT_DIR${NC}"
    echo -e "Runs as user:    ${GREEN}$TARGET_USER${NC}"
    echo -e "Notice board:    ${GREEN}nodeice-board.service${NC} (enabled at boot)"
    if [ "$MATRIX_OK" -eq 1 ]; then
        echo -e "Matrix display:  ${GREEN}nodeice-matrix.service${NC} (enabled at boot)"
    else
        echo -e "Matrix display:  ${YELLOW}not installed${NC}"
    fi
    echo
    echo -e "${YELLOW}Useful commands:${NC}"
    echo -e "  ${GREEN}sudo systemctl status nodeice-board.service${NC}"
    echo -e "  ${GREEN}sudo journalctl -u nodeice-board.service -f${NC}"
    if [ "$MATRIX_OK" -eq 1 ]; then
        echo -e "  ${GREEN}sudo systemctl status nodeice-matrix.service${NC}"
        echo -e "  ${GREEN}sudo journalctl -u nodeice-matrix.service -f${NC}"
    fi
    if [ "$REBOOT_NEEDED" -eq 1 ]; then
        echo
        warn "Onboard audio was disabled for the matrix display."
        warn "REBOOT NOW to finish setup: sudo reboot"
    fi
}

main "$@"
