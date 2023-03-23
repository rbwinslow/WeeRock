import functools
from http import HTTPStatus
from typing import Dict

from django.db.models import QuerySet
from django.http import HttpRequest, JsonResponse
from django.views import View

from top_albums.models import Album


class TopAlbumsView(View):

    _FEATURE_PARAMS_TO_FIELDS = {
        "artist": "artist",
        "category": "itunes_category__term",
        "name": "name",
        "price": "itunes_price_dollars",
        "release_date": "release_date",
    }

    def get(self, request: HttpRequest):
        """
        GET /top-albums/?param=value&...

        Get the current list of top albums on iTunes, optionally paginated.

        Specify page_size (and optionally page) to paginate, then use previous_page and next_page URLs in response.

        ===== URL parameters =====
            - page: 1-based page number for paginated access (NOTE: if specified, then page_size also required)
            - page_size: number of albums per page for paginated access (if page not specified, defaults to 1)
            - sort: features to order by, comma-delimited; e.g., "sort=category,name" sorts by itunes_category_term
                    first and name second (supported features: artist, category, name, price and release_date).
                    Precede feature names with a minus sign to signify descending order for that feature:
                    "sort=-price" goes from most expensive to least.
            - <feature>[__op]: a feature to filter results with, represented Django-style, as just a name by itself
                    (in which case, we filter for albums for which the feature is equal to the given value) or in
                    combination with a double-underscore operand from Django's repertoire:
                    https://docs.djangoproject.com/en/4.1/ref/models/querysets/#id4
                    You can also precede such an __op with "__not" to exclude rather than filter (or just "__not" by
                    itself to exclude by equality). The names you can use here are the same as the ones accepted by the
                    sort param.

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

        ===== Samples =====

        # All top albums, sorted first by artist name, then newest to oldest for that artist:
        GET /top-albums/?sort=artist,-release_date

        # Top Rock albums, sorted by artist and excluding anthologies:
        GET /top-albums/?sort=artist&category=Rock&artist__not=Various+Artists

        # Top albums cheaper than $12.00
        GET  /top-albums/?price__lt=12.00

        """
        page = request.GET.get("page")
        page_size = request.GET.get("page_size")
        sort = request.GET.get("sort")

        if page is not None and page_size is None:
            return JsonResponse(
                {"message": "page_size required when page is specified"},
                status=HTTPStatus.BAD_REQUEST
            )

        all_top = Album.objects.filter(is_itunes_top=True)
        if sort is not None:
            all_top = self._add_ordering_from_sort_param(all_top, sort)

        get_param_dict = {k: request.GET.get(k) for k in request.GET.keys()}
        all_top = self._apply_filters_from_params(all_top, get_param_dict)

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
        # OFFSET and LIMIT to the SQL query.
        albums = list(all_top[start:start + page_size])

        return JsonResponse({
            "contents": [a.serialize() for a in albums],
            "pagination": (self._make_response_pagination_part(all_top.count(), page, page_size, request))
        })

    def _add_ordering_from_sort_param(self, queryset: QuerySet, sort: str) -> QuerySet:
        return queryset.order_by(*[self._replace_feature_with_field(clause) for clause in sort.split(",")])

    def _apply_filters_from_params(self, queryset: QuerySet, get_params: Dict[str, str]) -> QuerySet:
        feature_keys = self._FEATURE_PARAMS_TO_FIELDS.keys()

        for param in get_params.keys():
            if any(param.startswith(k) for k in feature_keys):
                field = self._replace_feature_with_field(param)
                value = get_params[param]
                if "__not" in field:
                    queryset = queryset.exclude(**{field.replace("__not", ""): value})
                else:
                    queryset = queryset.filter(**{field: value})

        return queryset

    def _replace_feature_with_field(self, feature: str) -> str:
        return functools.reduce(
            lambda c, k: c.replace(k, self._FEATURE_PARAMS_TO_FIELDS[k], 1),
            self._FEATURE_PARAMS_TO_FIELDS.keys(),
            feature
        )

    def _make_response_pagination_part(self, count_all_results: int, page: int, page_size: int, request: HttpRequest) -> dict:
        pagination = {"page_size": page_size}
        if page > 1:
            pagination["previous_page"] = request.build_absolute_uri(
                f"/top-albums/?page={page - 1}&page_size={page_size}")
        if count_all_results > page * page_size:
            pagination["next_page"] = request.build_absolute_uri(f"/top-albums/?page={page + 1}&page_size={page_size}")
        return pagination
