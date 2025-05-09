"""
Configuration module for Nodeice Board.
"""

import os
import logging
import yaml
from typing import Dict, Any, Optional, Tuple, Union, List

logger = logging.getLogger("NodeiceBoard")

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path: Path to the configuration file.
        
    Returns:
        A dictionary containing the configuration.
    """
    config = {}
    
    try:
        # Check if the config file exists
        if not os.path.exists(config_path):
            logger.warning(f"Config file not found: {config_path}")
            return config
            
        # Load the config file with explicit UTF-8 encoding
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        logger.info(f"Loaded configuration from {config_path}")
        
        # Validate the config
        if not isinstance(config, dict):
            logger.warning(f"Invalid configuration format in {config_path}")
            return {}
            
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return {}

def get_device_names(config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """
    Get device names from the configuration.
    
    Args:
        config: The configuration dictionary.
        
    Returns:
        A tuple of (long_name, short_name).
    """
    long_name = None
    short_name = None
    
    try:
        if 'Nodeice_board' in config:
            nodeice_config = config['Nodeice_board']
            
            if isinstance(nodeice_config, dict):
                if 'Long_Name' in nodeice_config:
                    long_name = nodeice_config['Long_Name']
                    
                if 'Short_Name' in nodeice_config:
                    short_name = nodeice_config['Short_Name']
    except Exception as e:
        logger.error(f"Error getting device names from config: {e}")
        
    return long_name, short_name

def get_info_url(config: Dict[str, Any]) -> str:
    """
    Get the information URL from the configuration.
    
    Args:
        config: The configuration dictionary.
        
    Returns:
        The URL string, or a default URL if not found.
    """
    default_url = "https://github.com/AndreasThinks/nodeice-board"
    
    try:
        if 'Nodeice_board' in config:
            nodeice_config = config['Nodeice_board']
            
            if isinstance(nodeice_config, dict) and 'Info_URL' in nodeice_config:
                return nodeice_config['Info_URL']
    except Exception as e:
        logger.error(f"Error getting info URL from config: {e}")
        
    return default_url

def get_expiration_days(config: Dict[str, Any]) -> int:
    """
    Get the post expiration days from the configuration.
    
    Args:
        config: The configuration dictionary.
        
    Returns:
        The number of days after which posts expire, or the default value (7) if not found.
    """
    default_days = 7
    
    try:
        if 'Nodeice_board' in config:
            nodeice_config = config['Nodeice_board']
            
            if isinstance(nodeice_config, dict) and 'Expiration_Days' in nodeice_config:
                expiration_days = nodeice_config['Expiration_Days']
                if isinstance(expiration_days, int) and expiration_days > 0:
                    return expiration_days
                else:
                    logger.warning(f"Invalid Expiration_Days value: {expiration_days}, using default of {default_days}")
    except Exception as e:
        logger.error(f"Error getting expiration days from config: {e}")
        
    return default_days

def get_led_matrix_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get the LED matrix configuration from the configuration.
    
    Args:
        config: The configuration dictionary.
        
    Returns:
        A dictionary containing the LED matrix configuration, or default values if not found.
    """
    default_config = {
        "Enabled": False,
        "Hardware_Mapping": "adafruit-hat",
        "Rows": 32,
        "Cols": 32,
        "Chain_Length": 1,
        "Parallel": 1,
        "Brightness": 50,
        "GPIO_Slowdown": 2,
        "Display_Mode": "standard",
        "Status_Cycle_Seconds": 5,
        "Message_Effect": "rainbow",
        "Interactive": True,
        "Auto_Brightness": True
    }
    
    matrix_config = {}
    
    try:
        if 'Nodeice_board' in config and 'LED_Matrix' in config['Nodeice_board']:
            matrix_config = config['Nodeice_board']['LED_Matrix']
            
            # Validate the config
            if not isinstance(matrix_config, dict):
                logger.warning(f"Invalid LED_Matrix configuration format, using defaults")
                return default_config
    except Exception as e:
        logger.error(f"Error getting LED matrix config: {e}")
        return default_config
        
    # Merge with defaults
    for key, value in default_config.items():
        if key not in matrix_config:
            matrix_config[key] = value
            
    return matrix_config

def get_led_matrix_enabled(config: Dict[str, Any]) -> bool:
    """
    Check if the LED matrix is enabled in the configuration.
    
    Args:
        config: The configuration dictionary.
        
    Returns:
        True if the LED matrix is enabled, False otherwise.
    """
    try:
        matrix_config = get_led_matrix_config(config)
        return matrix_config.get("Enabled", False)
    except Exception as e:
        logger.error(f"Error checking if LED matrix is enabled: {e}")
        return False
