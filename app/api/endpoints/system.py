import json
import time
from datetime import datetime
from typing import Union

import tailer
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import schemas
from app.chain.search import SearchChain
from app.core.config import settings
from app.core.security import verify_token
from app.db import get_db
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.message import MessageHelper
from app.helper.progress import ProgressHelper
from app.scheduler import Scheduler
from app.schemas.types import SystemConfigKey
from app.utils.http import RequestUtils
from app.utils.system import SystemUtils
from version import APP_VERSION

router = APIRouter()


@router.get("/env", summary=" Querying system environment variables", response_model=schemas.Response)
def get_env_setting(_: schemas.TokenPayload = Depends(verify_token)):
    """
    Querying system environment variables， Include the current version number
    """
    info = settings.dict(
        exclude={"SECRET_KEY", "SUPERUSER_PASSWORD", "API_TOKEN"}
    )
    info.update({
        "VERSION": APP_VERSION
    })
    return schemas.Response(success=True,
                            data=info)


@router.get("/progress/{process_type}", summary=" Real time progress")
def get_progress(process_type: str, token: str):
    """
    Real-time access to processing progress， The return format isSSE
    """
    if not token or not verify_token(token):
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )

    progress = ProgressHelper()

    def event_generator():
        while True:
            detail = progress.get(process_type)
            yield 'data: %s\n\n' % json.dumps(detail)
            time.sleep(0.2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/setting/{key}", summary=" Query system settings", response_model=schemas.Response)
def get_setting(key: str,
                _: schemas.TokenPayload = Depends(verify_token)):
    """
    Query system settings
    """
    return schemas.Response(success=True, data={
        "value": SystemConfigOper().get(key)
    })


@router.post("/setting/{key}", summary=" Update system settings", response_model=schemas.Response)
def set_setting(key: str, value: Union[list, dict, str, int] = None,
                _: schemas.TokenPayload = Depends(verify_token)):
    """
    Update system settings
    """
    SystemConfigOper().set(key, value)
    return schemas.Response(success=True)


@router.get("/message", summary=" Real-time news")
def get_message(token: str):
    """
    Get system messages in real time， The return format isSSE
    """
    if not token or not verify_token(token):
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )

    message = MessageHelper()

    def event_generator():
        while True:
            detail = message.get()
            yield 'data: %s\n\n' % (detail or '')
            time.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/logging", summary=" Real-time logs")
def get_logging(token: str):
    """
    Real-time access to system logs， The return format isSSE
    """
    if not token or not verify_token(token):
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )

    def log_generator():
        log_path = settings.LOG_PATH / 'moviepilot.log'
        #  Read the end of the file50 Classifier for objects in rows such as words， Non-usetailer Module (in software)
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f.readlines()[-50:]:
                yield 'data: %s\n\n' % line
        while True:
            for text in tailer.follow(open(log_path, 'r', encoding='utf-8')):
                yield 'data: %s\n\n' % (text or '')
            time.sleep(1)

    return StreamingResponse(log_generator(), media_type="text/event-stream")


@router.get("/nettest", summary=" Test network connectivity")
def nettest(url: str,
            proxy: bool,
            _: schemas.TokenPayload = Depends(verify_token)):
    """
    Test network connectivity
    """
    #  Number of milliseconds since the start of the record
    start_time = datetime.now()
    url = url.replace("{TMDBAPIKEY}", settings.TMDB_API_KEY)
    result = RequestUtils(proxies=settings.PROXY if proxy else None,
                          ua=settings.USER_AGENT).get_res(url)
    #  Number of milliseconds to time out
    end_time = datetime.now()
    #  Calculate the number of relevant seconds
    if result and result.status_code == 200:
        return schemas.Response(success=True, data={
            "time": round((end_time - start_time).microseconds / 1000)
        })
    elif result:
        return schemas.Response(success=False, message=f" Error code：{result.status_code}", data={
            "time": round((end_time - start_time).microseconds / 1000)
        })
    else:
        return schemas.Response(success=False, message=" Network connection failure！")


@router.get("/versions", summary=" Consult (a document etc)Github PossessRelease Releases", response_model=schemas.Response)
def latest_version(_: schemas.TokenPayload = Depends(verify_token)):
    """
    Consult (a document etc)Github PossessRelease Releases
    """
    version_res = RequestUtils().get_res(f"https://api.github.com/repos/AlexanderHel/MoviePilotEngrisk/releases")
    if version_res:
        ver_json = version_res.json()
        if ver_json:
            return schemas.Response(success=True, data=ver_json)
    return schemas.Response(success=False)


@router.get("/ruletest", summary=" Priority rule testing", response_model=schemas.Response)
def ruletest(title: str,
             subtitle: str = None,
             ruletype: str = None,
             db: Session = Depends(get_db),
             _: schemas.TokenPayload = Depends(verify_token)):
    """
    Filter rule testing， Type of rule 1- Subscribe to，2- Typesetting，3- Look for sth.
    """
    torrent = schemas.TorrentInfo(
        title=title,
        description=subtitle,
    )
    if ruletype == "2":
        rule_string = SystemConfigOper().get(SystemConfigKey.BestVersionFilterRules)
    elif ruletype == "3":
        rule_string = SystemConfigOper().get(SystemConfigKey.SearchFilterRules)
    else:
        rule_string = SystemConfigOper().get(SystemConfigKey.SubscribeFilterRules)
    if not rule_string:
        return schemas.Response(success=False, message=" Priority rules not set！")

    #  Filtration
    result = SearchChain(db).filter_torrents(rule_string=rule_string,
                                             torrent_list=[torrent])
    if not result:
        return schemas.Response(success=False, message=" Failure to comply with priority rules！")
    return schemas.Response(success=True, data={
        "priority": 100 - result[0].pri_order + 1
    })


@router.get("/restart", summary=" Reboot", response_model=schemas.Response)
def restart_system(_: schemas.TokenPayload = Depends(verify_token)):
    """
    Reboot
    """
    if not SystemUtils.can_restart():
        return schemas.Response(success=False, message=" The current operating environment does not support reboot operations！")
    #  Perform a reboot
    ret, msg = SystemUtils.restart()
    return schemas.Response(success=ret, message=msg)


@router.get("/runscheduler", summary=" Operational services", response_model=schemas.Response)
def execute_command(jobid: str,
                    _: schemas.TokenPayload = Depends(verify_token)):
    """
    Execute a command
    """
    if not jobid:
        return schemas.Response(success=False, message=" The command cannot be empty！")
    if jobid == "subscribe_search":
        Scheduler().start(jobid, state = 'R')
    else:
        Scheduler().start(jobid)
    return schemas.Response(success=True)