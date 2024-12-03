# Create a node
from src.Node import Node

urlBigchainDBServer="http://localhost:9984"
urlTendermintNod1 = "http://localhost:26657"
node = Node(urlBigchainDBServer, urlTendermintNod1)




def create_certificate():
    # Create certificate
    cert = node.create_certificate(
        holder_name="John",
        surname="Doe",
        competence="Python",
        identifier="12345"
    )
    # Verify certificate
    verification = node.verify_certificate(cert['id'])

def main():
    node.print_ledger()
    node.print_ledger()

    print(node.verify_certificate('3cc13fc920ddb165e2483195e37500d50183194c56d7cd9052648fd33e9cf923'))


main()



