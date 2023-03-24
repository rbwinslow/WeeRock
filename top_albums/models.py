import re

from django.db import models


RE_FIELD_NAME = re.compile(r"^(?!object)[a-z][a-z\d_]+$")


class ITunesCategory(models.Model):
    id = models.IntegerField(primary_key=True)
    label = models.CharField(blank=False, max_length=255)
    term = models.CharField(blank=False, max_length=255)
    scheme = models.URLField()


class Album(models.Model):
    """
    Assumptions made in boiling down the schema from the iTunes RSS "topalbums" feed:

    - Apple's ID values are unique and eternal.
    - .title always equals .im:name.label + " - " + .im:artist.label.
    - Albums never have more than three images.
    - The "rel" and "type" characteristics of links never change (always "alternate" and "text/html," respectively).
    - Prices are always USD.
    - Either the URL in .id.label is always equal to the one in .link.attributes.href, or it's not something we need anyway.

    Images are denormalized because I think the appearance of flexibility in the RSS/JSON schema obscures what I
    suspect (based on limited evidence) is the fixed three-image shape of iTunes album feeds (and this is a model of
    iTunes feed albums, not "albums" in the abstract). Rather than designing this model and all higher layers that
    depend on it around a non-YAGNI assumption that we might encounter albums with more than three images later on, it
    would be better to just ignore fourth-and-beyond images if we ever encounter them, and design our own features
    around the evident three-image case. Also, there would be no one-to-many appeal in this relation, were it
    normalized, in contrast with iTunes categories. (Allowing for fewer than three is easy, by making these fields
    NULL-able.)

    Cascading deletion from ITunesCategory is explicitly disabled because we don't control categories and our feed
    doesn't tell us if the iTunes taxonomy has changed, so we foresee no meaningful deletion scenario (YAGNI).
    """

    id = models.IntegerField(primary_key=True, help_text="Value provided by iTunes RSS feed")
    name = models.CharField(blank=False, max_length=255)
    artist = models.CharField(blank=False, max_length=255)
    artist_url = models.URLField(null=True)
    release_date = models.DateField()
    track_count = models.IntegerField()
    rights = models.CharField(blank=False, max_length=511)

    is_itunes_top = models.BooleanField(default=True)
    itunes_category = models.ForeignKey("ITunesCategory", on_delete=models.DO_NOTHING)
    itunes_link = models.URLField()
    itunes_price_dollars = models.DecimalField(decimal_places=2, max_digits=6)

    image_1_url = models.URLField(null=True)
    image_1_height = models.IntegerField(null=True)
    image_2_url = models.URLField(null=True)
    image_2_height = models.IntegerField(null=True)
    image_3_url = models.URLField(null=True)
    image_3_height = models.IntegerField(null=True)

    def serialize(self):
        data = {
            k: getattr(self, k) for k in filter(
                lambda attr: bool(RE_FIELD_NAME.match(attr)) and not callable(getattr(self, attr)),
                dir(self)
            )
        }

        for stringify in ("itunes_price_dollars", "release_date"):
            data[stringify] = str(getattr(self, stringify))

        data["itunes_category_id"] = self.itunes_category.id
        data["itunes_category_term"] = self.itunes_category.term
        del data["itunes_category"]

        return data
