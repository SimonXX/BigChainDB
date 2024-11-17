Running BigchainDB Docker Image
To pull the BigchainDB Docker image:

bash
Copia codice
docker pull bigchaindb/bigchaindb:all-in-one
Running BigchainDB in a Docker Container
To run BigchainDB with all necessary services in detached mode, use the following command:

bash
Copia codice
docker run \
  --detach \
  --name bigchaindb \
  --publish 9984:9984 \
  --publish 9985:9985 \
  --publish 27017:27017 \
  --publish 26657:26657 \
  --volume $HOME/bigchaindb_docker/mongodb/data/db:/data/db \
  --volume $HOME/bigchaindb_docker/mongodb/data/configdb:/data/configdb \
  --volume $HOME/bigchaindb_docker/tendermint:/tendermint \
  bigchaindb/bigchaindb:all-in-one
Checking BigchainDB Status
To check if the BigchainDB container is running:

bash
Copia codice
docker ps | grep bigchaindb
Running the Application
To execute main.py using Uvicorn, run:

bash
Copia codice
uvicorn src.main:app --reload
