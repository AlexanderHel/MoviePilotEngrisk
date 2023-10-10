import datetime
import os
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import List, Union, Tuple

import docker
import psutil
from app import schemas


class SystemUtils:

    @staticmethod
    def execute(cmd: str) -> str:
        """
        Execute a command， Getting the return result
        """
        try:
            with os.popen(cmd) as p:
                return p.readline().strip()
        except Exception as err:
            print(str(err))
            return ""

    @staticmethod
    def is_docker() -> bool:
        """
        Determine if theDocker Matrix
        """
        return Path("/.dockerenv").exists()

    @staticmethod
    def is_synology() -> bool:
        """
        Determining if it is a group sunshine system
        """
        if SystemUtils.is_windows():
            return False
        return True if "synology" in SystemUtils.execute('uname -a') else False

    @staticmethod
    def is_windows() -> bool:
        """
        Determine if theWindows Systems
        """
        return True if os.name == "nt" else False

    @staticmethod
    def is_frozen() -> bool:
        """
        Determine if a binary file is frozen
        """
        return True if getattr(sys, 'frozen', False) else False

    @staticmethod
    def is_macos() -> bool:
        """
        Determine if theMacOS Systems
        """
        return True if platform.system() == 'Darwin' else False

    @staticmethod
    def copy(src: Path, dest: Path) -> Tuple[int, str]:
        """
        Make a copy of
        """
        try:
            shutil.copy2(src, dest)
            return 0, ""
        except Exception as err:
            print(str(err))
            return -1, str(err)

    @staticmethod
    def move(src: Path, dest: Path) -> Tuple[int, str]:
        """
        Mobility
        """
        try:
            #  Rename the current directory
            temp = src.replace(src.parent / dest.name)
            # Mobility到目标目录
            shutil.move(temp, dest)
            return 0, ""
        except Exception as err:
            print(str(err))
            return -1, str(err)

    @staticmethod
    def link(src: Path, dest: Path) -> Tuple[int, str]:
        """
        Hard link
        """
        try:
            # link To the current directory and rename it
            tmp_path = src.parent / (dest.name + ".mp")
            tmp_path.hardlink_to(src)
            # Mobility到目标目录
            shutil.move(tmp_path, dest)
            return 0, ""
        except Exception as err:
            print(str(err))
            return -1, str(err)

    @staticmethod
    def softlink(src: Path, dest: Path) -> Tuple[int, str]:
        """
        Soft link (computing)
        """
        try:
            dest.symlink_to(src)
            return 0, ""
        except Exception as err:
            print(str(err))
            return -1, str(err)

    @staticmethod
    def list_files(directory: Path, extensions: list, min_filesize: int = 0) -> List[Path]:
        """
        Get all files with the specified extension in the directory（ Including subdirectories）
        """

        if not min_filesize:
            min_filesize = 0

        if not directory.exists():
            return []

        if directory.is_file():
            return [directory]

        if not min_filesize:
            min_filesize = 0

        files = []
        pattern = r".*(" + "|".join(extensions) + ")$"

        #  Iterate through directories and subdirectories
        for path in directory.rglob('**/*'):
            if path.is_file() \
                    and re.match(pattern, path.name, re.IGNORECASE) \
                    and path.stat().st_size >= min_filesize * 1024 * 1024:
                files.append(path)

        return files

    @staticmethod
    def exits_files(directory: Path, extensions: list, min_filesize: int = 0) -> bool:
        """
        Determines whether a file with the specified extension exists in the directory
        :return True Remain False Non-existent
        """

        if not min_filesize:
            min_filesize = 0

        if not directory.exists():
            return False

        if directory.is_file():
            return True

        if not min_filesize:
            min_filesize = 0

        pattern = r".*(" + "|".join(extensions) + ")$"

        #  Iterate through directories and subdirectories
        for path in directory.rglob('**/*'):
            if path.is_file() \
                    and re.match(pattern, path.name, re.IGNORECASE) \
                    and path.stat().st_size >= min_filesize * 1024 * 1024:
                return True

        return False

    @staticmethod
    def list_sub_files(directory: Path, extensions: list) -> List[Path]:
        """
        List all files with the specified extension in the current directory( Excluding subdirectories)
        """
        if not directory.exists():
            return []

        if directory.is_file():
            return [directory]

        files = []
        pattern = r".*(" + "|".join(extensions) + ")$"

        #  Iterate through the catalog
        for path in directory.iterdir():
            if path.is_file() and re.match(pattern, path.name, re.IGNORECASE):
                files.append(path)

        return files

    @staticmethod
    def list_sub_directory(directory: Path) -> List[Path]:
        """
        List all subdirectories in the current directory（ Non-recursive）
        """
        if not directory.exists():
            return []

        if directory.is_file():
            return []

        dirs = []

        #  Iterate through the catalog
        for path in directory.iterdir():
            if path.is_dir():
                dirs.append(path)

        return dirs

    @staticmethod
    def get_directory_size(path: Path) -> float:
        """
        Calculating the size of a catalog

        Parameters:
            directory_path (Path):  Directory path

        Come (or go) back:
            int:  Catalog size（ Byte-based）
        """
        if not path or not path.exists():
            return 0
        if path.is_file():
            return path.stat().st_size
        total_size = 0
        for path in path.glob('**/*'):
            if path.is_file():
                total_size += path.stat().st_size

        return total_size

    @staticmethod
    def space_usage(dir_list: Union[Path, List[Path]]) -> Tuple[float, float]:
        """
        Calculate total free space for multiple directories/ Headroom（ Work unit (one's workplace)：Byte）， And remove duplicate disks
        """
        if not dir_list:
            return 0.0, 0.0
        if not isinstance(dir_list, list):
            dir_list = [dir_list]
        #  Storing non-repeatable disks
        disk_set = set()
        #  Total remaining storage space
        total_free_space = 0.0
        #  Total storage space
        total_space = 0.0
        for dir_path in dir_list:
            if not dir_path:
                continue
            if not dir_path.exists():
                continue
            #  Get the disk where the directory is located
            if os.name == "nt":
                disk = dir_path.drive
            else:
                disk = os.stat(dir_path).st_dev
            #  If the disk has not been， Then its remaining space is calculated and added to the total remaining space
            if disk not in disk_set:
                disk_set.add(disk)
                total_space += SystemUtils.total_space(dir_path)
                total_free_space += SystemUtils.free_space(dir_path)
        return total_space, total_free_space

    @staticmethod
    def free_space(path: Path) -> float:
        """
        Get the remaining space of the specified path（ Work unit (one's workplace)：Byte）
        """
        if not os.path.exists(path):
            return 0.0
        return psutil.disk_usage(str(path)).free

    @staticmethod
    def total_space(path: Path) -> float:
        """
        Get the total space of the specified path（ Work unit (one's workplace)：Byte）
        """
        if not os.path.exists(path):
            return 0.0
        return psutil.disk_usage(str(path)).total

    @staticmethod
    def processes() -> List[schemas.ProcessInfo]:
        """
        Get all processes
        """
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'create_time', 'memory_info', 'status']):
            try:
                if proc.status() != psutil.STATUS_ZOMBIE:
                    runtime = datetime.datetime.now() - datetime.datetime.fromtimestamp(
                        int(getattr(proc, 'create_time', 0)()))
                    mem_info = getattr(proc, 'memory_info', None)()
                    if mem_info is not None:
                        mem_mb = round(mem_info.rss / (1024 * 1024), 1)
                        processes.append(schemas.ProcessInfo(
                            pid=proc.pid, name=proc.name(), run_time=runtime.seconds, memory=mem_mb
                        ))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return processes

    @staticmethod
    def is_bluray_dir(dir_path: Path) -> bool:
        """
        Determining if a blu-ray disc is an original catalog
        """
        #  Essential files or folders for blu-ray disc original directory
        required_files = ['BDMV', 'CERTIFICATE']
        #  Check if the required file or folder exists in the directory
        for item in required_files:
            if (dir_path / item).exists():
                return True
        return False

    @staticmethod
    def get_windows_drives():
        """
        GainWindows All disk drives
        """
        vols = []
        for i in range(65, 91):
            vol = chr(i) + ':'
            if os.path.isdir(vol):
                vols.append(vol)
        return vols

    @staticmethod
    def cpu_usage():
        """
        GainCPU Utilization rate
        """
        return psutil.cpu_percent()

    @staticmethod
    def memory_usage() -> List[int]:
        """
        Getting memory usage and utilization
        """
        return [psutil.virtual_memory().used, int(psutil.virtual_memory().percent)]

    @staticmethod
    def can_restart() -> bool:
        """
        Determine if an internal reboot is possible
        """
        return Path("/var/run/docker.sock").exists()

    @staticmethod
    def restart() -> Tuple[bool, str]:
        """
        FulfillmentDocker Reboot operation
        """
        try:
            #  Establish Docker  Client (computing)
            client = docker.DockerClient(base_url='tcp://127.0.0.1:38379')
            #  Get the current container's ID
            container_id = None
            with open('/proc/self/mountinfo', 'r') as f:
                data = f.read()
                index_resolv_conf = data.find("resolv.conf")
                if index_resolv_conf != -1:
                    index_second_slash = data.rfind("/", 0, index_resolv_conf)
                    index_first_slash = data.rfind("/", 0, index_second_slash) + 1
                    container_id = data[index_first_slash:index_second_slash]
                    if len(container_id) < 20:
                        index_resolv_conf = data.find("/sys/fs/cgroup/devices")
                        if index_resolv_conf != -1:
                            index_second_slash = data.rfind(" ", 0, index_resolv_conf)
                            index_first_slash = data.rfind("/", 0, index_second_slash) + 1
                            container_id = data[index_first_slash:index_second_slash]
            if not container_id:
                return False, " Getting the containerID Fail (e.g. experiments)！"
            #  Restart the current container
            client.containers.get(container_id.strip()).restart()
            return True, ""
        except Exception as err:
            print(str(err))
            return False, f" An error occurred while rebooting：{str(err)}"
