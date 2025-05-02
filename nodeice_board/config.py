"""
Configuration module for Nodeice Board.
"""

import os
import logging
import yaml
from typing import Dict, Any, Optional

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
