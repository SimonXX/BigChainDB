from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
import time
import json
import requests

# Configurazione dei nodi
nodes = [
    'http://localhost:9984',
    'http://localhost:9986'
]


def check_node_status(node_url):
    try:
        response = requests.get(f"{node_url}/api/v1/")
        if response.status_code == 200:
            print(f"\nStato del nodo {node_url}:")
            print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(f"\nNodo {node_url} ha risposto con status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"\nErrore nella verifica del nodo {node_url}:")
        print(str(e))
        return False


def create_and_send_transaction(node_url):
    print(f"Connessione al nodo: {node_url}")
    bdb = BigchainDB(node_url)

    # Genera keypair
    alice = generate_keypair()
    print(f"Chiave pubblica generata: {alice.public_key}")

    # Crea asset
    asset_data = {
        'data': {
            'message': 'Broadcasting test',
            'timestamp': str(time.time())
        }
    }

    try:
        # Prepara transazione
        prepared_tx = bdb.transactions.prepare(
            operation='CREATE',
            signers=alice.public_key,
            asset=asset_data,
            metadata={'ciao BiGCHAINDB': 'test metadata'}
        )

        print("Transazione preparata:")
        print(json.dumps(prepared_tx, indent=2))

        # Firma transazione
        fulfilled_tx = bdb.transactions.fulfill(
            prepared_tx,
            private_keys=alice.private_key
        )

        print("\nTransazione firmata:")
        print(json.dumps(fulfilled_tx, indent=2))

        # Invia transazione in modalità commit
        sent_tx = bdb.transactions.send_commit(fulfilled_tx)

        return sent_tx['id']

    except Exception as e:
        print(f"\nDettagli errore:")
        print(f"Tipo di errore: {type(e)}")
        print(f"Messaggio di errore: {str(e)}")
        if hasattr(e, 'args'):
            for arg in e.args:
                print(f"Argomento errore: {arg}")
        return None


def verify_transaction_on_nodes(tx_id):
    if not tx_id:
        print("Nessun ID transazione fornito per la verifica")
        return

    print(f"\nVerifica transazione {tx_id} su tutti i nodi:")

    for node_url in nodes:
        try:
            bdb = BigchainDB(node_url)
            tx = bdb.transactions.retrieve(tx_id)
            node_number = nodes.index(node_url)
            print(f"Nodo {node_number}: Transazione trovata ✓")
            print(f"Dettagli transazione sul nodo {node_number}:")
            print(json.dumps(tx, indent=2))

        except Exception as e:
            print(f"Nodo {node_number}: Errore nel recupero della transazione")
            print(f"Errore: {str(e)}")


def main():
    print("Verifica dello stato dei nodi...")
    all_nodes_ok = all(check_node_status(node) for node in nodes)

    if not all_nodes_ok:
        print("Alcuni nodi non sono raggiungibili. Verifica la configurazione.")
        return

    print("\nTutti i nodi sono operativi. Procedo con la creazione della transazione...")

    # Crea transazione sul primo nodo
    tx_id = create_and_send_transaction(nodes[0])

    if tx_id:
        print(f"\nTransazione creata con successo!")
        print(f"ID Transazione: {tx_id}")

        # Attende che la transazione sia propagata
        print("\nAttesa propagazione transazione (10 secondi)...")
        time.sleep(10)

        # Verifica la presenza della transazione su tutti i nodi
        verify_transaction_on_nodes(tx_id)
    else:
        print("\nErrore nella creazione della transazione")


if __name__ == "__main__":
    main()