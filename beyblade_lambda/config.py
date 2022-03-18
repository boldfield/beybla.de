class StorageConfig:
    def __init__(self, state):
        self._state = state

    @property
    def state(self):
        return self._state

    def get_epi_data_prefix(self):
        return "static/epi/{self.state}/"

    def get_breakthrough_data_prefix(self):
        return f"static/reports/{self.state}/"

    def get_processed_data_prefix(self):
        return f"static/data/{self.state}"

    def get_processed_metadata_key(self):
        return f"{self.get_processed_data_prefix()}/metadata.json"

    def get_processed_epi_data_key(self, md5):
        return f"{self.get_processed_data_prefix()}/epi_{md5}.json"

    def get_processed_breakthrough_data_key(self, md5):
        return f"{self.get_processed_data_prefix()}/breakthrough_{md5}.json"
