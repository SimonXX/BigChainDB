from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
import json
import time
import pymongo
from bson.objectid import ObjectId

class BigchainDBNetwork:
    def __init__(self):
        # Indirizzi dei nodi BigchainDB
        self.nodes = [
            BigchainDB('http://localhost:9984'),
            BigchainDB('http://localhost:9985'),
            BigchainDB('http://localhost:9986'),
            BigchainDB('http://localhost:9987')
        ]

        # Connessione al database MongoDB
        self.mongo_client = pymongo.MongoClient('mongodb://localhost:27017')
        self.mongo_db = self.mongo_client['bigchaindb']
        self.mongo_transactions = self.mongo_db['blocks']

    def propagate_transaction(self, signed_tx):
        """
        Propaga una transazione a tutti i nodi.
        """
        print("🔄 Propagando la transazione a tutti i nodi...")
        for i, node in enumerate(self.nodes):
            try:
                node.transactions.send_commit(signed_tx)
                print(f"✅ Transazione propagata al nodo {i + 1}")
            except Exception as e:
                print(f"⚠️ Nodo {i + 1} fallito: {str(e)}")

    def verify_propagation(self, tx_id):
        """
        Verifica se la transazione è presente in tutti i nodi.
        """
        print("\n🔍 Verificando la propagazione della transazione...")
        all_verified = True
        for i, node in enumerate(self.nodes):
            try:
                tx = node.transactions.retrieve(tx_id)
                if tx and tx['id'] == tx_id:
                    print(f"✅ Nodo {i + 1}: Transazione verificata")
                else:
                    print(f"⚠️ Nodo {i + 1}: Transazione non trovata")
                    all_verified = False
            except Exception as e:
                print(f"⚠️ Nodo {i + 1}: Errore nel recupero della transazione - {str(e)}")
                all_verified = False
        return all_verified

    def get_transactions_from_mongo(self):
        """
        Recupera tutte le transazioni confermate dal database MongoDB.
        """
        print("\n📜 Recupero delle transazioni dal database MongoDB...")
        try:
            transactions = list(self.mongo_transactions.find({}))
            print(f"✅ Recuperate {len(transactions)} transazioni dal database.")
            return transactions
        except Exception as e:
            print(f"❌ Errore durante il recupero delle transazioni: {str(e)}")
            return []

    def create_asset(self, owner_keypair, asset_data):
        """
        Crea un asset su BigchainDB e lo propaga ai nodi.
        """
        print("\n🔷 Creazione di un nuovo asset...")
        node = self.nodes[0]  # Usa il primo nodo per creare la transazione

        try:
            prepared_tx = node.transactions.prepare(
                operation='CREATE',
                signers=owner_keypair.public_key,
                asset={'data': asset_data},
                metadata={'timestamp': time.time()}
            )

            signed_tx = node.transactions.fulfill(
                prepared_tx,
                private_keys=owner_keypair.private_key
            )

            print("📤 Inviando la transazione...")
            tx_id = signed_tx['id']
            node.transactions.send_commit(signed_tx)
            print(f"✅ Transazione creata con ID: {tx_id}")

            # Propaga la transazione agli altri nodi
            self.propagate_transaction(signed_tx)

            # Verifica la propagazione
            if self.verify_propagation(tx_id):
                print("✅ Transazione propagata con successo a tutti i nodi")
            else:
                print("⚠️ La propagazione non è completa")

            # Salva la transazione nel database MongoDB
            self.mongo_transactions.insert_one(signed_tx)

            return tx_id

        except Exception as e:
            print(f"❌ Errore durante la creazione dell'asset: {str(e)}")
            return None

    def print_ledger_with_consensus(self):
        """
        Stampa tutte le transazioni presenti nel ledger della rete BigchainDB
        verificando il consenso tra i nodi.
        """
        print("\n📜 Ledger della rete con consenso:")

        # Recupera le transazioni dal database MongoDB
        transactions = self.get_transactions_from_mongo()

        # Verifica il consenso per ogni transazione
        confirmed_transactions = []
        for tx in transactions:
            if self.verify_propagation(tx['id']):
                confirmed_transactions.append(tx)

        # Stampa il ledger con consenso
        if confirmed_transactions:
            print("\n✅ Transazioni confermate dalla rete:")
            for i, tx in enumerate(confirmed_transactions, start=1):
                print(f"\n🔹 Transazione {i}:")
                print(json.dumps(tx, indent=4))
        else:
            print("⚠️ Nessuna transazione ha raggiunto il consenso completo.")

def main():
    print("🚀 Avvio della demo BigchainDB con integrazione MongoDB")
    print("=" * 50)

    network = BigchainDBNetwork()

    alice = generate_keypair()
    print(f"👤 Chiave pubblica di Alice: {alice.public_key[:8]}...")

    asset_data = {
        'type': 'demo_asset',
        'name': 'Test Asset',
        'description': 'Questa è una demo per testare la propagazione',
        'value': 100
    }

    tx_id = network.create_asset(alice, asset_data)

    # Chiamata al metodo della classe per stampare il ledger
    network.print_ledger_with_consensus()

    if tx_id:
        print(f"✅ Demo completata con successo. Transazione ID: {tx_id}")
    else:
        print("❌ Demo fallita.")

if __name__ == "__main__":
    main()