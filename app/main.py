import multiprocessing
from pathlib import Path

import uvicorn as uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Config

from app.command import Command
from app.core.config import settings
from app.core.module import ModuleManager
from app.core.plugin import PluginManager
from app.db.init import init_db, update_db
from app.helper.display import DisplayHelper
from app.helper.sites import SitesHelper
from app.scheduler import Scheduler
from app.utils.system import SystemUtils

# App
App = FastAPI(title=settings.PROJECT_NAME,
              openapi_url=f"{settings.API_V1_STR}/openapi.json")

#  Cross-domain
App.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# uvicorn Service
Server = uvicorn.Server(Config(App, host=settings.HOST, port=settings.PORT,
                               reload=settings.DEV, workers=multiprocessing.cpu_count()))


def init_routers():
    """
    Initializing routes
    """
    from app.api.apiv1 import api_router
    from app.api.servarr import arr_router
    # API Routing (in computer networks)
    App.include_router(api_router, prefix=settings.API_V1_STR)
    # Radarr、Sonarr Routing (in computer networks)
    App.include_router(arr_router, prefix="/api/v3")


def start_frontend():
    """
    启动前端服务
    """
    if not SystemUtils.is_frozen():
        return
    if SystemUtils.is_windows():
        nginx_path = settings.ROOT_PATH / 'nginx' / 'nginx.exe'
    else:
        nginx_path = settings.ROOT_PATH / 'nginx' / 'nginx'
    if Path(nginx_path).exists():
        import subprocess
        subprocess.Popen(f"start {nginx_path}", shell=True)


def stop_frontend():
    """
    停止前端服务
    """
    if not SystemUtils.is_frozen():
        return
    import subprocess
    if SystemUtils.is_windows():
        subprocess.Popen(f"taskkill /f /im nginx.exe", shell=True)
    else:
        subprocess.Popen(f"killall nginx", shell=True)


@App.on_event("shutdown")
def shutdown_server():
    """
    Service shutdown
    """
    #  Stop module
    ModuleManager().stop()
    #  Stop plugins
    PluginManager().stop()
    #  Stop event consumption
    Command().stop()
    #  Stop virtual display
    DisplayHelper().stop()
    #  Stop timing service
    Scheduler().stop()
    # 停止前端服务
    stop_frontend()


@App.on_event("startup")
def start_module():
    """
    Starter module
    """
    # 虚拟显示
    DisplayHelper()
    #  Site management
    SitesHelper()
    #  Load modules
    ModuleManager()
    #  Loading plug-ins
    PluginManager()
    #  Start timing service
    Scheduler()
    #  Initiate event consumption
    Command()
    # Initializing routes
    init_routers()
    # 启动前端服务
    start_frontend()


if __name__ == '__main__':
    #  Initializing the database
    init_db()
    #  Updating the database
    update_db()
    #  Starting services
    Server.run()
