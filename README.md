#MoviePilot

Based on the partial code redesign of [NAStool](https://github.com/NAStool/nas-tools) , it focuses on the core requirements of automation, reducing problems and making it easier to expand and maintain.

#Only for learning and communication, please do not promote this project on any domestic platform!

Release channel: https://t.me/moviepilot_channel

## Main features
-Separation of front-end and back-end, based on FastApi + Vue3 , front-end project address: [MoviePilot-Frontend](https://github.com/jxxghp/MoviePilot-Frontend)
-Focus on core needs, simplify functions and settings, and use default values for some settings.
-The user interface has been redesigned to be more beautiful and easier to use .

## Installation

### 1. ** Install CookieCloud plug-in **

Site information needs to be obtained through CookieCloud synchronization , so you need to install the CookieCloud plug-in to synchronize the site cookie data in the browser to the cloud and then synchronize it to MoviePilot for use. Please click [ here ](https://github.com/easychen/CookieCloud/releases) for the plug-in download address .

### 2. ** Install CookieCloud server (optional) **

MoviePilot has a built-in public CookieCloud server . If you need to build your own service, you can refer to the [CookieCloud](https://github.com/easychen/CookieCloud) project to build it. For the docker image, please click [ here ](https://hub .docker.com/r/easychen/cookiecloud) .

** Statement: ** This project will not collect sensitive user data. Cookie synchronization is also based on the CookieCloud project and is not a capability provided by this project. From a technical perspective , CookieCloud uses end-to-end encryption. A third party cannot steal any user information (including the server holder ) without revealing the ` user KEY` and ` end-to-end encrypted password` . If you are worried, you don’t have to use public services or this project. However, if any information leakage occurs after use, this project has nothing to do with it!

### 3. ** Install supporting management software **

MoviePilot requires a downloader and media server to be used together.
-Downloader supports : qBittorrent , Transmission , QB version number requirement >= 4.3.9 , TR version number requirement >= 3.0 , QB is recommended .
-Media server support: Jellyfin , Emby , Plex , Emby is recommended .

### 4. ** Install MoviePilot**

- Docker image

  Click [ here ](https://hub.docker.com/r/jxxghp/moviepilot) or execute the command:

```shell
docker pull jxxghp/moviepilot:latest
```

- Windows

  Download [MoviePilot.exe](https://github.com/jxxghp/MoviePilot/releases) , double-click to run and automatically generate the configuration file directory.

## Configuration

All configurations of the project are set through environment variables, and two configuration methods are supported:
- Configure parameters in the Docker environment variables section or Wdinows system environment variables. If the configuration items are not automatically displayed, you need to manually add the corresponding environment variables.
-Download the [app.env](https://github.com/jxxghp/MoviePilot/raw/main/config/app.env) configuration file, modify the configuration and place it in the root directory of the configuration file mapping path , configuration items You can increase or decrease it according to the instructions.

Configuration file mapping path: `/config` , configuration item effective priority: environment variables > env file > default value, ** Some parameters such as path mapping, site authentication, permission port, time zone, etc. must be configured through environment variables ** .

items marked with $\color{red}{*}$ are required, and the others are optional. If you choose the option, you can delete the configuration variable and use the default value.

### 1. ** Basic Settings **

- **NGINX_PORT $\color{red}{*}$ : ** WEB service port, default `3000` , can be modified by yourself, and cannot conflict with the API service port (only environment variable configuration is supported)
- **PORT $\color{red}{*}$ : ** API service port, default `3001` , can be modified by yourself, and cannot conflict with the WEB service port (only environment variable configuration is supported)
- **PUID** : `uid` of the user running the program , default `0` ( only environment variable configuration is supported)
- **PGID** : `gid` of the user running the program , default `0` ( only environment variable configuration is supported)
- **UMASK** : Mask permission, default `000` , you can consider setting it to `022` ( only environment variable configuration is supported)
- **MOVIEPILOT_AUTO_UPDATE** : Restart update, `true`/`false` , default `true` ** Note: If there is a network problem, you can configure `PROXY_HOST` , see the explanation of `PROXY_HOST` below for details ** ( only Support environment variable configuration)
- **MOVIEPILOT_AUTO_UPDATE_DEV** : Update to unreleased development version code when restarting, `true`/`false` , default `false` ( only environment variable configuration is supported)
---
- **SUPERUSER $\color{red}{*}$ : ** Super administrator username, default `admin` , use this user to log in to the backend management interface after installation
- **SUPERUSER_PASSWORD $\color{red}{*}$ : ** Super administrator initial password, default `password` , it is recommended to change it to a complex password
- **API_TOKEN $\color{red}{*}$ : ** API key , default `moviepilot` , the value `?token=` needs to be added to the media server Webhook , WeChat callback and other address configurations , it is recommended to change it to a complex string
- **PROXY_HOST : ** Network proxy. To access themoviedb or restart the update, you need to use proxy access. The format is `http(s)://ip:port` , `socks5://user:pass@host:port` ( optional )
- **TMDB_API_DOMAIN : ** TMDB API address, the default is `api.themoviedb.org` , it can also be configured as `api.tmdb.org` or other transfer proxy service address, as long as it can be connected
- **TMDB_IMAGE_DOMAIN : ** TMDB image address, default `image.tmdb.org` , can be configured as other transfer agent to speed up TMDB image display, such as: `static-mdb.v.geilijiasu.com`
---
- **SCRAP_METADATA : ** Scrape media files into the library , `true`/`false` , default `true`
- **SCRAP_SOURCE : ** Data source used for scraping metadata and images, `themoviedb`/`douban` , default `themoviedb`
- **SCRAP_FOLLOW_TMDB : ** Whether the newly added media will follow the changes of TMDB information , `true`/`false` , default `true`
---
- **TRANSFER_TYPE $\color{red}{*}$ : ** Organize transfer methods, support `link`/`copy`/`move`/`softlink` ** Note: Transfer between `link` and `softlink` In this mode, the transferred file will inherit the permission mask of the source file and will not be affected by `UMASK` **
- **LIBRARY_PATH $\color{red}{*}$ : ** Media library directory, multiple directories are separated by `,`
- **LIBRARY_MOVIE_NAME : ** Movie media library directory name (not full path), default ` movie`
- **LIBRARY_TV_NAME : ** TV drama media library directory name (not the full path), default ` TV drama`
- **LIBRARY_ANIME_NAME : ** Animation media library directory name (not the full path), default ` TV Series / Anime`
- **LIBRARY_CATEGORY : ** Media library secondary classification switch, `true`/`false` , default `false` , after being turned on, it will be configured according to [category.yaml](https://github.com/jxxghp/MoviePilot /raw/main/config/category.yaml) automatically creates a secondary directory category in the media library directory.
---
- **COOKIECLOUD_HOST $\color{red}{*}$ : ** CookieCloud server address, format: `http(s)://ip:port` , if not configured , the built-in server `https:/ will be used by default /movie-pilot.org/cookiecloud`
- **COOKIECLOUD_KEY $\color{red}{*}$ : ** CookieCloud user KEY
- **COOKIECLOUD_PASSWORD $\color{red}{*}$ : ** CookieCloud end-to-end encryption password
- **COOKIECLOUD_INTERVAL $\color{red}{*}$ : ** CookieCloud synchronization interval (minutes)
- **USER_AGENT $\color{red}{*}$ : ** CookieCloud saves the browser UA corresponding to the cookie . It is recommended to configure it. After setting, it can increase the success rate of connecting to the site. It can be modified in the management interface after synchronizing the site.
- **OCR_HOST : ** OCR identification server address, format: `http(s)://ip:port` , used to identify site verification codes to achieve automatic login to obtain cookies , etc. If not configured , the built-in server `https will be used by default ://movie-pilot.org` , you can use [ this image ](https://hub.docker.com/r/jxxghp/moviepilot-ocr) to build it yourself.
---
- **SUBSCRIBE_MODE : ** Subscription mode, `rss`/`spider` , default `spider` , `rss` mode matches the subscription by regularly refreshing RSS ( the RSS address will be automatically obtained, or can be maintained manually), It puts less pressure on the site. At the same time, the subscription refresh cycle can be set and runs 24 hours a day. However, subscription and download notifications cannot be filtered and displayed for free. It is recommended to use RSS mode.
- **SUBSCRIBE_RSS_INTERVAL : ** RSS subscription mode refresh interval (minutes), default `30` minutes , cannot be less than 5 minutes .
- **SUBSCRIBE_SEARCH : ** Subscription search, `true`/`false` , default `false` , after turning on, all subscriptions will be fully searched every 24 hours to fill in missing episodes (normally normal Just subscribe. Subscribing to search is only for backup and will increase the pressure on the site. It is not recommended to enable it).
- **SEARCH_SOURCE : ** Media information search source, `themoviedb`/`douban` , default `themoviedb`
---
- **AUTO_DOWNLOAD_USER : ** User ID to automatically select the best download during remote interactive search , used by multiple users , divided, if not set, you need to select resources or reply `0`
- **MESSAGER $\color{red}{*}$ : ** Message notification channel, supports `telegram`/`wechat`/`slack`/`synologychat` , use `,` to separate multiple channels . At the same time, you also need to configure the environment variables of the corresponding channel. Variables that do not correspond to the channel can be deleted. It is recommended to use `telegram`

- `wechat` settings:

- **WECHAT_CORPID : ** WeChat corporate ID
- **WECHAT_APP_SECRET : ** WeChat Application Secret
- **WECHAT_APP_ID : ** WeChat application ID
- **WECHAT_TOKEN : ** Token for WeChat message callback
- **WECHAT_ENCODING_AESKEY : ** EncodingAESKey of WeChat message callback
- **WECHAT_ADMINS : ** WeChat administrator list, multiple administrators separated by English commas (optional)
- **WECHAT_PROXY : ** WeChat proxy server (do not add / after )

- `telegram` settings:

- **TELEGRAM_TOKEN : ** Telegram Bot Token
- **TELEGRAM_CHAT_ID : ** Telegram Chat ID
- **TELEGRAM_USERS : ** Telegram user ID , multiple use , separated, only the user ID in the list can use Bot , if not set, all Bot can be used
- **TELEGRAM_ADMINS : ** Telegram administrator ID , multiple uses , separated, only administrators can operate the Bot menu , if not set, everyone can operate the menu (optional)

- `slack` settings:

- **SLACK_OAUTH_TOKEN : ** Slack Bot User OAuth Token
- **SLACK_APP_TOKEN : ** Slack App-Level Token
** SLACK_CHANNEL : ** Slack channel name, default ` all` ( optional )
  
- `synologychat` settings:

- **SYNOLOGYCHAT_WEBHOOK : ** Create a bot in Synology Chat and get the bot's ` incoming URL`
- **SYNOLOGYCHAT_TOKEN : ** SynologyChat bot ` token`

---
- **DOWNLOAD_PATH $\color{red}{*}$ : ** Download saving directory, ** Note : The mapping paths of `moviepilot` and ` Downloader` need to be consistent ** , otherwise it will cause downloading File cannot be transferred
- **DOWNLOAD_MOVIE_PATH : ** Movie download and save directory path, if not set, download to `DOWNLOAD_PATH`
- **DOWNLOAD_TV_PATH : ** The path to the TV series download and save directory. If not set, it will be downloaded to `DOWNLOAD_PATH`
- **DOWNLOAD_ANIME_PATH : ** Animation download and save directory path, if not set, download to `DOWNLOAD_PATH`
- **DOWNLOAD_CATEGORY : ** Download the secondary classification switch, `true`/`false` , the default is `false` , after being turned on, it will be configured according to [category.yaml](https://github.com/jxxghp/MoviePilot /raw/main/config/category.yaml) automatically creates a secondary directory category in the download directory.
- **DOWNLOAD_SUBTITLE : ** Download site subtitles, `true`/`false` , default `true`
- **DOWNLOADER_MONITOR : ** Downloader monitoring, `true`/`false` , the default is `true` , it will be automatically sorted into the database when the download is completed.
- **TORRENT_TAG : ** Downloader seed tag, the default is `MOVIEPILOT` . After setting, only downloads added by MoviePilot will be processed. If left blank, all tasks in the downloader will be processed.
- **DOWNLOADER $\color{red}{*}$ : ** Downloader , supports `qbittorrent`/`transmission` , QB version number requirement >= 4.3.9 , TR version number requirement >= 3.0 , at the same time You also need to configure the environment variables of the corresponding channel. Variables that do not correspond to the channel can be deleted. It is recommended to use `qbittorrent`

- `qbittorrent` settings:

- **QB_HOST : ** qbittorrent address, format: `ip:port` , https needs to add `https://` prefix
- **QB_USER : ** qbittorrent username
- **QB_PASSWORD : ** qbittorrent password
- **QB_CATEGORY : ** Automatic management of qbittorrent categories, `true`/`false` , default `false` , when enabled, the download secondary category will be passed to the downloader, and the downloader will manage the download directory, which needs to be synchronized Turn on `DOWNLOAD_CATEGORY`

- `transmission` settings:

- **TR_HOST : ** transmission address, format: `ip:port` , https needs to add `https://` prefix
- **TR_USER : ** transmission username
- **TR_PASSWORD : ** transmission password

---
- **REFRESH_MEDIASERVER : ** Whether to refresh the media server after storage , `true`/`false` , default `true`
- **MEDIASERVER $\color{red}{*}$ : ** Media server , supports `emby`/`jellyfin`/`plex` , and can open multiple files at the same time separated by `,` . You also need to configure the environment variables corresponding to the media server. Variables that do not correspond to the media server can be deleted. It is recommended to use `emby`

- `emby` settings:

- **EMBY_HOST : ** Emby server address, format: `ip:port` , https needs to add `https://` prefix
- **EMBY_API_KEY : ** Emby Api Key , generated at ` Settings- > Advanced- > API Key`

- `jellyfin` settings:

- **JELLYFIN_HOST : ** Jellyfin server address, format: `ip:port` , https needs to add `https://` prefix
- **JELLYFIN_API_KEY : ** Jellyfin Api Key , generated at ` Settings- > Advanced- > API Key`

- `plex` settings:

- **PLEX_HOST : ** Plex server address, format: `ip:port` , https needs to add `https://` prefix
- **PLEX_TOKEN : ** `X-Plex-Token` in the Plex web page Url , obtained from the request URL through the browser F12-> Network

- **MEDIASERVER_SYNC_INTERVAL:** Media server synchronization interval (hours), default `6` , leave it blank to not synchronize
- **MEDIASERVER_SYNC_BLACKLIST:** Media server synchronization blacklist, multiple media library names used , split


### 2. ** User Authentication **

`MoviePilot` requires authentication before it can be used. After configuring `AUTH_SITE` , you need to configure the authentication parameters of the corresponding site according to the following table ( ** can only be configured through environment variables ** )

- **AUTH_SITE $\color{red}{*}$ : ** Authentication site, supports `iyuu`/`hhclub`/`audiences`/`hddolby`/`zmpt`/`freefarm`/`hdfans`/` wintersakura`/`leaves`/`1ptba`/`icc2022`/`ptlsp`/`xingtan`

| Site | Parameters |
|:---------------------:|:---------------------------------- ------------------:|
| iyuu | `IYUU_SIGN` : IYUU login token |
| hhclub | `HHCLUB_USERNAME` : username <br/> `HHCLUB_PASSKEY` : key |
| audiences | `AUDIENCES_UID` : User ID<br/> `AUDIENCES_PASSKEY` : Key |
| hddolby | `HDDOLBY_ID` : User ID<br/> `HDDOLBY_PASSKEY` : Key |
| zmpt | `ZMPT_UID` : User ID<br/> `ZMPT_PASSKEY` : Key |
| freefarm | `FREEFARM_UID` : User ID<br/> `FREEFARM_PASSKEY` : Key |
| hdfans | `HDFANS_UID` : User ID<br/> `HDFANS_PASSKEY` : Key |
| wintersakura | `WINTERSAKURA_UID` : User ID<br/> `WINTERSAKURA_PASSKEY` : Key |
| leaves | `LEAVES_UID` : User ID<br/> `LEAVES_PASSKEY` : Key |
| 1ptba | `1PTBA_UID` : User ID<br/> `1PTBA_PASSKEY` : Key |
| icc2022 | `ICC2022_UID` : User ID<br/> `ICC2022_PASSKEY` : Key |
| ptlsp | `PTLSP_UID` : User ID<br/> `PTLSP_PASSKEY` : Key |
| _ _ _ _


### 2. ** Advanced configuration **

- **BIG_MEMORY_MODE : ** Big memory mode, the default is `false` , it will take up more memory when turned on, but the response speed will be faster

- **MOVIE_RENAME_FORMAT : ** Movie rename format

Configuration items supported by `MOVIE_RENAME_FORMAT` :

> `title` : title  
> `original_name` : Original file name  
> `original_title` : Original language title  
> `name` : identification name  
> `year` : years  
> `resourceType` : resource type  
> `effect` : special effects  
> `edition` : Version ( resource type + special effects)  
> `videoFormat` : resolution  
> `releaseGroup` : Production team / subtitle team  
> `customization` : Custom placeholder  
> `videoCodec` : video encoding  
> `audioCodec` : audio encoding  
> `tmdbid` : TMDBID
> `imdbid` : IMDBID
> `part` : paragraph / section  
> `fileExt` : file extension

`MOVIE_RENAME_FORMAT` default configuration format:

```
{{title}}{% if year %} ({{year}}){% endif %}/{{title}}{% if year %} ({{year}}){% endif %}{% if part %}-{{part}}{% endif %}{% if videoFormat %} - {{videoFormat}}{% endif %}{{fileExt}}
```

- **TV_RENAME_FORMAT : ** TV series renaming format

Additional configuration items supported by `TV_RENAME_FORMAT` :

> `season` : Season number  
> `episode` : Set number  
> `season_episode` : Season EpisodeSxxExx
> `episode_title` : episode title

`TV_RENAME_FORMAT` default configuration format:

```
{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/{{title}} - {{season_episode}}{% if part %}-{ {part}}{ % endif %}{% if episode %} -Episode {{episode}} {% endif %}{{fileExt}}
```


### 3. ** Priority Rules **

-Only supports the use of built - in rules for arrangement and combination. The built-in rules are: ` Blu-ray original disc` , `4K` , `1080P` , ` Chinese subtitles` , ` Special effects subtitles` , ` H265` , `H264` , ` Dolby` , `HDR` , `REMUX` , ` WEB -DL` , ` Free` , ` Mandarin Dubbing` , etc.
-Resources that meet the rules of any level will be identified and selected. The level with successful matching will be used as the priority of the resource. The priority will be higher if it is ranked higher.
that do not comply with all levels of filtering rules will not be selected


## Use

- Quickly synchronize sites through CookieCloud synchronization. Sites that are not needed can be disabled in the WEB management interface, and sites that cannot be synchronized can be added manually .
-Manage through WEB, add WEB to the mobile desktop to obtain App- like usage effects, management interface port: ` 3000` , background API port: `3001` .
-Achieve automatic sorting and scraping through downloader monitoring or directory monitoring plug-in (choose one of the two).
-Remote management through WeChat /Telegram/Slack/SynologyChat , where WeChat /Telegram will automatically add an operation menu (the number of WeChat menus is limited, and some menus are not displayed); WeChat needs to set the callback address on the official page, and SynologyChat needs to set it The robot passes in the address, and the relative path of the address is: `/api/v1/message/` .
-Set media server Webhook , send playback notifications through MoviePilot , etc. The relative path of Webhook callback is `/api/v1/webhook?token=moviepilot` ( `3001` port), where `moviepilot` is the set `API_TOKEN` .
- Add MoviePilot as a Radarr or Sonarr server to Overseerr or Jellyseerr ( `API service port` ) , and you can use Overseerr/Jellyseerr to browse subscriptions.
- Map the host docker.sock file to the container `/var/run/docker.sock` to support built-in restart operations. Example: `-v /var/run/docker.sock:/var/run/docker.sock:ro`

### ** NOTE **
-The first startup of the container requires downloading the browser kernel, which may take a long time depending on network conditions, and you cannot log in at this time. The `/moviepilot` directory can be mapped to avoid re-triggering the browser kernel download after the container is reset. 
-When using a reverse proxy , you need to add the following configuration, otherwise some functions may be inaccessible ( `ip:port` is modified to the actual value):
```nginx configuration
location/{
proxy_pass http://ip:port;
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
}
```
-The newly created enterprise WeChat application requires a proxy with a fixed public IP to receive messages. Add the following code to the proxy:
```nginx configuration
location /cgi-bin/gettoken {
proxy_pass https://qyapi.weixin.qq.com;
}
location /cgi-bin/message/send {
proxy_pass https://qyapi.weixin.qq.com;
}
location /cgi-bin/menu/create {
proxy_pass https://qyapi.weixin.qq.com;
}
```

![image](https://github.com/jxxghp/MoviePilot/assets/51039935/f2654b09-26f3-464f-a0af-1de3f97832ee)

![image](https://github.com/jxxghp/MoviePilot/assets/51039935/fcb87529-56dd-43df-8337-6e34b8582819)

![image](https://github.com/jxxghp/MoviePilot/assets/51039935/bfa77c71-510a-46a6-9c1e-cf98cb101e3a)

![image](https://github.com/jxxghp/MoviePilot/assets/51039935/51cafd09-e38c-47f9-ae62-1e83ab8bf89b)

