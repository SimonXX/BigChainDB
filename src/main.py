from typing import Optional, Dict
from venv import logger

from fastapi import FastAPI, HTTPException
from src.adapters.certificate import CertificateAdapter
from pydantic import BaseModel, constr

app = FastAPI()
certificate_adapter = CertificateAdapter()


class CertificateCreate(BaseModel):
    holder_name: str
    surname: str
    competence: str
    identifier: constr(min_length=5)
    valid_months: Optional[int] = 12

    class Config:
        schema_extra = {
            "example": {
                "holder_name": "John",
                "surname": "Doe",
                "competence": "Python Programming",
                "identifier": "123-45-6789",
                "valid_months": 12
            }
        }


class CertificateRenewal(BaseModel):
    new_valid_months: int = 12


@app.post("/certificates/")
async def create_certificate(certificate: CertificateCreate):
    """Create a new certificate"""
    try:
        prepared_data = certificate_adapter.prepare_asset_creation(
            holder_name=certificate.holder_name,
            surname=certificate.surname,
            competence=certificate.competence,
            identifier=certificate.identifier,
            valid_months=certificate.valid_months
        )

        transaction = certificate_adapter.create_certificate(prepared_data)

        return {
            "message": "Certificate created successfully",
            "transaction_id": transaction['id'],
            "holder": {
                "name": certificate.holder_name,
                "surname": certificate.surname,
                "identifier": certificate.identifier
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/certificates/{tx_id}")
async def get_certificate(tx_id: str):
    """Get certificate details and verify its validity"""
    try:
        verification = certificate_adapter.verify_certificate(tx_id)
        if 'error' in verification:
            raise HTTPException(status_code=400, detail=verification['error'])
        return verification
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/certificates/{tx_id}/revoke")
async def revoke_certificate(tx_id: str):
    """Revoke a certificate"""
    try:
        # First verify the current state
        verification = certificate_adapter.verify_certificate(tx_id)
        if not verification['valid']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot revoke certificate: {verification['reason']}"
            )

        # Proceed with revocation
        transaction = certificate_adapter.revoke_certificate(tx_id)
        return {
            "message": "Certificate revoked successfully",
            "transaction_id": transaction['id'],
            "status": "revoked",
            "revocation_date": transaction['metadata']['revocation_date']
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/certificates/{tx_id}/renew")
async def renew_certificate(tx_id: str, renewal: CertificateRenewal):
    """Renew a certificate"""
    try:
        # First verify the current state
        verification = certificate_adapter.verify_certificate(tx_id)
        if not verification['valid']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot renew certificate: {verification['reason']}"
            )

        # Proceed with renewal
        transaction = certificate_adapter.renew_certificate(
            tx_id,
            renewal.new_valid_months
        )
        return {
            "message": "Certificate renewed successfully",
            "transaction_id": transaction['id'],
            "new_expiry_date": transaction['metadata']['expiry_date']
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/nodes/communication")
async def verify_nodes_communication() -> Dict:
    """
    Verify communication between primary and secondary nodes with detailed error reporting
    """
    try:

        # First verify individual node connectivity
        if not certificate_adapter.check_node_connection():
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "One or both nodes are not running",
                    "error": "Node connectivity check failed"
                }
            )
        print('Nodes are running')

        # Test communication
        result = certificate_adapter.verify_node_communication()

        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Node communication failed",
                    "error": result['error'],
                    "primary_status": result['primary_node_status'],
                    "secondary_status": result['secondary_node_status']
                }
            )

        return {
            "status": "success",
            "message": "Nodes are communicating successfully",
            "details": {
                "primary_node": {
                    "status": result['primary_node_status'],
                    "url": 'http://localhost:9984'
                },
                "secondary_node": {
                    "status": result['secondary_node_status'],
                    "url": 'http://localhost:9986'
                },
                "test_transaction": {
                    "id": result.get('transaction_id'),
                    "verification": result.get('verification_details')
                }
            }
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Unexpected error during node communication verification",
                "error": str(e)
            }
        )