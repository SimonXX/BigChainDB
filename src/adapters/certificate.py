from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
import uuid


class CertificateAdapter:
    def __init__(self, bigchaindb_url='http://localhost:9984'):
        self.bdb = BigchainDB(bigchaindb_url)
        self.issuer = generate_keypair()

    def _datetime_to_str(self, dt):
        return dt.strftime('%Y-%m-%dT%H:%M:%S')

    def _str_to_datetime(self, dt_str):
        return datetime.strptime(dt_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')

    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """Get a single transaction by ID"""
        try:
            return self.bdb.transactions.retrieve(tx_id)
        except Exception as e:
            print(f"Error getting transaction: {str(e)}")
            return None

    def get_transaction_history(self, asset_id: str) -> List[Dict]:
        """Get all transactions for an asset"""
        try:
            return self.bdb.transactions.get(asset_id=asset_id)
        except Exception as e:
            print(f"Error getting transaction history: {str(e)}")
            return []

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
                'issuer_public_key': self.issuer.public_key
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
        prepared_tx = self.bdb.transactions.prepare(
            operation='CREATE',
            signers=self.issuer.public_key,
            asset=prepared_data['asset'],
            metadata=prepared_data['metadata']
        )

        fulfilled_tx = self.bdb.transactions.fulfill(
            prepared_tx,
            private_keys=self.issuer.private_key
        )

        return self.bdb.transactions.send_commit(fulfilled_tx)

    def prepare_revocation(self, certificate_tx_id: str) -> Dict[str, Any]:
        """Prepare revocation data"""
        return {
            'metadata': {
                'status': 'revoked',
                'revocation_date': self._datetime_to_str(datetime.now()),
                'previous_tx': certificate_tx_id
            },
            'asset': {'id': certificate_tx_id}
        }

    def revoke_certificate(self, tx_id: str) -> Dict[str, Any]:
        """Revoke a certificate"""
        try:
            # Get the transaction
            tx = self.get_transaction(tx_id)
            if not tx:
                raise ValueError("Transaction not found")

            # Get the asset id from the transaction
            if tx['operation'] == 'CREATE':
                asset_id = tx['id']
            else:
                asset_id = tx['asset']['id']

            # Prepare revocation metadata
            revocation_metadata = {
                'status': 'revoked',
                'revocation_date': self._datetime_to_str(datetime.now()),
                'previous_tx': tx_id
            }

            transfer_asset = {
                'id': asset_id
            }

            # Create transfer input
            output_index = 0
            output = tx['outputs'][output_index]
            transfer_input = {
                'fulfillment': output['condition']['details'],
                'fulfills': {
                    'output_index': output_index,
                    'transaction_id': tx['id']
                },
                'owners_before': output['public_keys']
            }

            # Prepare and fulfill transfer transaction
            prepared_transfer_tx = self.bdb.transactions.prepare(
                operation='TRANSFER',
                asset=transfer_asset,
                metadata=revocation_metadata,
                inputs=transfer_input,
                recipients=self.issuer.public_key,
            )

            fulfilled_transfer_tx = self.bdb.transactions.fulfill(
                prepared_transfer_tx,
                private_keys=self.issuer.private_key
            )

            # Send transaction
            return self.bdb.transactions.send_commit(fulfilled_transfer_tx)

        except Exception as e:
            raise Exception(f"Failed to revoke certificate: {str(e)}")

    def prepare_renewal(self, certificate_tx_id: str,
                        new_valid_months: int = 12) -> Dict[str, Any]:
        """Prepare renewal data"""
        new_expiry_date = datetime.now() + timedelta(days=30 * new_valid_months)

        return {
            'metadata': {
                'status': 'valid',
                'renewal_date': self._datetime_to_str(datetime.now()),
                'expiry_date': self._datetime_to_str(new_expiry_date),
                'previous_tx': certificate_tx_id
            },
            'asset': {'id': certificate_tx_id}
        }

    def renew_certificate(self, certificate_tx_id: str,
                          new_valid_months: int = 12) -> Dict[str, Any]:
        """Renew a certificate"""
        prepared_data = self.prepare_renewal(certificate_tx_id, new_valid_months)
        latest_tx = self.bdb.transactions.get(asset_id=certificate_tx_id)[-1]

        output_index = 0
        output = latest_tx['outputs'][output_index]
        transfer_input = {
            'fulfillment': output['condition']['details'],
            'fulfills': {
                'output_index': output_index,
                'transaction_id': latest_tx['id']
            },
            'owners_before': output['public_keys']
        }

        prepared_transfer_tx = self.bdb.transactions.prepare(
            operation='TRANSFER',
            asset=prepared_data['asset'],
            metadata=prepared_data['metadata'],
            inputs=transfer_input,
            recipients=self.issuer.public_key,
        )

        fulfilled_transfer_tx = self.bdb.transactions.fulfill(
            prepared_transfer_tx,
            private_keys=self.issuer.private_key
        )

        return self.bdb.transactions.send_commit(fulfilled_transfer_tx)

    def verify_certificate(self, tx_id: str) -> Dict[str, Any]:
        """Verify a certificate"""
        try:
            # Get the initial transaction
            tx = self.get_transaction(tx_id)
            if not tx:
                return {'valid': False, 'reason': 'Certificate not found'}

            # Get the asset id
            asset_id = tx['id'] if tx['operation'] == 'CREATE' else tx['asset']['id']

            # Get all transactions for this asset
            transactions = self.get_transaction_history(asset_id)
            if not transactions:
                return {'valid': False, 'reason': 'Certificate history not found'}

            # Get the latest transaction
            latest_tx = transactions[-1]

            # Check status
            current_status = latest_tx['metadata'].get('status', 'unknown')
            if current_status == 'revoked':
                return {
                    'valid': False,
                    'reason': 'Certificate has been revoked',
                    'revocation_date': latest_tx['metadata'].get('revocation_date')
                }

            # Check expiry
            expiry_date = self._str_to_datetime(latest_tx['metadata']['expiry_date'])
            if datetime.now() > expiry_date:
                return {
                    'valid': False,
                    'reason': 'Certificate has expired',
                    'expiry_date': self._datetime_to_str(expiry_date)
                }

            # Certificate is valid
            return {
                'valid': True,
                'expiry_date': self._datetime_to_str(expiry_date),
                'status': current_status,
                'holder': transactions[0]['asset']['data']['holder'],
                'competence': transactions[0]['asset']['data']['competence'],
                'transaction_history': [
                    {
                        'transaction_id': tx['id'],
                        'operation': tx['operation'],
                        'status': tx['metadata'].get('status'),
                        'timestamp': tx['metadata'].get('issue_date') or
                                     tx['metadata'].get('renewal_date') or
                                     tx['metadata'].get('revocation_date')
                    } for tx in transactions
                ]
            }

        except Exception as e:
            return {'valid': False, 'reason': f'Verification error: {str(e)}'}


