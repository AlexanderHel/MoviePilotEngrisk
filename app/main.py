import multiprocessing
import os
import sys
import threading
from pathlib import Path

import uvicorn as uvicorn
from PIL import Image
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Config

from app.utils.system import SystemUtils

# 禁用输出
if SystemUtils.is_frozen():
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

from app.command import Command
from app.core.config import settings
from app.core.module import ModuleManager
from app.core.plugin import PluginManager
from app.db.init import init_db, update_db
from app.helper.display import DisplayHelper
from app.helper.sites import SitesHelper
from app.scheduler import Scheduler

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
    Starting front-end services
    """
    if not SystemUtils.is_frozen():
        return
    nginx_path = settings.ROOT_PATH / 'nginx'
    if not nginx_path.exists():
        return
    import subprocess
    if SystemUtils.is_windows():
        subprocess.Popen("start nginx.exe",
                         cwd=nginx_path,
                         shell=True)
    else:
        subprocess.Popen("nohup ./nginx &",
                         cwd=nginx_path,
                         shell=True)


def stop_frontend():
    """
    Stopping front-end services
    """
    if not SystemUtils.is_frozen():
        return
    import subprocess
    if SystemUtils.is_windows():
        subprocess.Popen(f"taskkill /f /im nginx.exe", shell=True)
    else:
        subprocess.Popen(f"killall nginx", shell=True)


def start_tray():
    """
    Launch tray icon
    """

    if not SystemUtils.is_frozen():
        return

    def open_web():
        """
        Calling the browser to open the front-end page
        """
        import webbrowser
        webbrowser.open(f"http://localhost:{settings.NGINX_PORT}")

    def quit_app():
        """
        Opt-out program
        """
        TrayIcon.stop()
        Server.should_exit = True

    import pystray

    #  Pallet icon
    TrayIcon = pystray.Icon(
        settings.PROJECT_NAME,
        icon=Image.open(settings.ROOT_PATH / 'app.ico'),
        menu=pystray.Menu(
            pystray.MenuItem(
                ' Show (a ticket)',
                open_web,
            ),
            pystray.MenuItem(
                ' Abort',
                quit_app,
            )
        )
    )
    # Launch tray icon
    threading.Thread(target=TrayIcon.run, daemon=True).start()


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
    # Stopping front-end services
    stop_frontend()


@App.on_event("startup")
def start_module():
    """
    Starter module
    """
    #  Virtualization
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
    # Starting front-end services
    start_frontend()


if __name__ == '__main__':
    #  Boot tray
    start_tray()
    #  Initializing the database
    init_db()
    #  Updating the database
    update_db()
    #  Activate (a plan)API Service
    Server.run()
