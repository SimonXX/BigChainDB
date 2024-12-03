from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair

# Inizializzazione
keypair = generate_keypair()
node_url = 'http://localhost:9984'  # URL del nodo BigchainDB
network = BigchainDB(node_url)


# Funzione per inviare una transazione semplice di test
def prepare_asset_creation(self, holder_name: str, surname: str,
                           competence: str, identifier: str,
                           valid_months: int = 12) -> Dict[str, Any]:
    """
    Prepare certificate data for creation
    """
    certificate_id = str(uuid.uuid4())
    issue_date = datetime.now()
    expiry_date = issue_date + timedelta(days=30 * valid_months)

    asset_data = {
        'data': {
            'certificate_id': certificate_id,
            'type': 'micro_certificate',
            'holder': {
                'name': holder_name,
                'surname': surname,
                'identifier': identifier
            },
            'competence': competence,
            'issuer_public_key': self.keypair.public_key
        }
    }

    metadata = {
        'status': 'valid',
        'issue_date': self._datetime_to_str(issue_date),
        'expiry_date': self._datetime_to_str(expiry_date),
        'version': '1.0'
    }

    return {
        'asset': asset_data,
        'metadata': metadata
    }


def create_certificate(self, prepared_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new certificate"""
    prepared_tx = self.coordinator1.transactions.prepare(
        operation='CREATE',
        signers=self.keypair.public_key,
        asset=prepared_data['asset'],
        metadata=prepared_data['metadata']
    )

    fulfilled_tx = self.coordinator1.transactions.fulfill(
        prepared_tx,
        private_keys=self.keypair.private_key
    )

    return self.coordinator1.transactions.send_commit(fulfilled_tx)

# Esegui il test di transazione
simple_test_transaction()
