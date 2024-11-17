from typing import Optional

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