import subprocess
from datetime import datetime, timedelta, time
from typing import Dict, Any, Optional, List
from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
import uuid
import time

from bigchaindb_driver.exceptions import NotFoundError
from pymongo import MongoClient
from uvicorn import logging


class CertificateAdapter:
    def __init__(self, coordinator1='http://localhost:9984',
                 member2='http://localhost:9986',
                 member3='http://localhost:9988',
                 member4='http://localhost:9990'):

        self.coordinator1 = BigchainDB(coordinator1)
        self.member2 = BigchainDB(member2)
        self.member3 = BigchainDB(member3)
        self.member4 = BigchainDB(member4)

        self.keypair = generate_keypair()

        # Usa l'hostname del container come definito nel docker-compose
        self.mongo_uri = 'mongodb://localhost:27017/'
        self.mongo_client = MongoClient(self.mongo_uri)
        self.mongo_db = self.mongo_client.bigchain

    def _datetime_to_str(self, dt):
        return dt.strftime('%Y-%m-%dT%H:%M:%S')

    def _str_to_datetime(self, dt_str):
        return datetime.strptime(dt_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')

    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """Get a single transaction by ID"""
        try:
            return self.coordinator1.transactions.retrieve(tx_id)
        except Exception as e:
            print(f"Error getting transaction: {str(e)}")
            return None

    def get_transaction_history(self, asset_id: str) -> List[Dict]:
        """Get all transactions for an asset"""
        try:
            return self.coordinator1.transactions.get(asset_id=asset_id)
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
            prepared_transfer_tx = self.coordinator1.transactions.prepare(
                operation='TRANSFER',
                asset=transfer_asset,
                metadata=revocation_metadata,
                inputs=transfer_input,
                recipients=self.keypair.public_key,
            )

            fulfilled_transfer_tx = self.coordinator1.transactions.fulfill(
                prepared_transfer_tx,
                private_keys=self.keypair.private_key
            )

            # Send transaction
            return self.coordinator1.transactions.send_commit(fulfilled_transfer_tx)

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
        latest_tx = self.coordinator1.transactions.get(asset_id=certificate_tx_id)[-1]

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

        prepared_transfer_tx = self.coordinator1.transactions.prepare(
            operation='TRANSFER',
            asset=prepared_data['asset'],
            metadata=prepared_data['metadata'],
            inputs=transfer_input,
            recipients=self.keypair.public_key,
        )

        fulfilled_transfer_tx = self.coordinator1.transactions.fulfill(
            prepared_transfer_tx,
            private_keys=self.keypair.private_key
        )

        return self.coordinator1.transactions.send_commit(fulfilled_transfer_tx)

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

    def check_node_connection(self):
        """Check connection to nodes"""
        try:
            # Check primary node
            primary_info = self.coordinator1.info()
            print("Primary node connected successfully")
            print(f"Primary node info: {primary_info}")

            # Check secondary node if exists
            if self.member2:
                secondary_info = self.member2.info()
                print("Secondary node connected successfully")
                print(f"Secondary node info: {secondary_info}")

            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def create_test_transaction(self):
        """Create a simple test transaction"""
        try:
            # Simple test asset
            test_asset = {
                'data': {
                    'test': 'communication_check',
                    'timestamp': int(time.time())
                }
            }

            # Prepare transaction
            prepared_tx = self.coordinator1.transactions.prepare(
                operation='CREATE',
                signers=self.keypair.public_key,
                asset=test_asset
            )

            # Fulfill transaction
            fulfilled_tx = self.coordinator1.transactions.fulfill(
                prepared_tx,
                private_keys=self.keypair.private_key
            )

            print('primo nodo creata ')
            # Send transaction
            return self.coordinator1.transactions.send_commit(fulfilled_tx)

        except Exception as e:
            print(f"Error creating test transaction: {e}")
            return None

    def verify_transaction(self, tx_id: str, max_retries: int = 5):
        """
        Verify if transaction exists on secondary node with retries
        """
        for attempt in range(max_retries):
            try:
                # Try to get transaction from secondary node
                verification = self.member2.transactions.retrieve(tx_id)
                if verification:
                    print(f"Attempt {attempt + 1}: Transaction found on secondary node")
                    return verification

            except Exception as e:
                print(f"Attempt {attempt + 1}: Error verifying transaction: {e}")
                if attempt < max_retries - 1:
                    print("Waiting before retry...")
                    time.sleep(2)  # Wait between retries
                    continue

            print(f"Attempt {attempt + 1}: Transaction not found")
            time.sleep(2)  # Wait before next attempt

        print("All verification attempts failed")
        return None

    def verify_node_communication(self) -> Dict:
        try:
            test_tx = self.create_test_transaction()
            if not test_tx:
                return {
                    'success': False,
                    'error': 'Failed to create test transaction',
                    'primary_node_status': 'Failed',
                    'secondary_node_status': 'Not tested'
                }

            # Aumenta il tempo di attesa per la propagazione
            time.sleep(5)  # Aumentato da 2 a 5 secondi

            verification = self.verify_transaction(test_tx['id'], max_retries=5)  # Aumentato i retry
            if not verification:
                return {
                    'success': False,
                    'error': 'Transaction verification failed on secondary node',
                    'primary_node_status': 'Success',
                    'secondary_node_status': 'Failed'
                }

            return {
                'success': True,
                'error': None,
                'primary_node_status': 'Success',
                'secondary_node_status': 'Success',
                'transaction_id': test_tx['id'],
                'verification_details': verification
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'primary_node_status': 'Unknown',
                'secondary_node_status': 'Unknown'
            }

    def get_container_ip(container_name):
        cmd = f"docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {container_name}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()

    def print_ledger(self) -> List[Dict]:
        """
        Retrieves and prints all certificates by using BigchainDB API and MongoDB
        """
        try:
            print("\n=== FULL CERTIFICATE LEDGER ===")
            certificates = []

            # Connect to MongoDB using docker network alias
            client = MongoClient('mongodb://bigchaindb1:27017/',
                                 serverSelectionTimeoutMS=5000,
                                 connectTimeoutMS=5000)

            db = client.bigchain

            # Get all transactions that are certificate creations
            cursor = db.transactions.find(
                {"$and": [
                    {"operation": "CREATE"},
                    {"asset.data.type": "micro_certificate"}
                ]}
            )

            for tx in cursor:
                try:
                    # Get certificate details
                    certificate_details = self.verify_certificate(tx['id'])
                    if certificate_details:
                        print(f"\nCertificate ID: {tx['id']}")
                        print(f"Holder: {tx['asset']['data']['holder']}")
                        print(f"Competence: {tx['asset']['data']['competence']}")
                        print(f"Status: {certificate_details['valid']}")
                        print("=====================")

                        certificates.append({
                            'id': tx['id'],
                            'details': certificate_details,
                            'asset': tx['asset'],
                            'metadata': tx['metadata']
                        })

                except Exception as e:
                    print(f"Error processing certificate {tx['id']}: {str(e)}")
                    continue

            return certificates

        except Exception as e:
            print(f"Error in print_ledger: {str(e)}")
            return []
        finally:
            if 'client' in locals():
                client.close()