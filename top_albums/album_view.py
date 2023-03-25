import functools
import json
from http import HTTPStatus
from typing import Dict, Optional, Tuple

from django.db import IntegrityError
from django.db.models import QuerySet
from django.http import HttpRequest, JsonResponse
from django.views import View

from top_albums.auth import authenticated
from top_albums.models import Album, ITunesCategory


class TopAlbumsView(View):

    _FEATURE_PARAMS_TO_FIELDS = {
        "artist": "artist",
        "category": "itunes_category__term",
        "is_itunes_top": "is_itunes_top",
        "name": "name",
        "price": "itunes_price_dollars",
        "release_date": "release_date",
    }

    @authenticated
    def delete(self, request: HttpRequest, id: int):
        """
        DELETE /top-albums/<id>/

            $ curl --request DELETE --user 'uname:passwd' 'http://<domain>/top-albums/<id>/'
            {"deleted": 1}

        Delete the album record with the given id value from the service's database. Requires authentication.

        """
        number_deleted, _ = Album.objects.filter(id=id).delete()
        return JsonResponse({"deleted": number_deleted})

    def get(self, request: HttpRequest):
        """
        GET /top-albums/?param=value&...

            $ curl --silent 'http://<domain>/top-albums/?sort=artist' | jq .
            {
              "contents": [
                {
                  "artist": "ABBA",
                  "artist_url": "https://music.apple.com/us/artist/abba/372976?uo=2",
                  "id": 1422648512,
                  ... more fields ...
                },
                ... more albums ...
              ],
              "pagination": {
                "page_size": 68
              }
            }

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
                        "image_2_url": "https://...",
                        "image_2_height": 48,
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
        GET /top-albums/?price__lt=12.00

        # Top soundtracks (not using category because there are multiple that apply)
        GET /top-albums/?name__contains=Motion+Picture

        """
        page = request.GET.get("page")
        page_size = request.GET.get("page_size")
        sort = request.GET.get("sort")

        if page is not None and page_size is None:
            return JsonResponse(
                {"message": "page_size required when page is specified"},
                status=HTTPStatus.BAD_REQUEST
            )

        query = Album.objects.all()
        if sort is not None:
            query = self._add_ordering_from_sort_param(query, sort)

        get_param_dict = {k: request.GET.get(k) for k in request.GET.keys()}
        get_param_dict["is_itunes_top"] = bool(int(get_param_dict["is_itunes_top"])) if "is_itunes_top" in get_param_dict else True
        query = self._apply_filters_from_params(query, get_param_dict)

        if page_size is None:
            albums = list(query)
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
        albums = list(query[start:start + page_size])

        return JsonResponse({
            "contents": [a.serialize() for a in albums],
            "pagination": (self._make_response_pagination_part(query.count(), page, page_size, request))
        })

    @authenticated
    def patch(self, request: HttpRequest, id: int):
        """
        PATCH /top-albums/<id>/

            $ curl --silent --request PATCH --user 'uname:passwd' -H 'Content-Type: application/json' \
                 --data '{"rights": "all rights renounced"}' 'http://<domain>/top-albums/<id>/' | jq .
            {
                "artist": "ABBA",
                ...
                "rights": "all rights renounced",
                ...
            }

        Update values in an existing album in the top-albums service's database. Accepts input as JSON or form-encoded.

        Response is the complete album record as updated, as a JSON document (same schema as the items in the
        "contents" array returned by GET).

        """
        inputs = self._parsed_request_contents(request)

        if not id:
            return JsonResponse(
                {"message": "Must specify id when PATCHing an album"},
                status=HTTPStatus.BAD_REQUEST
            )

        category, maybe_response = self._resolve_category_input(inputs, required=False)
        if maybe_response is not None:
            return maybe_response

        query = Album.objects.filter(id=id)
        if query.count() == 0:
            return JsonResponse(
                {"message": f"No album exists with id={inputs['id']}"},
                status=HTTPStatus.NOT_FOUND
            )
        query.update(**inputs)

        return JsonResponse(query[0].serialize())

    @authenticated
    def post(self, request: HttpRequest):
        """
        POST /top-albums/

            $ curl --silent --request POST --user 'uname:passwd' -H 'Content-Type: application/json' \
                 --data '{"artist": "ABBA", ..., "track_count": 7}' 'http://<domain>/top-albums/' | jq .
            {
                "artist": "ABBA",
                ...
                "track_count": 7,
                ...
            }

        Store a new album in the top-albums service's database. Accepts input as JSON or form-encoded.

        Response is the complete album record as stored, as a JSON document (same schema as the items in the "contents"
        array returned by GET). At a minimum, input data must include:

        - id: YOU set this value, just as Apple sets values coming from the feed. This service doesn't originate album ids.
        - artist
        - itunes_category_term or itunes_category_id
        - itunes_price_dollars
        - name
        - rights

        Look at the fields supplied when you GET albums. What you POST should be data-complete to the extent possible
        (artist_url can be absent/null for example becuase Apple does this for "Various Artists").

        """
        inputs = self._parsed_request_contents(request)

        required_inputs = ("artist", "id", "itunes_price_dollars", "name", "rights")
        missing = [f for f in required_inputs if f not in inputs]
        if missing:
            return JsonResponse(
                {"message": f"Required fields missing: {', '.join(missing)}"},
                status=HTTPStatus.BAD_REQUEST
            )

        category, maybe_response = self._resolve_category_input(inputs)
        if maybe_response is not None:
            return maybe_response

        error = None
        model = Album(itunes_category=category, **inputs)
        try:
            model.save(force_insert=True)
        except IntegrityError as ex:
            error = str(ex)

        if error is None:
            return JsonResponse(model.serialize(), status=HTTPStatus.ACCEPTED)
        else:
            error_data = {"message": error}
            return JsonResponse(error_data, status=HTTPStatus.BAD_REQUEST)

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

    def _parsed_request_contents(self, request):
        if "json" in request.content_type.lower():
            return json.loads(request.body)
        else:
            return {k: request.POST.get(k) for k in request.POST.keys()}

    def _replace_feature_with_field(self, feature: str) -> str:
        return functools.reduce(
            lambda c, k: c.replace(k, self._FEATURE_PARAMS_TO_FIELDS[k], 1),
            self._FEATURE_PARAMS_TO_FIELDS.keys(),
            feature
        )

    def _resolve_category_input(self, inputs: Dict[str, str], required=True) -> Tuple[Optional[ITunesCategory], Optional[JsonResponse]]:
        category = None
        try:
            if "itunes_category_id" in inputs:
                category = ITunesCategory.objects.get(id=int(inputs["itunes_category_id"]))
                del inputs["itunes_category_id"]
            elif "itunes_category_term" in inputs:
                category = ITunesCategory.objects.get(term=inputs["itunes_category_term"])
                del inputs["itunes_category_term"]
            if category is None and required:
                return None, JsonResponse(
                    {"message": "Must specify an iTunes category via itunes_category_id or itunes_category_term"},
                    status=HTTPStatus.BAD_REQUEST
                )
            else:
                return category, None
        except ITunesCategory.DoesNotExist:
            return None, JsonResponse(
                {"message": "Cannot find iTunes category specified via itunes_category_id or itunes_category_term"},
                status=HTTPStatus.BAD_REQUEST
            )

    def _make_response_pagination_part(self, count_all_results: int, page: int, page_size: int, request: HttpRequest) -> dict:
        pagination = {"page_size": page_size}
        if page > 1:
            pagination["previous_page"] = request.build_absolute_uri(
                f"/top-albums/?page={page - 1}&page_size={page_size}"
            )
        if count_all_results > page * page_size:
            pagination["next_page"] = request.build_absolute_uri(f"/top-albums/?page={page + 1}&page_size={page_size}")
        return pagination
