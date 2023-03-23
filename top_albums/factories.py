import datetime
import decimal
import functools
import random
import re
import uuid
from typing import Optional

import factory

from top_albums.models import Album, ITunesCategory


RE_NON_WORD_CHARS = re.compile(r"\W+")


class ITunesCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ITunesCategory
        django_get_or_create = ("id", "label", "term")

    _last_auto_id = 0

    id = factory.LazyFunction(lambda: ITunesCategoryFactory._auto_id())

    @classmethod
    def make(cls, name: str, id: Optional[int] = None) -> ITunesCategory:
        """ Use this instead of __init__ (way less verbose). """
        if id is None:
            id = cls._auto_id()
        name = RE_NON_WORD_CHARS.sub("-", name.lower())
        return ITunesCategoryFactory(id=id, label=name, term=name, scheme=f"https://music.apple.com/us/genre/music-{name}/id{id}?uo=2")

    @classmethod
    def _auto_id(cls):
        cls._last_auto_id += 1
        return cls._last_auto_id


class AlbumFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Album

    id = factory.LazyFunction(functools.partial(random.randint, 1_000_000_000, 2_000_000_000))
    name = factory.LazyFunction(lambda: f"Soothing Sounds of {uuid.uuid4()}")
    release_date = datetime.date(year=2000, month=1, day=1)
    track_count = 10

    itunes_price_dollars = decimal.Decimal("19.99")
