from http.client import HTTPException
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
import uuid

from cryptography.fernet import Fernet
from pymongo import MongoClient
import requests
import base64
import json


class Node:
    def __init__(self, url: str, urlTendermint):
        self.bdb = BigchainDB(url)
        self.tenderMint = urlTendermint
        self.keypair = generate_keypair()
        # Generate unique encryption key for this node
        self.encryption_key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.encryption_key)

    def _encrypt_identifier(self, identifier: str) -> dict:
        """Encrypt identifier and return both encrypted data and node public key"""
        encoded_text = identifier.encode()
        encrypted_text = self.cipher_suite.encrypt(encoded_text)
        return {
            'encrypted_data': base64.b64encode(encrypted_text).decode(),
            'issuer_public_key': self.keypair.public_key
        }

    def _decrypt_identifier(self, encrypted_data: dict) -> str:
        """
        Decrypt identifier if this node was the issuer
        Returns decrypted data or 'ENCRYPTED' if not the issuer
        """
        try:
            if encrypted_data['issuer_public_key'] == self.keypair.public_key:
                decoded = base64.b64decode(encrypted_data['encrypted_data'])
                return self.cipher_suite.decrypt(decoded).decode()
            return "ENCRYPTED - Not the issuing node"
        except:
            return "ENCRYPTED - Decryption failed"

    def create_certificate(self, holder_name: str, surname: str,
                           competence: str, identifier: str,
                           valid_months: int = 12) -> Dict:

        encrypted_identifier = self._encrypt_identifier(identifier)

        certificate_data = {
            'data': {
                'certificate_id': str(uuid.uuid4()),
                'type': 'micro_certificate',
                'holder': {
                    'name': holder_name,
                    'surname': surname,
                    'identifier': encrypted_identifier
                },
                'competence': competence,
                'issuer_public_key': self.keypair.public_key
            }
        }

        metadata = {
            'status': 'valid',
            'issue_date': self._datetime_to_str(datetime.now()),
            'expiry_date': self._datetime_to_str(datetime.now() + timedelta(days=30 * valid_months)),
            'version': '1.0'
        }

        return self._create_transaction('CREATE', certificate_data, metadata)

    def revoke_certificate(self, tx_id: str) -> Dict:
        """Revoke a certificate"""
        try:
            # Get the latest transaction
            latest_tx = self.bdb.transactions.get(asset_id=tx_id)[-1]

            # Prepare revocation data
            prepared_data = {
                'metadata': {
                    'status': 'revoked',
                    'revocation_date': self._datetime_to_str(datetime.now()),
                    'previous_tx': tx_id
                },
                'asset': {'id': tx_id}
            }

            # Prepare transfer input
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

            # Create and fulfill transfer transaction
            prepared_transfer_tx = self.bdb.transactions.prepare(
                operation='TRANSFER',
                asset=prepared_data['asset'],
                metadata=prepared_data['metadata'],
                inputs=transfer_input,
                recipients=self.keypair.public_key,
            )

            fulfilled_transfer_tx = self.bdb.transactions.fulfill(
                prepared_transfer_tx,
                private_keys=self.keypair.private_key
            )

            return self.bdb.transactions.send_commit(fulfilled_transfer_tx)

        except Exception as e:
            print(f"Error revoking certificate: {str(e)}")
            raise ValueError(f"Failed to revoke certificate: {str(e)}")

    def verify_certificate(self, tx_id: str) -> Dict:
        tx = self._get_transaction(tx_id)
        if not tx:
            return {'valid': False, 'reason': 'Certificate not found'}

        asset_id = tx['id'] if tx['operation'] == 'CREATE' else tx['asset']['id']
        transactions = self._get_transaction_history(asset_id)

        latest_tx = transactions[-1]
        status = latest_tx['metadata'].get('status', 'unknown')

        if status == 'revoked':
            return {
                'valid': False,
                'reason': 'Certificate revoked',
                'revocation_date': latest_tx['metadata'].get('revocation_date')
            }

        expiry_date = self._str_to_datetime(latest_tx['metadata']['expiry_date'])
        if datetime.now() > expiry_date:
            return {
                'valid': False,
                'reason': 'Certificate expired',
                'expiry_date': self._datetime_to_str(expiry_date)
            }

        # Get the original certificate data (from CREATE transaction)
        original_tx = transactions[0]
        holder_data = original_tx['asset']['data']['holder']

        # Try to decrypt identifier if this node was the issuer
        identifier = holder_data['identifier']
        decrypted_identifier = self._decrypt_identifier(identifier)

        return {
            'valid': True,
            'holder': {
                'name': holder_data['name'],
                'surname': holder_data['surname'],
                'identifier': decrypted_identifier
            },
            'competence': original_tx['asset']['data']['competence'],
            'expiry_date': self._datetime_to_str(expiry_date),
            'status': status,
            'issuer_public_key': original_tx['asset']['data']['issuer_public_key']
        }

    def _create_transaction(self, operation: str, asset: Dict,
                            metadata: Dict, inputs: Optional[Dict] = None) -> Dict:
        prepared = self.bdb.transactions.prepare(
            operation=operation,
            signers=self.keypair.public_key,
            asset=asset,
            metadata=metadata,
            inputs=inputs
        )
        fulfilled = self.bdb.transactions.fulfill(
            prepared,
            private_keys=self.keypair.private_key
        )
        return self.bdb.transactions.send_commit(fulfilled)

    def _get_transaction(self, tx_id: str) -> Optional[Dict]:
        try:
            return self.bdb.transactions.retrieve(tx_id)
        except Exception as e:
            print(f"Error getting transaction: {str(e)}")
            return None

    def _get_transaction_history(self, asset_id: str) -> List[Dict]:
        try:
            return self.bdb.transactions.get(asset_id=asset_id)
        except Exception as e:
            print(f"Error getting transaction history: {str(e)}")
            return []

    def _prepare_transfer_input(self, tx: Dict) -> Dict:
        output_index = 0
        output = tx['outputs'][output_index]
        return {
            'fulfillment': output['condition']['details'],
            'fulfills': {
                'output_index': output_index,
                'transaction_id': tx['id']
            },
            'owners_before': output['public_keys']
        }

    def _datetime_to_str(self, dt: datetime) -> str:
        return dt.strftime('%Y-%m-%dT%H:%M:%S')

    def _str_to_datetime(self, dt_str: str) -> datetime:
        """Convert string to datetime with better error handling"""
        try:
            if not dt_str:
                raise ValueError("Empty date string")
            # Remove any whitespace and split on possible decimal point
            cleaned_dt = dt_str.strip().split('.')[0]
            return datetime.strptime(cleaned_dt, '%Y-%m-%dT%H:%M:%S')
        except (AttributeError, ValueError) as e:
            print(f"Error parsing date: {dt_str}. Error: {str(e)}")
            # Return a default date or raise an exception based on your needs
            raise ValueError(f"Invalid date format: {dt_str}")

    def print_ledger(self) -> List[Dict]:
        """
        Get all transactions in the blockchain using Tendermint API and return them as a list
        """
        try:
            transactions_list = []
            # Get max height
            response = requests.get(f"{self.tenderMint}/status")
            if not response.ok:
                raise Exception(f"Failed to get status: {response.status_code}")

            status_data = response.json()
            max_height = int(status_data['result']['sync_info']['latest_block_height'])

            # Iterate through blocks
            for height in range(1, max_height + 1):
                try:
                    # Get block data
                    block_response = requests.get(
                        f"{self.tenderMint}/block",
                        params={'height': height}
                    )
                    if not block_response.ok:
                        print(f"Skipping block {height}: {block_response.status_code}")
                        continue

                    block_data = block_response.json()
                    block_txs = block_data['result']['block']['data'].get('txs', [])

                    # Skip if no transactions
                    if not block_txs:
                        continue

                    # Process transactions
                    for tx_base64 in block_txs:
                        try:
                            # Decode base64 transaction
                            tx_bytes = base64.b64decode(tx_base64)
                            tx_data = json.loads(tx_bytes)

                            # Add block height to transaction data
                            tx_data['block_height'] = height

                            transactions_list.append(tx_data)
                        except Exception as decode_error:
                            print(f"Error decoding transaction in block {height}: {str(decode_error)}")
                            continue

                except Exception as block_error:
                    print(f"Error processing block {height}: {str(block_error)}")
                    continue

            return transactions_list

        except Exception as e:
            print(f"Error scanning blockchain: {str(e)}")
            return []  # Return empty list instead of raising exception

    def renew_certificate(self, tx_id: str, new_valid_months: int = 12) -> Dict:
        """Renew a certificate"""
        try:
            # Prepare renewal data
            prepared_data = {
                'metadata': {
                    'status': 'valid',
                    'renewal_date': self._datetime_to_str(datetime.now()),
                    'expiry_date': self._datetime_to_str(datetime.now() + timedelta(days=30 * new_valid_months)),
                    'previous_tx': tx_id
                },
                'asset': {'id': tx_id}
            }

            # Get the latest transaction
            latest_tx = self.bdb.transactions.get(asset_id=tx_id)[-1]

            # Prepare transfer input
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

            # Create and fulfill transfer transaction
            prepared_transfer_tx = self.bdb.transactions.prepare(
                operation='TRANSFER',
                asset=prepared_data['asset'],
                metadata=prepared_data['metadata'],
                inputs=transfer_input,
                recipients=self.keypair.public_key,
            )

            fulfilled_transfer_tx = self.bdb.transactions.fulfill(
                prepared_transfer_tx,
                private_keys=self.keypair.private_key
            )

            return self.bdb.transactions.send_commit(fulfilled_transfer_tx)

        except Exception as e:
            print(f"Error renewing certificate: {str(e)}")
            raise ValueError(f"Failed to renew certificate: {str(e)}")