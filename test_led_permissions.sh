#!/bin/bash
# Test script for LED matrix permissions

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}===== Testing RGB LED Matrix Permissions =====${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Running as root. Some tests will be skipped.${NC}"
    IS_ROOT=true
else
    echo -e "Running as user: $(whoami)"
    IS_ROOT=false
fi

# Check if user is in gpio group
if getent group gpio > /dev/null; then
    if id -nG "$USER" | grep -qw gpio; then
        echo -e "User is in gpio group: ${GREEN}OK${NC}"
    else
        echo -e "User is NOT in gpio group: ${RED}FAIL${NC}"
        echo -e "Run: ${YELLOW}sudo usermod -a -G gpio $USER${NC}"
        echo -e "Then log out and log back in for changes to take effect."
    fi
else
    echo -e "GPIO group does not exist (may not be needed on some systems)"
fi

# Test GPIO access
echo -e "\nTesting GPIO access..."
if [ -e /dev/gpiomem ]; then
    if [ -w /dev/gpiomem ]; then
        echo -e "Can write to /dev/gpiomem: ${GREEN}OK${NC}"
    else
        echo -e "Cannot write to /dev/gpiomem: ${RED}FAIL${NC}"
        echo -e "Run: ${YELLOW}sudo chmod a+rw /dev/gpiomem${NC}"
    fi
else
    echo -e "GPIO memory device (/dev/gpiomem) not found: ${RED}FAIL${NC}"
    echo -e "This may indicate that GPIO support is not enabled on this system."
fi

# Test if Python can import the rgbmatrix module
echo -e "\nTesting Python RGB Matrix module..."
python3 -c "import rgbmatrix" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "RGB Matrix module is installed: ${GREEN}OK${NC}"
    
    # Get version information
    echo -e "\nRGB Matrix module version:"
    python3 -c "import rgbmatrix; print(f'Version: {rgbmatrix.__version__ if hasattr(rgbmatrix, \"__version__\") else \"Unknown\"}')" 2>/dev/null
else
    echo -e "RGB Matrix module is NOT installed: ${RED}FAIL${NC}"
    echo -e "Install the module with:"
    echo -e "${YELLOW}git clone https://github.com/hzeller/rpi-rgb-led-matrix.git${NC}"
    echo -e "${YELLOW}cd rpi-rgb-led-matrix/bindings/python/${NC}"
    echo -e "${YELLOW}make build-python${NC}"
    echo -e "${YELLOW}sudo make install-python${NC}"
fi

# Check for Adafruit HAT
echo -e "\nChecking for Adafruit RGB Matrix HAT..."
if [ -e /proc/device-tree/hat/product ]; then
    HAT_PRODUCT=$(cat /proc/device-tree/hat/product 2>/dev/null | tr -d '\0')
    if [[ "$HAT_PRODUCT" == *"RGB Matrix HAT"* ]] || [[ "$HAT_PRODUCT" == *"Adafruit"* ]]; then
        echo -e "Adafruit RGB Matrix HAT detected: ${GREEN}OK${NC}"
        echo -e "Product: $HAT_PRODUCT"
    else
        echo -e "HAT detected, but not an Adafruit RGB Matrix HAT: ${YELLOW}WARNING${NC}"
        echo -e "Product: $HAT_PRODUCT"
    fi
else
    echo -e "No HAT information found: ${YELLOW}WARNING${NC}"
    echo -e "This may be normal if you're not using a HAT or if you're not on a Raspberry Pi."
fi

# Check for I2C access (used by some RGB matrix HATs)
echo -e "\nChecking for I2C access..."
if [ -e /dev/i2c-1 ]; then
    if [ -r /dev/i2c-1 ]; then
        echo -e "Can read from I2C device: ${GREEN}OK${NC}"
    else
        echo -e "Cannot read from I2C device: ${RED}FAIL${NC}"
        echo -e "Run: ${YELLOW}sudo usermod -a -G i2c $USER${NC}"
        echo -e "And: ${YELLOW}sudo chmod a+rw /dev/i2c-1${NC}"
    fi
else
    echo -e "I2C device not found: ${YELLOW}WARNING${NC}"
    echo -e "This may be normal if I2C is not enabled or if you're not on a Raspberry Pi."
    echo -e "To enable I2C, run: ${YELLOW}sudo raspi-config${NC} and enable I2C under Interfacing Options."
fi

# Check for SPI access (used by some RGB matrix configurations)
echo -e "\nChecking for SPI access..."
if [ -e /dev/spidev0.0 ]; then
    if [ -r /dev/spidev0.0 ]; then
        echo -e "Can read from SPI device: ${GREEN}OK${NC}"
    else
        echo -e "Cannot read from SPI device: ${RED}FAIL${NC}"
        echo -e "Run: ${YELLOW}sudo usermod -a -G spi $USER${NC}"
        echo -e "And: ${YELLOW}sudo chmod a+rw /dev/spidev0.0${NC}"
    fi
else
    echo -e "SPI device not found: ${YELLOW}WARNING${NC}"
    echo -e "This may be normal if SPI is not enabled or if you're not on a Raspberry Pi."
    echo -e "To enable SPI, run: ${YELLOW}sudo raspi-config${NC} and enable SPI under Interfacing Options."
fi

# Check if the rpi-rgb-led-matrix library is installed
echo -e "\nChecking for rpi-rgb-led-matrix library..."
if [ -d "rpi-rgb-led-matrix" ]; then
    echo -e "rpi-rgb-led-matrix directory found: ${GREEN}OK${NC}"
else
    echo -e "rpi-rgb-led-matrix directory not found: ${YELLOW}WARNING${NC}"
    echo -e "This may be normal if you installed the library globally or in a different location."
    echo -e "To clone the library, run: ${YELLOW}git clone https://github.com/hzeller/rpi-rgb-led-matrix.git${NC}"
fi

# Check for Python PIL/Pillow library (required for image display)
echo -e "\nChecking for Python PIL/Pillow library..."
python3 -c "from PIL import Image" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "PIL/Pillow library is installed: ${GREEN}OK${NC}"
    
    # Get version information
    echo -e "PIL/Pillow version:"
    python3 -c "from PIL import Image; import PIL; print(f'Version: {PIL.__version__}')" 2>/dev/null
else
    echo -e "PIL/Pillow library is NOT installed: ${RED}FAIL${NC}"
    echo -e "Install with: ${YELLOW}pip3 install Pillow${NC}"
fi

# Summary
echo -e "\n${YELLOW}===== Test Summary =====${NC}"
echo -e "If you see any ${RED}FAIL${NC} messages above, you'll need to fix those issues before the LED matrix will work properly."
echo -e "Some ${YELLOW}WARNING${NC} messages may be normal depending on your setup."

echo -e "\n${YELLOW}===== Recommended Next Steps =====${NC}"
echo -e "1. Fix any permission issues identified above"
echo -e "2. Run the test_led_matrix.py script to verify the LED matrix works:"
echo -e "   ${YELLOW}python3 test_led_matrix.py${NC}"
echo -e "3. If you're still having issues, check the rpi-rgb-led-matrix documentation:"
echo -e "   ${YELLOW}https://github.com/hzeller/rpi-rgb-led-matrix${NC}"

echo -e "\nTest completed."
