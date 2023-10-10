from typing import Union, Any, List

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi import Request
from sqlalchemy.orm import Session
from starlette.responses import PlainTextResponse

from app import schemas
from app.chain.message import MessageChain
from app.core.config import settings
from app.core.security import verify_token
from app.db import get_db
from app.db.systemconfig_oper import SystemConfigOper
from app.log import logger
from app.modules.wechat.WXBizMsgCrypt3 import WXBizMsgCrypt
from app.schemas import NotificationSwitch
from app.schemas.types import SystemConfigKey, NotificationType

router = APIRouter()


def start_message_chain(db: Session, body: Any, form: Any, args: Any):
    """
    Starting chained tasks
    """
    MessageChain(db).process(body=body, form=form, args=args)


@router.post("/", summary=" Receive user messages", response_model=schemas.Response)
async def user_message(background_tasks: BackgroundTasks, request: Request,
                       db: Session = Depends(get_db)):
    """
    User message response
    """
    body = await request.body()
    form = await request.form()
    args = request.query_params
    background_tasks.add_task(start_message_chain, db, body, form, args)
    return schemas.Response(success=True)


@router.get("/", summary=" Wechat verification")
def wechat_verify(echostr: str, msg_signature: str,
                  timestamp: Union[str, int], nonce: str) -> Any:
    """
    User message response
    """
    logger.info(f" Received wechat authentication request: {echostr}")
    try:
        wxcpt = WXBizMsgCrypt(sToken=settings.WECHAT_TOKEN,
                              sEncodingAESKey=settings.WECHAT_ENCODING_AESKEY,
                              sReceiveId=settings.WECHAT_CORPID)
    except Exception as err:
        logger.error(f" Wechat request verification failed: {err}")
        return str(err)
    ret, sEchoStr = wxcpt.VerifyURL(sMsgSignature=msg_signature,
                                    sTimeStamp=timestamp,
                                    sNonce=nonce,
                                    sEchoStr=echostr)
    if ret != 0:
        logger.error(" Wechat request verification failed VerifyURL ret: %s" % str(ret))
    #  Validate (a theory)URL Successes， Commander-in-chief (military)sEchoStr Return to enterprise
    return PlainTextResponse(sEchoStr)


@router.get("/switchs", summary=" Query notification message channel switch", response_model=List[NotificationSwitch])
def read_switchs(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query notification message channel switch
    """
    return_list = []
    #  Read database
    switchs = SystemConfigOper().get(SystemConfigKey.NotificationChannels)
    if not switchs:
        for noti in NotificationType:
            return_list.append(NotificationSwitch(mtype=noti.value, wechat=True,
                                                  telegram=True, slack=True,
                                                  synologychat=True))
    else:
        for switch in switchs:
            return_list.append(NotificationSwitch(**switch))
    return return_list


@router.post("/switchs", summary=" Setting the notification message channel switch", response_model=schemas.Response)
def set_switchs(switchs: List[NotificationSwitch],
                _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query notification message channel switch
    """
    switch_list = []
    for switch in switchs:
        switch_list.append(switch.dict())
    #  Deposit
    SystemConfigOper().set(SystemConfigKey.NotificationChannels, switch_list)

    return schemas.Response(success=True)
