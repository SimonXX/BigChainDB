from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
from typing import Dict, Any

class BlockchainService:
    def __init__(self, url: str = 'http://localhost:9984'):
        self.bdb = BigchainDB(url)
        self.issuer = generate_keypair()

    def create_asset(self, asset_data: Dict[str, Any], metadata: Dict[str, Any]) -> Dict:
        prepared_tx = self.bdb.transactions.prepare(
            operation='CREATE',
            signers=self.issuer.public_key,
            asset=asset_data,
            metadata=metadata
        )

        fulfilled_tx = self.bdb.transactions.fulfill(
            prepared_tx,
            private_keys=self.issuer.private_key
        )

        return self.bdb.transactions.send_commit(fulfilled_tx)

    def retrieve_asset(self, asset_id: str) -> Dict:
        try:
            # Get all transactions for this asset
            transactions = self.bdb.transactions.get(asset_id=asset_id)

            # If no transactions found, return None
            if not transactions:
                return None

            # Get the latest transaction
            latest_tx = transactions[-1] if isinstance(transactions, list) else transactions
            return latest_tx
        except Exception as e:
            print(f"Error retrieving asset: {str(e)}")
            return None