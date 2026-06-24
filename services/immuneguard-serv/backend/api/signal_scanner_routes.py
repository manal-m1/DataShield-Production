import io
import os

import pandas as pd
import requests as req
from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.models.schemas import SignalScanResponse
from core.signal_scanner.scanner import SignalScannerService


router = APIRouter(prefix="/scan-signals", tags=["Signal Scanner"])
signal_scanner_service: SignalScannerService | None = None


def get_signal_scanner_service() -> SignalScannerService:
    global signal_scanner_service
    if signal_scanner_service is None:
        initialize_signal_scanner_service()
    return signal_scanner_service


def initialize_signal_scanner_service() -> None:
    global signal_scanner_service
    reference_override = os.getenv("SIGNAL_REFERENCE_PATH")
    signal_scanner_service = (
        SignalScannerService.from_path(reference_override)
        if reference_override
        else SignalScannerService.load_default()
    )


def _scan_dataframe(dataframe: pd.DataFrame) -> dict:
    if dataframe.empty:
        raise HTTPException(400, "Uploaded dataset is empty.")

    try:
        service = get_signal_scanner_service()
    except FileNotFoundError as exc:
        raise HTTPException(500, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Unable to initialize signal scanner reference: {exc}") from exc

    return service.scan_dataframe(dataframe)


@router.post("", response_model=SignalScanResponse)
async def scan_signals(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "A CSV file is required.")

    try:
        content = await file.read()
        dataframe = pd.read_csv(io.BytesIO(content), sep=None, engine="python")
    except Exception as exc:
        raise HTTPException(400, f"Unable to parse uploaded CSV: {exc}") from exc

    return _scan_dataframe(dataframe)


@router.post("/{dataset_id}", response_model=SignalScanResponse)
async def scan_signals_by_dataset_id(dataset_id: str):
    try:
        cleaning_url = os.getenv("CLEANING_SERVICE_URL", "http://localhost:8004")
        response = req.get(f"{cleaning_url}/dataset/{dataset_id}/json", timeout=20)
        if response.status_code != 200:
            raise HTTPException(
                404,
                f"Dataset {dataset_id} not found in cleaning-service (status={response.status_code})",
            )
        payload = response.json()
        dataframe = pd.DataFrame(payload.get("data", []))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Unable to fetch dataset from cleaning-service: {exc}") from exc

    return _scan_dataframe(dataframe)
