import decimal
import functools
import http.client
import json
from typing import Callable, List, Optional, Tuple

from dateutil import parser
from django.forms import model_to_dict

from top_albums.models import Album, ITunesCategory


class FeedError(Exception):
    def __init__(self, *args, json_entry=None):
        super().__init__(*args)
        self.json_entry = json_entry


class ITunesFeed:

    def __init__(self, downloader: Optional[Callable] = None):
        if downloader is None:
            def download():
                conn = http.client.HTTPSConnection("itunes.apple.com")
                conn.request("GET", "/us/rss/topalbums/limit=100/json")
                response = conn.getresponse()
                return response.read().decode("UTF-8")

            self.downloader = download
        else:
            self.downloader = downloader

    def download_top_albums(self) -> Tuple[List[Album], List[ITunesCategory]]:
        """ Downloads feed & translates into model objects; doesn't touch database. """
        document = json.loads(self.downloader())

        albums = []
        categories = []
        for entry in document["feed"]["entry"]:
            album, category = self._models_from_feed_entry(entry)
            albums.append(album)
            categories.append(category)

        # Remove duplicates.
        # Hint: "acc" is a pair (tuple) where [0] is new list we're building and [1] is last id value visited.
        categories = sorted(categories, key=lambda x: x.id)
        categories = functools.reduce(
            lambda acc, cat: (acc[0]+[cat] if acc[1] != cat.id else acc[0], cat.id), categories, ([], 0)
        )[0]

        return albums, categories

    def download_and_merge_top_albums(self) -> int:
        albums, categories = self.download_top_albums()
        top_albums = list(albums)
        if not top_albums:
            raise FeedError("Cannot merge empty top-albums list into database")

        for category in categories:
            ITunesCategory.objects.update_or_create(defaults=model_to_dict(category), id=category.id)

        top_ids = []
        for album in albums:
            data = model_to_dict(album, exclude=("itunes_category",))
            data["itunes_category"] = album.itunes_category
            Album.objects.update_or_create(defaults=data, id=album.id)
            top_ids.append(album.id)

        Album.objects.exclude(id__in=top_ids).filter(is_itunes_top=True).update(is_itunes_top=False)

        return len(top_ids)

    @staticmethod
    def _models_from_feed_entry(entry: dict, is_top=True) -> Tuple[Album, ITunesCategory]:
        try:
            cat_attrs = entry["category"]["attributes"]
            category = ITunesCategory(
                id=int(cat_attrs["im:id"]),
                label=cat_attrs["label"],
                term=cat_attrs["term"],
                scheme=cat_attrs["scheme"]
            )

            album = Album(
                id=int(entry["id"]["attributes"]["im:id"]),
                name=entry["im:name"]["label"],
                artist=entry["im:artist"]["label"],
                artist_url=entry["im:artist"]["attributes"]["href"] if "attributes" in entry["im:artist"] else None,
                release_date=parser.parse(entry["im:releaseDate"]["label"]).date(),
                track_count=int(entry["im:itemCount"]["label"]),
                rights=entry["rights"]["label"],
                is_itunes_top=is_top,
                itunes_category=category,
                itunes_link=entry["link"]["attributes"]["href"],
                itunes_price_dollars=decimal.Decimal(entry["im:price"]["attributes"]["amount"])
            )

            image_list = entry["im:image"]
            for index in range(min(3, len(image_list))):
                setattr(album, f"image_{index + 1}_url", image_list[index]["label"])
                setattr(album, f"image_{index + 1}_height", int(image_list[index]["attributes"]["height"]))

            return album, category
        except (KeyError, ValueError) as ex:
            raise FeedError(f"iTunes feed structure change? Clue: {ex}", json_entry=entry)
