from enum import Enum


class MediaType(Enum):
    MOVIE = ' Cinematic'
    TV = ' Dramas'
    UNKNOWN = ' Uncharted'


class TorrentStatus(Enum):
    TRANSFER = " Transferable"
    DOWNLOADING = " Downloading"


#  Event listener
class EventType(Enum):
    #  Plugin reloading
    PluginReload = "plugin.reload"
    #  Execute a command
    CommandExcute = "command.excute"
    #  Site check-in
    SiteSignin = "site.signin"
    #  Site statistics
    SiteStatistic = "site.statistic"
    #  Site deletion
    SiteDeleted = "site.deleted"
    #  Douban wants to see
    DoubanSync = "douban.sync"
    # Webhook Messages
    WebhookMessage = "webhook.message"
    #  Transfer completed
    TransferComplete = "transfer.complete"
    #  Add download
    DownloadAdded = "download.added"
    #  Delete history
    HistoryDeleted = "history.deleted"
    #  Delete download source file
    DownloadFileDeleted = "downloadfile.deleted"
    #  User external messages
    UserMessage = "user.message"
    #  Notification message
    NoticeMessage = "notice.message"


#  System configurationKey Dictionaries
class SystemConfigKey(Enum):
    #  User-installed plug-ins
    UserInstalledPlugins = "UserInstalledPlugins"
    #  Search results
    SearchResults = "SearchResults"
    #  Search site scope
    IndexerSites = "IndexerSites"
    #  Subscription site coverage
    RssSites = "RssSites"
    #  Seed prioritization rules
    TorrentsPriority = "TorrentsPriority"
    #  Notification message渠道设置
    NotificationChannels = "NotificationChannels"
    #  Customizing the production team/ Subtitling team
    CustomReleaseGroups = "CustomReleaseGroups"
    #  Custom placeholders
    Customization = "Customization"
    #  Customized identifiers
    CustomIdentifiers = "CustomIdentifiers"
    #  Search prioritization rules
    SearchFilterRules = "SearchFilterRules"
    #  Subscription prioritization rules
    SubscribeFilterRules = "SubscribeFilterRules"
    #  Washing rules
    BestVersionFilterRules = "BestVersionFilterRules"
    #  Default filtering rules
    DefaultFilterRules = "DefaultFilterRules"
    #  Redirection of blocked words
    TransferExcludeWords = "TransferExcludeWords"


#  Processing progressKey Dictionaries
class ProgressKey(Enum):
    #  Look for sth.
    Search = "search"
    #  Divert or distract (attention etc)
    FileTransfer = "filetransfer"


#  Media image types
class MediaImageType(Enum):
    Poster = "poster"
    Backdrop = "backdrop"


#  Message type
class NotificationType(Enum):
    #  Resource download
    Download = " Resource download"
    #  Put sth into storage
    Organize = " Put sth into storage"
    #  Subscribe to
    Subscribe = " Subscribe to"
    #  Site news
    SiteMessage = " Site news"
    #  Media server notification
    MediaServer = " Media server notification"
    #  Processing failures require manual intervention
    Manual = " Manual processing of notifications"


class MessageChannel(Enum):
    """
    News channel
    """
    Wechat = " Microsoft"
    Telegram = "Telegram"
    Slack = "Slack"
    SynologyChat = "SynologyChat"
