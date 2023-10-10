from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.chain.webhook import WebhookChain
from app.core.config import settings
from app.db import get_db

router = APIRouter()


def start_webhook_chain(db: Session, body: Any, form: Any, args: Any):
    """
    Starting chained tasks
    """
    WebhookChain(db).message(body=body, form=form, args=args)


@router.post("/", summary="Webhook Message response", response_model=schemas.Response)
async def webhook_message(background_tasks: BackgroundTasks,
                          token: str, request: Request,
                          db: Session = Depends(get_db),) -> Any:
    """
    Webhook Responsive
    """
    if token != settings.API_TOKEN:
        return schemas.Response(success=False, message="token Failed certification")
    body = await request.body()
    form = await request.form()
    args = request.query_params
    background_tasks.add_task(start_webhook_chain, db, body, form, args)
    return schemas.Response(success=True)


@router.get("/", summary="Webhook Message response", response_model=schemas.Response)
async def webhook_message(background_tasks: BackgroundTasks,
                          token: str, request: Request,
                          db: Session = Depends(get_db)) -> Any:
    """
    Webhook Responsive
    """
    if token != settings.API_TOKEN:
        return schemas.Response(success=False, message="token Failed certification")
    args = request.query_params
    background_tasks.add_task(start_webhook_chain, db, None, None, args)
    return schemas.Response(success=True)
