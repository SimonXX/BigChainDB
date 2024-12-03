from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
import time


def test_network():
    # Connetti ai nodi
    nodes = [
        BigchainDB('http://localhost:9984'),
        BigchainDB('http://localhost:9985'),
        BigchainDB('http://localhost:9986'),
        BigchainDB('http://localhost:9987')
    ]

    print("Test di consenso BigchainDB")
    print("-" * 30)

    # Crea una transazione di test
    alice = generate_keypair()

    # Prova a creare e inviare una transazione su ogni nodo
    for i, bdb in enumerate(nodes):
        try:
            print(f"\nTest nodo {i + 1}:")

            # Crea transazione
            tx = bdb.transactions.prepare(
                operation='CREATE',
                signers=alice.public_key,
                asset={'data': {'test': f'messaggio da nodo {i + 1}'}}
            )

            # Firma transazione
            tx_signed = bdb.transactions.fulfill(
                tx,
                private_keys=alice.private_key
            )

            # Invia transazione
            resp = bdb.transactions.send_commit(tx_signed)
            tx_id = resp['id']
            print(f"Transazione creata con ID: {tx_id}")

            # Verifica propagazione
            time.sleep(2)  # Attendi la propagazione
            print("\nVerifica propagazione:")

            for j, verify_node in enumerate(nodes):
                try:
                    result = verify_node.transactions.retrieve(tx_id)
                    print(f"Nodo {j + 1}: ✓ Ha la transazione")
                except:
                    print(f"Nodo {j + 1}: ✗ Non ha la transazione")

        except Exception as e:
            print(f"Errore sul nodo {i + 1}: {e}")


if __name__ == "__main__":
    test_network()