import os
import uvicorn
import uuid
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from pythonjsonlogger import jsonlogger
import sentry_sdk
from prometheus_fastapi_instrumentator import Instrumentator

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=os.getenv("ENVIRONMENT", "development"),
    )

app = FastAPI()
Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Налаштування кастомного JSON-логера для бізнес-подій
logger = logging.getLogger("bank_logger")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

if logger.handlers:
    logger.handlers.clear()

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(message)s %(traceId)s %(service)s %(event_type)s %(step)s %(status)s %(reason)s %(error_type)s %(from_card_last4)s %(to_card_last4)s %(card_last4)s %(amount)s %(attempted_amount)s %(current_balance)s %(new_sender_balance)s %(new_receiver_balance)s'
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

os.makedirs("logs", exist_ok=True)
file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


@app.middleware("http")
async def middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id", f"tx-trace-{uuid.uuid4().hex[:8]}")
    request.state.trace_id = trace_id

    if request.url.path != "/metrics":
        logger.info("Bank API Request Received", extra={
            "traceId": trace_id,
            "service": "bank-core-api",
            "method": request.method,
            "url": str(request.url.path)
        })

    response: Response = await call_next(request)
    response.headers["x-trace-id"] = trace_id
    return response

@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0
    return division_by_zero




accounts_db = {
    "4441111122223333": {"holder": "Олексій Іванов", "balance": 1500.00, "currency": "UAH"},
    "5375414199998888": {"holder": "Марія Коваленко", "balance": 50.00, "currency": "UAH"}
}




class SendMoney(BaseModel):
    from_account: str
    to_account: str
    amount: float

class TransferAddMoneyRequest(BaseModel):
    card_number: str
    amount: float




@app.get("/")
async def health_check():
    return {"status": "ok", "message": "app is running"}


@app.get("/api/v1/cards/{card_number}/balance")
async def get_balance(card_number: str, request: Request):
    if card_number not in accounts_db:
        logger.warning(f"Card number {card_number} not found",extra = {
            "traceId": request.state.trace_id,
            "service": "bank-core-api",
            "method": request.method,
            "card_last4": card_number[-4:]
        })
        raise HTTPException(status_code=404, detail="Card number not found")

    account = accounts_db[card_number]

    logger.info(f"Account balance: {account['balance']}", extra={
        "traceId": request.state.trace_id,
        "service": "bank-core-api",
        "method": request.method,
        "card_last4": card_number[-4:]
    })

    return {
        "card": f"**** **** **** {card_number[-4:]}",
        "holder": account["holder"],
        "balance": account["balance"],
        "currency": account["currency"]
    }

@app.post("/api/v1/cards/addmoney")
async def add_money(transfer: TransferAddMoneyRequest, request: Request):
    if transfer.card_number not in accounts_db:
        logger.warning(f"Card number {transfer.card_number} not found",extra = {
            "traceId": request.state.trace_id,
            "service": "bank-core-api",
            "method": request.method,
            "card_last4": transfer.card_number[-4:]
        })
        raise HTTPException(status_code=404, detail="Card number not found")

    accounts_db[transfer.card_number]["balance"] += transfer.amount

    logger.info("Account balance: {account['balance']}", extra={
        "traceId": request.state.trace_id,
        "service": "bank-core-api",
        "method": request.method,
        "card_last4": transfer.card_number[-4:]
    })

    return {
        "status": "success",
        "card": f"**** **** **** {transfer.card_number[-4:]}",
        "holder": accounts_db[transfer.card_number]["holder"],
        "balance": accounts_db[transfer.card_number]["balance"],
    }

