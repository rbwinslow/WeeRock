import copy
import decimal
import json
import os
import random

from django.test import TestCase

from top_albums.factories import AlbumFactory, ITunesCategoryFactory
from top_albums.feed import ITunesFeed
from top_albums.models import Album, ITunesCategory


class ITunesFeedTests(TestCase):

    def setUp(self) -> None:
        path = os.path.join(os.path.dirname(__file__), "feed-sample-top-albums.json")
        with open(path, "r") as f:
            self.sample_feed_contents = json.load(f)
        self.feed_boilerplate = {
            "feed": {k: (self.sample_feed_contents["feed"][k] if k != "entry" else [])
                     for k in self.sample_feed_contents["feed"].keys()}
        }

    def test_download_happy_path(self) -> None:
        # given
        expected_category_ids = set(
            int(e["category"]["attributes"]["im:id"]) for e in self.sample_feed_contents["feed"]["entry"]
        )
        feed = ITunesFeed(lambda: json.dumps(self.sample_feed_contents))

        # when
        actual_albums, actual_categories = feed.download_top_albums()

        # then
        self.assertEquals(len(actual_albums), len(self.sample_feed_contents["feed"]["entry"]))
        self.assertEquals(len(actual_categories), len(expected_category_ids))
        albums_by_id = {a.id: a for a in actual_albums}
        for expected_entry in self.sample_feed_contents["feed"]["entry"]:
            actual_album = albums_by_id[int(expected_entry["id"]["attributes"]["im:id"])]
            # spot check some fields
            self.assertEquals(actual_album.name, expected_entry["im:name"]["label"])
            self.assertEquals(actual_album.artist, expected_entry["im:artist"]["label"])
            self.assertEquals(actual_album.release_date.strftime("%Y-%m-%d"), expected_entry["im:releaseDate"]["label"][:10])
            self.assertTrue(actual_album.is_itunes_top)
            self.assertEquals(actual_album.itunes_price_dollars, decimal.Decimal(expected_entry["im:price"]["attributes"]["amount"]))
            self.assertEquals(actual_album.image_1_url, expected_entry["im:image"][0]["label"])
            actual_category = next(c for c in actual_categories if c.id == int(expected_entry["category"]["attributes"]["im:id"]))
            for attr in ("label", "scheme", "term"):
                self.assertEquals(getattr(actual_category, attr), expected_entry["category"]["attributes"][attr])

    def test_merge_top_albums_dethrones_others(self) -> None:
        # given
        feed_data = self.feed_boilerplate.copy()
        feed_data["feed"]["entry"].append(self._entry_boilerplate((("im:name", "label"), "should be top")))
        feed = ITunesFeed(lambda: json.dumps(feed_data))

        test_category = ITunesCategoryFactory.make("test")
        AlbumFactory(name="will be dethroned", is_itunes_top=True, itunes_category=test_category)

        # when
        feed.download_and_merge_top_albums()

        # then
        self.assertEquals(Album.objects.all().count(), 2)
        self.assertEquals(ITunesCategory.objects.all().count(), 2)
        for actual_album in Album.objects.all():
            self.assertEquals(actual_album.name == "should be top", actual_album.is_itunes_top)

    def _entry_boilerplate(self, *args, random_id=True) -> dict:
        """
        Pass pairs of (("keys", "to", "select"), value), e.g.: _entry_boilerplate((("im:name", "label"), "New Name")
        """
        result = copy.deepcopy(self.sample_feed_contents["feed"]["entry"][0])
        if random_id:
            result["id"]["attributes"]["im:id"] = str(random.randint(1_000_000, 2_000_000))

        for keys, value in args:
            ref = result
            for index, key in enumerate(keys):
                if index == len(keys) - 1:
                    ref[key] = value
                else:
                    ref = ref[key]

        return result
