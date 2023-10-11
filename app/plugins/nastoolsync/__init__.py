import json
import os
import sqlite3
from datetime import datetime

from app.core.config import settings
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.plugindata_oper import PluginDataOper
from app.db.transferhistory_oper import TransferHistoryOper
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple
from app.log import logger


class NAStoolSync(_PluginBase):
    #  Plug-in name
    plugin_name = " History synchronization"
    #  Plugin description
    plugin_desc = " SynchronizationNAStool Historical record、 Download record、 The plugin logs to theMoviePilot。"
    #  Plug-in icons
    plugin_icon = "sync.png"
    #  Theme color
    plugin_color = "#53BA47"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "nastoolsync_"
    #  Loading sequence
    plugin_order = 15
    #  Available user levels
    auth_level = 1

    #  Private property
    _transferhistory = None
    _plugindata = None
    _downloadhistory = None
    _clear = None
    _nt_db_path = None
    _path = None
    _site = None
    _downloader = None
    _transfer = False

    def init_plugin(self, config: dict = None):
        self._transferhistory = TransferHistoryOper(self.db)
        self._plugindata = PluginDataOper(self.db)
        self._downloadhistory = DownloadHistoryOper(self.db)

        if config:
            self._clear = config.get("clear")
            self._nt_db_path = config.get("nt_db_path")
            self._path = config.get("path")
            self._site = config.get("site")
            self._downloader = config.get("downloader")
            self._transfer = config.get("transfer")

            if self._nt_db_path and self._transfer:
                #  Retrievesqlite Digital
                try:
                    gradedb = sqlite3.connect(self._nt_db_path)
                except Exception as e:
                    self.update_config(
                        {
                            "transfer": False,
                            "clear": False,
                            "nt_db_path": None,
                            "path": self._path,
                            "downloader": self._downloader,
                            "site": self._site,
                        }
                    )
                    logger.error(f" Unable to open database file {self._nt_db_path}， Please check if the path is correct：{e}")
                    return

                #  Creating a cursorcursor To executeexecuteＳＱＬ Statement
                cursor = gradedb.cursor()

                download_history = self.get_nt_download_history(cursor)
                plugin_history = self.get_nt_plugin_history(cursor)
                transfer_history = self.get_nt_transfer_history(cursor)

                #  Close cursor
                cursor.close()

                #  Importing download logs
                if download_history:
                    self.sync_download_history(download_history)

                #  Importing plug-in records
                if plugin_history:
                    self.sync_plugin_history(plugin_history)

                #  Importing history
                if transfer_history:
                    self.sync_transfer_history(transfer_history)

                self.update_config(
                    {
                        "transfer": False,
                        "clear": False,
                        "nt_db_path": self._nt_db_path,
                        "path": self._path,
                        "downloader": self._downloader,
                        "site": self._site,
                    }
                )

    def sync_plugin_history(self, plugin_history):
        """
        Importing plug-in records

        NAStool
        {
            "id": "TorrentTransfer",
            "key: "1-4bdc22bc1e062803c8686beb2796369c59ee141f",
            "value": "{"to_download": 2, "to_download_id": "4bdc22bc1e062803c8686beb2796369c59ee141f", "delete_source": true}"
        },
        {
            "id": "IYUUAutoSeed",
            "key: "f161efaf008d2e56e7939272e8d95eca58fa71dd",
            "value": "[{"downloader": "2", "torrents": ["bd64a8edc5afe6b4beb8813bdbf6faedfb1d4cc4"]}]"
        }
        """
        #  Start counting
        start_time = datetime.now()
        logger.info(" Start synchronizationNAStool The plugin history goes toMoviePilot")
        #  EmptyMoviePilot Plugin records
        if self._clear:
            logger.info("MoviePilot Plugin record cleared")
            self._plugindata.truncate()

        cnt = 0
        for history in plugin_history:
            plugin_id = history[1]
            plugin_key = history[2]
            plugin_value = history[3]

            #  Handling downloader mapping
            if self._downloader:
                downloaders = self._downloader.split("\n")
                for downloader in downloaders:
                    if not downloader:
                        continue
                    sub_downloaders = downloader.split(":")
                    if not str(sub_downloaders[0]).isdigit():
                        logger.error(f" Downloader mapping configuration error：NAStool Downloaderid  Should be a number！")
                        continue
                    #  Replacement of transfer records
                    if str(plugin_id) == "TorrentTransfer":
                        keys = str(plugin_key).split("-")
                        if keys[0].isdigit() and int(keys[0]) == int(sub_downloaders[0]):
                            #  Interchangeabilitykey
                            plugin_key = plugin_key.replace(keys[0], sub_downloaders[1])

                        #  Interchangeabilityvalue
                        if isinstance(plugin_value, str):
                            _value: dict = json.loads(plugin_value)
                        elif isinstance(plugin_value, dict):
                            if str(plugin_value.get("to_download")).isdigit() and int(
                                    plugin_value.get("to_download")) == int(sub_downloaders[0]):
                                plugin_value["to_download"] = sub_downloaders[1]

                    #  Replacement of auxiliary species records
                    if str(plugin_id) == "IYUUAutoSeed":
                        if isinstance(plugin_value, str):
                            plugin_value: list = json.loads(plugin_value)
                        if not isinstance(plugin_value, list):
                            plugin_value = [plugin_value]
                        for value in plugin_value:
                            if not str(value.get("downloader")).isdigit():
                                continue
                            if str(value.get("downloader")).isdigit() and int(value.get("downloader")) == int(
                                    sub_downloaders[0]):
                                value["downloader"] = sub_downloaders[1]

            self._plugindata.save(plugin_id=plugin_id,
                                  key=plugin_key,
                                  value=plugin_value)
            cnt += 1
            if cnt % 100 == 0:
                logger.info(f" Plugin records synchronization progress {cnt} / {len(plugin_history)}")

        #  Computational time
        end_time = datetime.now()

        logger.info(f" Plugin records have been synchronized to complete。 Total time consumption {(end_time - start_time).seconds}  Unit of angle or arc equivalent one sixtieth of a degree")

    def sync_download_history(self, download_history):
        """
        Importing download logs
        """
        #  Start counting
        start_time = datetime.now()
        logger.info(" Start synchronizationNAStool Download history toMoviePilot")
        #  EmptyMoviePilot Download record
        if self._clear:
            logger.info("MoviePilot The download history has been cleared")
            self._downloadhistory.truncate()

        cnt = 0
        for history in download_history:
            mpath = history[0]
            mtype = history[1]
            mtitle = history[2]
            myear = history[3]
            mtmdbid = history[4]
            mseasons = history[5]
            mepisodes = history[6]
            mimages = history[7]
            mdownload_hash = history[8]
            mtorrent = history[9]
            mdesc = history[10]
            msite = history[11]
            mdate = history[12]

            #  Handling of site mapping
            if self._site:
                sites = self._site.split("\n")
                for site in sites:
                    sub_sites = site.split(":")
                    if str(msite) == str(sub_sites[0]):
                        msite = str(sub_sites[1])

            self._downloadhistory.add(
                path=os.path.basename(mpath),
                type=mtype,
                title=mtitle,
                year=myear,
                tmdbid=mtmdbid,
                seasons=mseasons,
                episodes=mepisodes,
                image=mimages,
                download_hash=mdownload_hash,
                torrent_name=mtorrent,
                torrent_description=mdesc,
                torrent_site=msite,
                userid=settings.SUPERUSER,
                date=mdate
            )
            cnt += 1
            if cnt % 100 == 0:
                logger.info(f" Download record synchronization progress {cnt} / {len(download_history)}")

        #  Computational time
        end_time = datetime.now()

        logger.info(f" Download records have been synchronized。 Total time consumption {(end_time - start_time).seconds}  Unit of angle or arc equivalent one sixtieth of a degree")

    def sync_transfer_history(self, transfer_history):
        """
        Import (data)nt Transfer records
        """
        #  Start counting
        start_time = datetime.now()
        logger.info(" Start synchronizationNAStool Transfer history toMoviePilot")

        #  EmptyMoviePilot Transfer records
        if self._clear:
            logger.info("MoviePilot Transfer records have been cleared")
            self._transferhistory.truncate()

        #  Processing data， Deposit (e.g. in a bank account)mp Comprehensive database
        cnt = 0
        for history in transfer_history:
            msrc_path = history[0]
            msrc_filename = history[1]
            mdest_path = history[2]
            mdest_filename = history[3]
            mmode = history[4]
            mtype = history[5]
            mcategory = history[6]
            mtitle = history[7]
            myear = history[8]
            mtmdbid = history[9]
            mseasons = history[10]
            mepisodes = history[11]
            mimage = history[12]
            mdate = history[13]

            if not msrc_path or not mdest_path:
                continue

            msrc = msrc_path + "/" + msrc_filename
            mdest = mdest_path + "/" + mdest_filename

            #  Handling path mapping
            if self._path:
                paths = self._path.split("\n")
                for path in paths:
                    sub_paths = path.split(":")
                    msrc = msrc.replace(sub_paths[0], sub_paths[1]).replace('\\', '/')
                    mdest = mdest.replace(sub_paths[0], sub_paths[1]).replace('\\', '/')

            #  Stockpile
            self._transferhistory.add(
                src=msrc,
                dest=mdest,
                mode=mmode,
                type=mtype,
                category=mcategory,
                title=mtitle,
                year=myear,
                tmdbid=mtmdbid,
                seasons=mseasons,
                episodes=mepisodes,
                image=mimage,
                date=mdate
            )
            logger.debug(f"{mtitle} {myear} {mtmdbid} {mseasons} {mepisodes}  Synchronized")

            cnt += 1
            if cnt % 100 == 0:
                logger.info(f" Synchronization of progress in transferring records {cnt} / {len(transfer_history)}")

        #  Computational time
        end_time = datetime.now()

        logger.info(f" Transfer records have been synchronized。 Total time consumption {(end_time - start_time).seconds}  Unit of angle or arc equivalent one sixtieth of a degree")

    @staticmethod
    def get_nt_plugin_history(cursor):
        """
        Get plugin history
        """
        sql = 'select * from PLUGIN_HISTORY;'
        cursor.execute(sql)
        plugin_history = cursor.fetchall()

        if not plugin_history:
            logger.error(" Not availableNAStool History of plug-ins in database files， Please check that the database path is correct")
            return

        logger.info(f" GetNAStool Plugin records {len(plugin_history)}  Clause (of law or treaty)")
        return plugin_history

    @staticmethod
    def get_nt_download_history(cursor):
        """
        Get download history
        """
        sql = '''
        SELECT
            SAVE_PATH,
            TYPE,
            TITLE,
            YEAR,
            TMDBID,
        CASE
                SE 
            WHEN NULL THEN
                NULL ELSE substr( SE, 1, instr ( SE, ' ' ) - 1 ) 
            END AS seasons,
        CASE
                SE 
            WHEN NULL THEN
                NULL ELSE substr( SE, instr ( SE, ' ' ) + 1 ) 
            END AS episodes,
            POSTER,
            DOWNLOAD_ID,
            TORRENT,
            DESC,
            SITE,
            DATE
        FROM
            DOWNLOAD_HISTORY 
        WHERE
            SAVE_PATH IS NOT NULL;
            '''
        cursor.execute(sql)
        download_history = cursor.fetchall()

        if not download_history:
            logger.error(" Not availableNAStool Download history in database files， Please check that the database path is correct")
            return

        logger.info(f" GetNAStool Download record {len(download_history)}  Clause (of law or treaty)")
        return download_history

    @staticmethod
    def get_nt_transfer_history(cursor):
        """
        Gainnt Transfer records
        """
        sql = '''
        SELECT
            t.SOURCE_PATH AS src_path,
            t.SOURCE_FILENAME AS src_filename,
            t.DEST_PATH AS dest_path,
            t.DEST_FILENAME AS dest_filename,
        CASE
                t.MODE 
                WHEN ' Hard link' THEN
                'link' 
                WHEN ' Mobility' THEN
                'move' 
                WHEN ' Make a copy of' THEN
                'copy' 
            END AS mode,
        CASE
                t.TYPE 
                WHEN ' Cartoons and comics' THEN
                ' Dramas' ELSE t.TYPE 
            END AS type,
            t.CATEGORY AS category,
            t.TITLE AS title,
            t.YEAR AS year,
            t.TMDBID AS tmdbid,
        CASE
                t.SEASON_EPISODE 
            WHEN NULL THEN
                NULL ELSE substr( t.SEASON_EPISODE, 1, instr ( t.SEASON_EPISODE, ' ' ) - 1 ) 
            END AS seasons,
        CASE
                t.SEASON_EPISODE 
            WHEN NULL THEN
                NULL ELSE substr( t.SEASON_EPISODE, instr ( t.SEASON_EPISODE, ' ' ) + 1 ) 
            END AS episodes,
            d.POSTER AS image,
            t.DATE AS date 
        FROM
            TRANSFER_HISTORY t
            LEFT JOIN ( SELECT * FROM DOWNLOAD_HISTORY GROUP BY TMDBID ) d ON t.TMDBID = d.TMDBID
            AND t.TYPE = d.TYPE;
            '''
        cursor.execute(sql)
        nt_historys = cursor.fetchall()

        if not nt_historys:
            logger.error(" Not availableNAStool Transfer history in database files， Please check that the database path is correct")
            return

        logger.info(f" GetNAStool Transfer records {len(nt_historys)}  Clause (of law or treaty)")
        return nt_historys

    def get_state(self) -> bool:
        return False

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Assembly plugin configuration page， Two pieces of data need to be returned：1、 Page configuration；2、 Data structure
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'transfer',
                                            'label': ' Synchronized recording'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'clear',
                                            'label': ' Empty records'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'nt_db_path',
                                            'label': 'NAStool Comprehensive databaseuser.db Trails',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'path',
                                            'rows': '2',
                                            'label': ' History path mapping',
                                            'placeholder': 'NAStool Trails:MoviePilot Trails（ One in a row）'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'downloader',
                                            'rows': '2',
                                            'label': ' Plugin data downloader mapping',
                                            'placeholder': 'NAStool Downloaderid:qbittorrent|transmission（ One in a row）'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'site',
                                            'label': ' Download historical site mapping',
                                            'placeholder': 'NAStool Site name:MoviePilot Site name（ One in a row）'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'text': ' When clearing records is turned on， Will be deleted before importing historical dataMoviePilot Previous records。'
                                                    ' If there are a lot of transfer records， Synchronization may take a long time（3-10 Minutes），'
                                                    ' So it's normal that the page doesn't respond when you click ok.， It's being processed in the background.。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "transfer": False,
            "clear": False,
            "supp": False,
            "nt_db_path": "",
            "path": "",
            "downloader": "",
            "site": "",
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        Exit plugin
        """
        pass