@app.post("/api/v1/transfer/p2p")
async def transfer(transfer: SendMoney, request: Request):
    logger.info("P2P transfer request received", extra={
        "traceId": request.state.trace_id,
        "service": "bank-core-api",
        "event_type": "p2p_transfer_received",
        "step": "1",
        "from_card_last4": transfer.from_account[-4:],
        "to_card_last4": transfer.to_account[-4:],
        "amount": transfer.amount
    })

    logger.debug("P2P transfer payload received", extra={
        "traceId": request.state.trace_id,
        "service": "bank-core-api",
        "event_type": "debug_p2p_payload",
        "from_card_last4": transfer.from_account[-4:],
        "to_card_last4": transfer.to_account[-4:],
        "amount": transfer.amount
    })

    logger.info("Sender card validation started", extra={
        "traceId": request.state.trace_id,
        "service": "card-validation-service",
        "event_type": "sender_card_validation_started",
        "step": "2",
        "from_card_last4": transfer.from_account[-4:]
    })

    if transfer.from_account not in accounts_db:
        logger.warning("Sender card validation failed", extra={
            "traceId": request.state.trace_id,
            "service": "card-validation-service",
            "event_type": "sender_card_not_found",
            "step": "2",
            "status": 404,
            "from_card_last4": transfer.from_account[-4:]
        })

        logger.warning("P2P transfer failed", extra={
            "traceId": request.state.trace_id,
            "service": "bank-core-api",
            "event_type": "p2p_transfer_failed",
            "step": "2",
            "status": 404,
            "reason": "sender_card_not_found"
        })

        raise HTTPException(status_code=404, detail="Sender card number not found")

    logger.info("Sender card validation passed", extra={
        "traceId": request.state.trace_id,
        "service": "card-validation-service",
        "event_type": "sender_card_validation_passed",
        "step": "2",
        "from_card_last4": transfer.from_account[-4:]
    })

    logger.info("Receiver card validation started", extra={
        "traceId": request.state.trace_id,
        "service": "card-validation-service",
        "event_type": "receiver_card_validation_started",
        "step": "3",
        "to_card_last4": transfer.to_account[-4:]
    })

    if transfer.to_account not in accounts_db:
        logger.warning("Receiver card validation failed", extra={
            "traceId": request.state.trace_id,
            "service": "card-validation-service",
            "event_type": "receiver_card_not_found",
            "step": "3",
            "status": 404,
            "to_card_last4": transfer.to_account[-4:]
        })

        logger.warning("P2P transfer failed", extra={
            "traceId": request.state.trace_id,
            "service": "bank-core-api",
            "event_type": "p2p_transfer_failed",
            "step": "3",
            "status": 404,
            "reason": "receiver_card_not_found"
        })

        raise HTTPException(status_code=404, detail="Receiver card number not found")

    logger.info("Receiver card validation passed", extra={
        "traceId": request.state.trace_id,
        "service": "card-validation-service",
        "event_type": "receiver_card_validation_passed",
        "step": "3",
        "to_card_last4": transfer.to_account[-4:]
    })

    sender = accounts_db[transfer.from_account]

    logger.debug("Sender account loaded from in-memory database", extra={
        "traceId": request.state.trace_id,
        "service": "bank-core-api",
        "event_type": "debug_sender_account_loaded",
        "from_card_last4": transfer.from_account[-4:],
        "current_balance": sender["balance"]
    })

    logger.info("Balance check started", extra={
        "traceId": request.state.trace_id,
        "service": "balance-service",
        "event_type": "balance_check_started",
        "step": "4",
        "from_card_last4": transfer.from_account[-4:],
        "attempted_amount": transfer.amount,
        "current_balance": sender["balance"]
    })

    if sender["balance"] < transfer.amount:
        logger.warning("Balance check failed", extra={
            "traceId": request.state.trace_id,
            "service": "balance-service",
            "event_type": "insufficient_funds",
            "step": "4",
            "status": 400,
            "from_card_last4": transfer.from_account[-4:],
            "attempted_amount": transfer.amount,
            "current_balance": sender["balance"]
        })

        logger.warning("P2P transfer failed", extra={
            "traceId": request.state.trace_id,
            "service": "bank-core-api",
            "event_type": "p2p_transfer_failed",
            "step": "4",
            "status": 400,
            "reason": "insufficient_funds"
        })

        raise HTTPException(
            status_code=400,
            detail="Not enough money to make this transfer",
        )

    logger.info("Balance check passed", extra={
        "traceId": request.state.trace_id,
        "service": "balance-service",
        "event_type": "balance_check_passed",
        "step": "4",
        "from_card_last4": transfer.from_account[-4:],
        "attempted_amount": transfer.amount,
        "current_balance": sender["balance"]
    })

    logger.debug("Transfer processor is ready to update balances", extra={
        "traceId": request.state.trace_id,
        "service": "transfer-processor",
        "event_type": "debug_transfer_processor_ready",
        "from_card_last4": transfer.from_account[-4:],
        "to_card_last4": transfer.to_account[-4:],
        "amount": transfer.amount,
        "current_balance": sender["balance"]
    })

    logger.info("Fraud check passed", extra={
        "traceId": request.state.trace_id,
        "service": "fraud-check-service",
        "event_type": "fraud_check_passed",
        "step": "5",
        "from_card_last4": transfer.from_account[-4:],
        "to_card_last4": transfer.to_account[-4:],
        "amount": transfer.amount
    })

    sender["balance"] -= transfer.amount

    logger.info("Sender account debited", extra={
        "traceId": request.state.trace_id,
        "service": "transfer-processor",
        "event_type": "sender_account_debited",
        "step": "6",
        "from_card_last4": transfer.from_account[-4:],
        "amount": transfer.amount,
        "new_sender_balance": sender["balance"]
    })

    accounts_db[transfer.to_account]["balance"] += transfer.amount

    logger.info("Receiver account credited", extra={
        "traceId": request.state.trace_id,
        "service": "transfer-processor",
        "event_type": "receiver_account_credited",
        "step": "7",
        "to_card_last4": transfer.to_account[-4:],
        "amount": transfer.amount,
        "new_receiver_balance": accounts_db[transfer.to_account]["balance"]
    })

    logger.info("P2P transfer completed successfully", extra={
        "traceId": request.state.trace_id,
        "service": "bank-core-api",
        "event_type": "p2p_transfer_completed",
        "step": "8",
        "status": 200,
        "from_card_last4": transfer.from_account[-4:],
        "to_card_last4": transfer.to_account[-4:],
        "amount": transfer.amount
    })

    return {
        "status": "success",
        "amount": transfer.amount,
        "balance": sender["balance"]
    }

