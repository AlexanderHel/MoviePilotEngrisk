from pathlib import Path

import regex as re

from app.core.config import settings
from app.core.meta import MetaAnime, MetaVideo, MetaBase
from app.core.meta.words import WordsMatcher


def MetaInfo(title: str, subtitle: str = None) -> MetaBase:
    """
    Identify metadata by title and subtitle
    :param title:  Caption、 Seed name、 Filename
    :param subtitle:  Subheading、 Descriptive
    :return: MetaAnime、MetaVideo
    """
    #  Original title
    org_title = title
    #  Preprocessing headings
    title, apply_words = WordsMatcher().prepare(title)
    #  Determining whether to process a file
    if title and Path(title).suffix.lower() in settings.RMT_MEDIAEXT:
        isfile = True
    else:
        isfile = False
    #  Recognize
    meta = MetaAnime(title, subtitle, isfile) if is_anime(title) else MetaVideo(title, subtitle, isfile)
    #  Original title of record
    meta.title = org_title
    #   Record the identifiers used
    meta.apply_words = apply_words or []

    return meta


def MetaInfoPath(path: Path) -> MetaBase:
    """
    Recognize metadata based on paths
    :param path:  Trails
    """
    #  Upper level catalog metadata
    dir_meta = MetaInfo(title=path.parent.name)
    #  Document metadata， Exclusive of suffix
    file_meta = MetaInfo(title=path.stem)
    #  Merging metadata
    file_meta.merge(dir_meta)
    return file_meta


def is_anime(name: str) -> bool:
    """
    Determine if it's an anime
    :param name:  Name (of a thing)
    :return:  Anime or not
    """
    if not name:
        return False
    if re.search(r'【[+0-9XVPI-]+】\s*【', name, re.IGNORECASE):
        return True
    if re.search(r'\s+-\s+[\dv]{1,4}\s+', name, re.IGNORECASE):
        return True
    if re.search(r"S\d{2}\s*-\s*S\d{2}|S\d{2}|\s+S\d{1,2}|EP?\d{2,4}\s*-\s*EP?\d{2,4}|EP?\d{2,4}|\s+EP?\d{1,4}", name,
                 re.IGNORECASE):
        return False
    if re.search(r'\[[+0-9XVPI-]+]\s*\[', name, re.IGNORECASE):
        return True
    return False
