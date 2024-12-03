# backend/app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.Node import Node

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

nodes = {}

class CertificateCreate(BaseModel):
    holder_name: str
    surname: str
    competence: str
    identifier: str

def get_node(node_id: int):
    if node_id not in nodes:
        ports = {
            1: ("9984", "26657"),
            2: ("9986", "26658"),
            3: ("9988", "26659"),
            4: ("9990", "26660")
        }
        bdb_port, tm_port = ports[node_id]
        nodes[node_id] = Node(
            f"http://localhost:{bdb_port}",
            f"http://localhost:{tm_port}"
        )
    return nodes[node_id]

@app.post("/node/{node_id}/certificate")
def create_certificate(node_id: int, cert: CertificateCreate):
    node = get_node(node_id)
    result = node.create_certificate(
        cert.holder_name,
        cert.surname,
        cert.competence,
        cert.identifier
    )
    return {"message": "Certificate created", "transaction_id": result['id']}

@app.get("/node/{node_id}/certificate/{tx_id}")
def verify_certificate(node_id: int, tx_id: str):
    return get_node(node_id).verify_certificate(tx_id)

@app.delete("/node/{node_id}/certificate/{tx_id}")
def revoke_certificate(node_id: int, tx_id: str):
    try:
        result = get_node(node_id).revoke_certificate(tx_id)
        return {
            "message": "Certificate revoked",
            "transaction_id": result['id']
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/node/{node_id}/ledger")
def get_ledger(node_id: int):
    try:
        transactions = get_node(node_id).print_ledger()
        return {
            "message": "Ledger retrieved successfully",
            "transactions": transactions,
            "count": len(transactions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/node/{node_id}/certificate/{tx_id}/renew")
def renew_certificate(node_id: int, tx_id: str, valid_months: int = 12):
    try:
        result = get_node(node_id).renew_certificate(tx_id, valid_months)
        return {
            "message": "Certificate renewed",
            "transaction_id": result['id'],
            "expiry_date": result['metadata']['expiry_date']
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))