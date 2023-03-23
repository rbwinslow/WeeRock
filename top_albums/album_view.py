import json
from http import HTTPStatus

from django.http import HttpRequest, JsonResponse
from django.views import View

from top_albums.models import Album


class TopAlbumsView(View):

    def get(self, request: HttpRequest):
        """
        GET /top-albums/?param=value&...

        Get the current list of top albums on iTunes, optionally paginated.

        Specify page_size (and optionally page) to paginate, then use previous_page and next_page URLs in response.

        ===== URL parameters =====
            - page: 1-based page number for paginated access (NOTE: if specified, then page_size also required)
            - page_size: number of albums per page for paginated access (if page not specified, defaults to 1)

        ===== Response (JSON) =====
            The "previous_page" and "next_page" keys appear under pagination only when such (non-empty) pages exist.

            {
                "contents": [
                    {
                        "id": 1234567,
                        "name": "Album Name",
                        "artist": "Various Artists",
                        "artist_url": null,
                        "release_date": "1973-03-01",
                        "track_count": 10,
                        "rights": "all rights reserved",
                        "is_itunes_top": true,
                        "itunes_category_id": 123,
                        "itunes_category_term": "Difficult Listening",
                        "itunes_link": "https://...",
                        "itunes_price_dollars": "19.99",
                        "image_1_url": "https://...",
                        "image_1_height": 55,
                        ...
                        "image_3_url": "https://...",
                        "image_3_height": 32
                    },
                    ... more albums ...
                ],
                "pagination": {
                    "page_size": 10,
                    "previous_page": "http://...",
                    "next_page": "http://..."
                }
            }
        """
        page = request.GET.get("page")
        page_size = request.GET.get("page_size")

        if page is not None and page_size is None:
            return JsonResponse(
                {"message": "page_size required when page is specified"},
                status=HTTPStatus.BAD_REQUEST
            )

        all_top = Album.objects.filter(is_itunes_top=True)

        if page_size is None:
            albums = list(all_top)
            return JsonResponse({
                "contents": [a.serialize() for a in albums],
                "pagination": {"page_size": len(albums)}
            })

        page = 1 if page is None else int(page)
        page_size = int(page_size)
        start = (page - 1) * page_size
        # For the casual observer who may be concerned about inefficiency:
        # Django QuerySets are lazy (and meta-programmatic), so the actual effect of the indexed access here is to add
        # OFFSET & LIMIT to the SQL query.
        albums = list(all_top[start:start + page_size])

        pagination = {"page_size": len(albums)}
        if page > 1:
            pagination["previous_page"] = request.build_absolute_uri(f"/top-albums/?page={page-1}&page_size={page_size}")
        if all_top.count() > page * page_size:
            pagination["next_page"] = request.build_absolute_uri(f"/top-albums/?page={page+1}&page_size={page_size}")

        return JsonResponse({
            "contents": [a.serialize() for a in albums],
            "pagination": pagination
        })
