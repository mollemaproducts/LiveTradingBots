import json
import os

class TrackerFile:
    def __init__(self, path_tracker_file, symbol) -> None:
        self.path_tracker_file = path_tracker_file
        self.tracker_file = self.get_filename_for_symbol(symbol)

        if not os.path.exists(self.tracker_file):
            with open(self.tracker_file, 'w') as file:
                json.dump({"status": "ok_to_trade", "last_side": None, "stop_loss_ids": []}, file)

    def read_tracker_file(self):
        with open(self.tracker_file, 'r') as file:
            return json.load(file)

    def update_tracker_file(self, data):
        with open(self.tracker_file, 'w') as file:
            json.dump(data, file)

    def get_filename_for_symbol(self, symbol):
        filename = f"tracker_{symbol.replace('/', '-').replace(':', '-')}.json"
        return os.path.join(self.path_tracker_file, filename)  # ✅ Use instance variable