@app.post("/api/v1/transfer/crash")
async def crash(request: Request):
    logger.info("SWIFT transfer request received", extra={
        "traceId": request.state.trace_id,
        "service": "bank-core-api",
        "event_type": "swift_transfer_received",
        "step": "1"
    })

    logger.debug("SWIFT transfer debug context prepared", extra={
        "traceId": request.state.trace_id,
        "service": "bank-core-api",
        "event_type": "debug_swift_context",
        "gateway": "SWIFT",
        "operation": "external_transfer"
    })

    logger.info("Customer card validation passed", extra={
        "traceId": request.state.trace_id,
        "service": "card-validation-service",
        "event_type": "card_validation_passed",
        "step": "2"
    })

    logger.info("Account balance check passed", extra={
        "traceId": request.state.trace_id,
        "service": "balance-service",
        "event_type": "balance_check_passed",
        "step": "3"
    })

    logger.info("Fraud check passed", extra={
        "traceId": request.state.trace_id,
        "service": "fraud-check-service",
        "event_type": "fraud_check_passed",
        "step": "4"
    })

    logger.info("External SWIFT gateway request started", extra={
        "traceId": request.state.trace_id,
        "service": "swift-gateway",
        "event_type": "gateway_request_started",
        "step": "5"
    })

    logger.debug("Preparing simulated SWIFT gateway request", extra={
        "traceId": request.state.trace_id,
        "service": "swift-gateway",
        "event_type": "debug_swift_gateway_payload",
        "gateway": "SWIFT",
        "timeout_ms": 3000
    })

    try:
        db_connection = None
        db_connection.execute("SELECT * FROM users")
    except Exception as e:
        logger.error("External SWIFT gateway timeout", extra={
            "traceId": request.state.trace_id,
            "service": "swift-gateway",
            "event_type": "gateway_timeout",
            "step": "6",
            "error_type": type(e).__name__
        })

        logger.debug("Captured exception details before sending to Sentry", extra={
            "traceId": request.state.trace_id,
            "service": "swift-gateway",
            "event_type": "debug_exception_captured",
            "error_type": type(e).__name__
        })

        try:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("trace_id", request.state.trace_id)
                scope.set_tag("failed_service", "swift-gateway")
                scope.set_tag("event_type", "gateway_timeout")
                sentry_sdk.capture_exception(e)
        except Exception as sentry_err:
            logger.warning("Failed to send exception to Sentry", extra={
                "traceId": request.state.trace_id,
                "service": "bank-core-api",
                "event_type": "sentry_capture_failed",
                "error_type": type(sentry_err).__name__
            })

        logger.error("SWIFT transfer failed", extra={
            "traceId": request.state.trace_id,
            "service": "bank-core-api",
            "event_type": "swift_transfer_failed",
            "step": "7",
            "status": 500
        })

        raise HTTPException(
            status_code=500,
            detail=f"Payment Gateway Timeout/Crash. TraceID: {request.state.trace_id}"
        )



















if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, access_log=True)

