import os
import sys
import platform
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

# Version information
LIAM_VERSION = "2.1.1" 
LIAM_BUILD_DATE = "2025-06-06" 
LIAM_AUTHOR = "Awiones"

# Configure logging
def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration for Liam AI.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("LiamAI")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not create log file {log_file}: {e}")
    
    return logger

# Global logger instance
logger = setup_logging()

# ASCII Art Banner
LIAM_ASCII_BANNER = r"""                                                                                                                                                                                                    
                            @@@@@@@@@@                                
                        @@@@@@@@@@@@@@@@@@                            
                    @@@@@@# @@@@@@@@@@@@@@                             
                @@@@@@@@@@@@@@@@@@@@@@@@@@@@@                         
        @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@                      
            @@@@@@@@@@  @@@@@@@@@@@@@@@@@@@@ @@@@@@@                    
        @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@  @@@@@@@                  
        @@@@@@@@@@@@@@@@@@@@@@@@@@@    @@@   @   @@@@@                
        @@@@@@@@@@@@@@@@@@@@@@@@@@@@ @@@   @@@@@@                     
        @@@@@@  @@@@@@@@@@@@@@@@@@@      @@@@@@@@@                   
            @  @@    @@@@@@@@@@@@@@@@@  @@@    @@@@@@@@                 
                    @@@@@@@@@@@@@@ @   @@@@@   @@@@@@@                
                    @@@@@@@@@ @@@@    @@@@@@@   @@@@@@               
                    @@ @@@@@ @@@@ @@@    @@@@@@@@@   @@@@               
                @@@ @@@@@   @@ @@    @@@@@@@@@@@   @@@@              
            @   @@@ @@@@@           @@@@@@@@@@@@@    @@%             
            @@@@@  @@@@@@          @@@@@@@  @@@@@     @@             
                @ @@@@            @@@@@@@@  @@@@@@                   
                @@@@@@@@       @@  @@@@@@@@   @@@@@@@                   
                @@@@@@@      @@@ @@@@@@@    @@@@@@                     
                @@@       @@@ @@@@@@      @@@@                       
                            @@@@@@@@      @@@                          
                            @@@@@@@      @                             
                            @@@@@                                      
                            @@                                                                                                                                          
"""

class Colors:
    """ANSI color codes for terminal output styling."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


def print_banner(colored: bool = True) -> None:
    """
    Print the Liam AI Assistant banner.
    
    Args:
        colored: Whether to print the banner with colors.
    """
    if colored and supports_color():
        print(f"{Colors.CYAN}{LIAM_ASCII_BANNER}{Colors.RESET}")
        print(f"{Colors.BOLD}Liam AI Assistant - Version {LIAM_VERSION}{Colors.RESET}")
        print(f"Build Date: {LIAM_BUILD_DATE}\n")
    else:
        print(LIAM_ASCII_BANNER)
        print(f"Liam AI Assistant - Version {LIAM_VERSION}")
        print(f"Build Date: {LIAM_BUILD_DATE}\n")


def supports_color() -> bool:
    """
    Check if the terminal supports color output.
    
    Returns:
        True if the terminal supports color, False otherwise.
    """
    # Check if we're on Windows
    if platform.system() == "Windows":
        return os.environ.get("TERM") is not None or "ANSICON" in os.environ
    
    # Check if we're connected to a terminal
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    
    # Check if we have a color-supporting terminal
    if os.environ.get("TERM") == "dumb":
        return False
    
    return True


def log_message(message: str, level: str = "INFO", colored: bool = True) -> None:
    """
    Log a message with timestamp and log level.
    
    Args:
        message: The message to log.
        level: The log level (INFO, WARNING, ERROR, DEBUG).
        colored: Whether to use colors in the output.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Define color based on log level
    color = Colors.RESET
    if colored and supports_color():
        if level == "INFO":
            color = Colors.GREEN
        elif level == "WARNING":
            color = Colors.YELLOW
        elif level == "ERROR":
            color = Colors.RED
        elif level == "DEBUG":
            color = Colors.MAGENTA
    
    # Format and print the message
    if colored and supports_color():
        print(f"{timestamp} [{color}{level}{Colors.RESET}] {message}")
    else:
        print(f"{timestamp} [{level}] {message}")


def progress_bar(iteration: int, total: int, prefix: str = '', suffix: str = '', 
                 decimals: int = 1, length: int = 50, fill: str = '█', 
                 colored: bool = True) -> None:
    """
    Display a progress bar in the console.
    
    Args:
        iteration: Current iteration
        total: Total iterations
        prefix: Prefix string
        suffix: Suffix string
        decimals: Decimal places for percentage
        length: Character length of bar
        fill: Bar fill character
        colored: Whether to use colors
    """
    percent = ('{0:.' + str(decimals) + 'f}').format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    
    if colored and supports_color():
        bar_color = Colors.GREEN if iteration == total else Colors.YELLOW
        print(f'\r{prefix} |{bar_color}{bar}{Colors.RESET}| {percent}% {suffix}', end='\r')
    else:
        print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    
    # Print new line when complete
    if iteration == total:
        print()


def get_system_info() -> Dict[str, Any]:
    """
    Get system information.
    
    Returns:
        A dictionary containing system information.
    """
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "liam_version": LIAM_VERSION,
        "timestamp": datetime.now().isoformat()
    }


def print_system_info(colored: bool = True) -> None:
    """
    Print system information to the console.
    
    Args:
        colored: Whether to use colors in the output.
    """
    info = get_system_info()
    
    if colored and supports_color():
        print(f"{Colors.BOLD}{Colors.CYAN}System Information:{Colors.RESET}")
        print(f"{Colors.BOLD}OS:{Colors.RESET} {info['os']} {info['os_version']}")
        print(f"{Colors.BOLD}Architecture:{Colors.RESET} {info['architecture']}")
        print(f"{Colors.BOLD}Processor:{Colors.RESET} {info['processor']}")
        print(f"{Colors.BOLD}Python Version:{Colors.RESET} {info['python_version']}")
        print(f"{Colors.BOLD}Liam Version:{Colors.RESET} {info['liam_version']}")
        print(f"{Colors.BOLD}Timestamp:{Colors.RESET} {info['timestamp']}")
    else:
        print("System Information:")
        print(f"OS: {info['os']} {info['os_version']}")
        print(f"Architecture: {info['architecture']}")
        print(f"Processor: {info['processor']}")
        print(f"Python Version: {info['python_version']}")
        print(f"Liam Version: {info['liam_version']}")
        print(f"Timestamp: {info['timestamp']}")


def measure_execution_time(func):
    """
    Decorator to measure the execution time of a function.
    
    Args:
        func: The function to measure.
        
    Returns:
        Wrapper function that measures execution time.
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        log_message(f"Function '{func.__name__}' executed in {end_time - start_time:.4f} seconds.", 
                   level="DEBUG")
        return result
    return wrapper


def format_size(size_bytes: int) -> str:
    """
    Format a file size in bytes to a human-readable string.
    
    Args:
        size_bytes: Size in bytes.
        
    Returns:
        Human-readable size string.
    """
    if size_bytes == 0:
        return "0B"
    
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"
