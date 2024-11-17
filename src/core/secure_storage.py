import json
from typing import Dict, Any, Optional
from pathlib import Path
import uuid


class SecureStorage:
    def __init__(self, storage_path: str = "secure_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def store(self, data: Dict[str, Any]) -> str:
        """Store sensitive data and return a reference ID"""
        reference_id = str(uuid.uuid4())
        file_path = self.storage_path / f"{reference_id}.json"

        with open(file_path, 'w') as f:
            json.dump(data, f)

        return reference_id

    def retrieve(self, reference_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve sensitive data by reference ID"""
        file_path = self.storage_path / f"{reference_id}.json"

        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def delete(self, reference_id: str) -> bool:
        """Delete sensitive data by reference ID"""
        file_path = self.storage_path / f"{reference_id}.json"

        try:
            file_path.unlink()
            return True
        except FileNotFoundError:
            return False
