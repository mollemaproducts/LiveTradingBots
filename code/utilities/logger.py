import logging
import os

class LoggerOld:

    @staticmethod
    def init(log_path, coin) -> None:
        # Initialize logging
        log_file = os.path.join(log_path, "bot_" + coin.lower() + ".log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),  # Log to file
                logging.StreamHandler()  # Log to console as well
            ]
        )