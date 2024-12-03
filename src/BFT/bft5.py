from pymongo import MongoClient

# Assuming you're running the MongoDB instance on the Docker network (bigchaindb1 is the alias)
client = MongoClient('mongodb://localhost:27017')

# Access the BigchainDB database
db = client['bigchain']

# Access the transactions collection
transactions_collection = db['blocks']

# Query for all transactions
transactions = transactions_collection.find()

# Iterate through the transactions and print them
for tx in transactions:
    print(tx)
