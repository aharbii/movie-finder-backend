import logging
import sys
import os
from datetime import datetime

def setup_logger(name: str = "movie_finder") -> logging.Logger:
    logger = logging.getLogger(name)
    
    # Prevent duplicated log entries gracefully
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.INFO)
    
    # Configure granular enterprise formatting
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console Diagnostic Output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Rotating Timestamped File Logging outputting to explicit /logs natively
    # To securely map file paths seamlessly out-of-the-box irrespective of execution boundaries:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"app_run_{timestamp}.log")
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()
