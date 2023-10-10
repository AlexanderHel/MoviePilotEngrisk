import shutil
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter, Depends
from starlette.responses import FileResponse, Response

from app import schemas
from app.core.config import settings
from app.core.security import verify_token
from app.log import logger
from app.utils.system import SystemUtils

router = APIRouter()

IMAGE_TYPES = [".jpg", ".png", ".gif", ".bmp", ".jpeg", ".webp"]


@router.get("/list", summary=" All directories and files", response_model=List[schemas.FileItem])
def list_path(path: str,
              sort: str = 'time',
              _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query all directories and files in the current directory
    :param path:  Directory path
    :param sort:  Sort by，name: Sort by name，time: Sort by modification time
    :param _: token
    :return:  All directories and files
    """
    #  Return results
    ret_items = []
    if not path or path == "/":
        if SystemUtils.is_windows():
            partitions = SystemUtils.get_windows_drives() or ["C:/"]
            for partition in partitions:
                ret_items.append(schemas.FileItem(
                    type="dir",
                    path=partition + "/",
                    name=partition,
                    basename=partition
                ))
            return ret_items
        else:
            path = "/"
    else:
        if not SystemUtils.is_windows() and not path.startswith("/"):
            path = "/" + path

    #  Iterate through the catalog
    path_obj = Path(path)
    if not path_obj.exists():
        logger.error(f" Catalog does not exist：{path}")
        return []

    #  If the file
    if path_obj.is_file():
        ret_items.append(schemas.FileItem(
            type="file",
            path=str(path_obj).replace("\\", "/"),
            name=path_obj.name,
            basename=path_obj.stem,
            extension=path_obj.suffix[1:],
            size=path_obj.stat().st_size,
            modify_time=path_obj.stat().st_mtime,
        ))
        return ret_items

    #  Flat calendar all catalogs
    for item in SystemUtils.list_sub_directory(path_obj):
        ret_items.append(schemas.FileItem(
            type="dir",
            path=str(item).replace("\\", "/") + "/",
            name=item.name,
            basename=item.stem,
            modify_time=item.stat().st_mtime,
        ))

    #  Iterate through all files， No subdirectories
    for item in SystemUtils.list_sub_files(path_obj,
                                           settings.RMT_MEDIAEXT
                                           + settings.RMT_SUBEXT
                                           + IMAGE_TYPES
                                           + [".nfo"]):
        ret_items.append(schemas.FileItem(
            type="file",
            path=str(item).replace("\\", "/"),
            name=item.name,
            basename=item.stem,
            extension=item.suffix[1:],
            size=item.stat().st_size,
            modify_time=item.stat().st_mtime,
        ))
    #  Arrange in order
    if sort == 'time':
        ret_items.sort(key=lambda x: x.modify_time, reverse=True)
    else:
        ret_items.sort(key=lambda x: x.name, reverse=False)
    return ret_items


@router.get("/mkdir", summary=" Create a catalog", response_model=schemas.Response)
def mkdir(path: str, _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Create a catalog
    """
    if not path:
        return schemas.Response(success=False)
    path_obj = Path(path)
    if path_obj.exists():
        return schemas.Response(success=False)
    path_obj.mkdir(parents=True, exist_ok=True)
    return schemas.Response(success=True)


@router.get("/delete", summary=" Delete a file or directory", response_model=schemas.Response)
def delete(path: str, _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Delete a file or directory
    """
    if not path:
        return schemas.Response(success=False)
    path_obj = Path(path)
    if not path_obj.exists():
        return schemas.Response(success=True)
    if path_obj.is_file():
        path_obj.unlink()
    else:
        shutil.rmtree(path_obj, ignore_errors=True)
    return schemas.Response(success=True)


@router.get("/download", summary=" Download a file or directory")
def download(path: str, token: str) -> Any:
    """
    Download a file or directory
    """
    if not path:
        return schemas.Response(success=False)
    #  Accreditationtoken
    if not verify_token(token):
        return None
    path_obj = Path(path)
    if not path_obj.exists():
        return schemas.Response(success=False)
    if path_obj.is_file():
        #  Streaming download as a file
        return FileResponse(path_obj)
    else:
        #  Download as a zip file
        shutil.make_archive(base_name=path_obj.stem, format="zip", root_dir=path_obj)
        reponse = Response(content=path_obj.read_bytes(), media_type="application/zip")
        #  Delete zip
        Path(f"{path_obj.stem}.zip").unlink()
        return reponse


@router.get("/rename", summary=" Rename a file or directory", response_model=schemas.Response)
def rename(path: str, new_name: str, _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Rename a file or directory
    """
    if not path or not new_name:
        return schemas.Response(success=False)
    path_obj = Path(path)
    if not path_obj.exists():
        return schemas.Response(success=False)
    path_obj.rename(path_obj.parent / new_name)
    return schemas.Response(success=True)


@router.get("/image", summary=" Read image")
def image(path: str, token: str) -> Any:
    """
    Read image
    """
    if not path:
        return None
    #  Accreditationtoken
    if not verify_token(token):
        return None
    path_obj = Path(path)
    if not path_obj.exists():
        return None
    if not path_obj.is_file():
        return None
    #  Determine if an image file
    if path_obj.suffix.lower() not in IMAGE_TYPES:
        return None
    return Response(content=path_obj.read_bytes(), media_type="image/jpeg")
