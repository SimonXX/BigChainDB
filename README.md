### Running BigchainDB Docker Image

#### To pull the BigchainDB Docker image:

```bash
docker pull bigchaindb/bigchaindb:all-in-one
```

#### Running BigchainDB in a Docker Container
```
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
```


#### Verify Running Container
```
docker ps | grep bigchaindb
```

#### Execute main.py file
```
uvicorn src.main:app --reload
```
