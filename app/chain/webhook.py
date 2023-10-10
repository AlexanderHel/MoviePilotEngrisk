import time
from typing import Any

from app.chain import ChainBase
from app.schemas import Notification
from app.schemas.types import EventType, MediaImageType, MediaType, NotificationType
from app.utils.web import WebUtils


class WebhookChain(ChainBase):
    """
    Webhook Process chain
    """

    def message(self, body: Any, form: Any, args: Any) -> None:
        """
        Deal withWebhook Message and send the message
        """
        #  Getting the main content
        event_info = self.webhook_parser(body=body, form=form, args=args)
        if not event_info:
            return
        #  Broadcasting incident
        self.eventmanager.send_event(EventType.WebhookMessage, event_info)
        #  Assembly message content
        _webhook_actions = {
            "library.new": " New entry",
            "system.webhooktest": " Beta (software)",
            "playback.start": " Start playing",
            "playback.stop": " Stop playing",
            "user.authenticated": " Login successful",
            "user.authenticationfailed": " Login failure",
            "media.play": " Start playing",
            "media.stop": " Stop playing",
            "PlaybackStart": " Start playing",
            "PlaybackStop": " Stop playing",
            "item.rate": " Marked"
        }
        _webhook_images = {
            "emby": "https://emby.media/notificationicon.png",
            "plex": "https://www.plex.tv/wp-content/uploads/2022/04/new-logo-process-lines-gray.png",
            "jellyfin": "https://play-lh.googleusercontent.com/SCsUK3hCCRqkJbmLDctNYCfehLxsS4ggD1ZPHIFrrAN1Tn9yhjmGMPep2D9lMaaa9eQi"
        }

        if not _webhook_actions.get(event_info.event):
            return

        #  Message title
        if event_info.item_type in ["TV", "SHOW"]:
            message_title = f"{_webhook_actions.get(event_info.event)} Episode {event_info.item_name}"
        elif event_info.item_type == "MOV":
            message_title = f"{_webhook_actions.get(event_info.event)} Cinematic {event_info.item_name}"
        elif event_info.item_type == "AUD":
            message_title = f"{_webhook_actions.get(event_info.event)} Audiobook {event_info.item_name}"
        else:
            message_title = f"{_webhook_actions.get(event_info.event)}"

        #  Message
        message_texts = []
        if event_info.user_name:
            message_texts.append(f" Subscribers：{event_info.user_name}")
        if event_info.device_name:
            message_texts.append(f" Installations：{event_info.client} {event_info.device_name}")
        if event_info.ip:
            message_texts.append(f"IP Address：{event_info.ip} {WebUtils.get_location(event_info.ip)}")
        if event_info.percentage:
            percentage = round(float(event_info.percentage), 2)
            message_texts.append(f" Degree of progress (on project)：{percentage}%")
        if event_info.overview:
            message_texts.append(f" Plots：{event_info.overview}")
        message_texts.append(f" Timing：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}")

        #  Message
        message_content = "\n".join(message_texts)

        #  Message pictures
        image_url = event_info.image_url
        #  Check episode images
        if (event_info.tmdb_id
                and event_info.season_id
                and event_info.episode_id):
            specific_image = self.obtain_specific_image(
                mediaid=event_info.tmdb_id,
                mtype=MediaType.TV,
                image_type=MediaImageType.Backdrop,
                season=event_info.season_id,
                episode=event_info.episode_id
            )
            if specific_image:
                image_url = specific_image
        #  Using the default image
        if not image_url:
            image_url = _webhook_images.get(event_info.channel)

        #  Send a message
        self.post_message(Notification(mtype=NotificationType.MediaServer,
                                       title=message_title, text=message_content, image=image_url))
