from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
import json
import time


class BigchainDBNetwork:
    def __init__(self):
        # Indirizzi dei nodi BigchainDB
        self.nodes = [
            BigchainDB('http://localhost:9984'),
            BigchainDB('http://localhost:9985'),
            BigchainDB('http://localhost:9986'),
            BigchainDB('http://localhost:9987')
        ]

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
        all_transactions = {}
        try:
            # Itera attraverso i nodi per raccogliere le transazioni confermate
            for i, node in enumerate(self.nodes):
                print(f"\n🔍 Recupero transazioni dal nodo {i + 1}...")
                try:
                    # Recupera transazioni per un asset specifico, se noto
                    cursor = node.assets.get(search='')
                    for asset in cursor:
                        tx_id = asset['id']
                        if tx_id not in all_transactions:
                            all_transactions[tx_id] = {
                                'tx': asset,
                                'confirmed_by': set()
                            }
                        all_transactions[tx_id]['confirmed_by'].add(i + 1)
                except Exception as e:
                    print(f"⚠️ Nodo {i + 1} fallito: {str(e)}")

            # Filtra le transazioni che sono confermate da tutti i nodi
            confirmed_transactions = [
                data['tx'] for tx_id, data in all_transactions.items()
                if len(data['confirmed_by']) == len(self.nodes)
            ]

            # Stampa il ledger con consenso
            if confirmed_transactions:
                print("\n✅ Transazioni confermate dalla rete:")
                for i, tx in enumerate(confirmed_transactions, start=1):
                    print(f"\n🔹 Transazione {i}:")
                    print(json.dumps(tx, indent=4))
            else:
                print("⚠️ Nessuna transazione ha raggiunto il consenso completo.")

        except Exception as e:
            print(f"❌ Errore durante l'accesso al ledger: {str(e)}")


def main():
    print("🚀 Avvio della demo BigchainDB senza Tendermint")
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

    # Chiamata al metodo della classe
    network.print_ledger_with_consensus()

    if tx_id:
        print(f"✅ Demo completata con successo. Transazione ID: {tx_id}")
    else:
        print("❌ Demo fallita.")


if __name__ == "__main__":
    main()
