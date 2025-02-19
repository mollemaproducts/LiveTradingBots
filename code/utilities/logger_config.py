import logging
import os

class Logger:
    _log_filename = None  # No default filename
    _instance = None  # Shared logger instance

    @staticmethod
    def init(log_path, coin) -> None:
        """Sets the log file name before getting the logger."""
        Logger._log_filename = Logger.create_filename_for_coin(log_path, coin)
        Logger._instance = None  # Reset instance to apply new filename

    @staticmethod
    def info(log_message) -> None:
        """Returns a shared logger instance, fails if filename is not set."""
        if Logger._log_filename is None:
            raise RuntimeError("Log filename must be set using Logger.init() before getting the logger.")

        if Logger._instance is None:
            logger = logging.getLogger("SharedLogger")

            # Remove existing handlers to prevent duplicates
            while logger.hasHandlers():
                logger.handlers.clear()

            file_handler = logging.FileHandler(Logger._log_filename, mode='a')  # Append mode
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.setLevel(logging.INFO)

            logger.info(log_message)

    @staticmethod
    def create_filename_for_coin(log_path, coin):
        """Creates a log filename for a specific coin, ensuring the directory exists."""
        if not log_path:
            raise ValueError("log_path cannot be empty")

        os.makedirs(log_path, exist_ok=True)  # Ensure log directory exists
        return os.path.join(log_path, f"bot_{coin.lower()}.log")
