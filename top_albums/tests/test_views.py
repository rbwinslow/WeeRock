import json
import unittest.mock
from typing import Tuple

from unittest.mock import Mock

from django.db import connections, OperationalError
from django.test import TestCase
from http import HTTPStatus

from top_albums.factories import AlbumFactory, ITunesCategoryFactory


class HealthCheckTests(TestCase):

    def test_health_happy_path(self) -> None:
        # when
        response = self.client.get("/")

        # then
        self.assertEquals(response.status_code, HTTPStatus.OK)
        data = json.loads(response.content.decode("UTF-8"))
        self.assertIsInstance(data, dict)
        self.assertIn("database", data)
        self.assertTrue(data["database"])

    def test_database_unhealthy(self) -> None:
        # given
        broken_cursor = Mock(side_effect=OperationalError)

        # when
        with unittest.mock.patch.object(connections["default"], "cursor", broken_cursor):
            response = self.client.get("/")

        # then
        self.assertEquals(response.status_code, HTTPStatus.OK)
        data = json.loads(response.content.decode("UTF-8"))
        self.assertIsInstance(data, dict)
        self.assertIn("database", data)
        self.assertFalse(data["database"])


class AlbumsAPITests(TestCase):

    def setUp(self) -> None:
        self.test_category = ITunesCategoryFactory.make("test")

    def test_get_all_top_albums(self) -> None:
        # given
        expected_albums = [
            AlbumFactory(itunes_category=self.test_category),
            AlbumFactory(itunes_category=self.test_category)
        ]
        AlbumFactory(is_itunes_top=False, itunes_category=self.test_category)

        # when
        response = self.client.get("/top-albums/")

        # then
        self.assertEquals(response.status_code, HTTPStatus.OK)
        data = json.loads(response.content.decode("UTF-8"))
        self.assertIsInstance(data, dict)
        contents, pagination = self._assert_response_has_contents_and_pagination(response)
        self.assertEquals(pagination.get("page_size", None), len(expected_albums))
        self.assertNotIn("previous_page", pagination)
        self.assertNotIn("next_page", pagination)
        self.assertEquals(len(contents), len(expected_albums))
        actual_ids = [a["id"] for a in contents]
        for expected_id in [a.id for a in expected_albums]:
            self.assertIn(expected_id, actual_ids)

    def test_get_top_albums_paginated(self) -> None:
        # given
        expected_page_size = 10
        for _ in range(30):
            AlbumFactory(itunes_category=self.test_category)

        # when (page 1)
        response = self.client.get(f"/top-albums/?page_size={expected_page_size}")

        # then (page 1)
        self.assertEquals(response.status_code, HTTPStatus.OK)
        contents, pagination = self._assert_response_has_contents_and_pagination(response)
        self.assertEquals(len(contents), expected_page_size)
        self.assertEquals(pagination.get("page_size", None), expected_page_size)
        self.assertNotIn("previous_page", pagination)
        next_page = pagination.get("next_page", "(next_page missing)")
        self.assertRegexpMatches(next_page, rf"^http.+/top-albums/\?.*page=2.*$")

        # when (page 2)
        response = self.client.get(next_page)

        # then (page 2)
        self.assertEquals(response.status_code, HTTPStatus.OK)
        contents, pagination = self._assert_response_has_contents_and_pagination(response)
        self.assertEquals(len(contents), expected_page_size)
        self.assertEquals(pagination.get("page_size", None), expected_page_size)
        previous_page = pagination.get("previous_page", "(previous_page missing)")
        self.assertRegexpMatches(previous_page, rf"^http.+/top-albums/\?.*page=1.*$")
        next_page = pagination.get("next_page", "(next_page missing)")
        self.assertRegexpMatches(next_page, rf"^http.+/top-albums/\?.*page=3.*$")

        # when (page 3)
        response = self.client.get(next_page)

        # then (page 3)
        self.assertEquals(response.status_code, HTTPStatus.OK)
        contents, pagination = self._assert_response_has_contents_and_pagination(response)
        self.assertEquals(pagination.get("page_size", None), expected_page_size)
        previous_page = pagination.get("previous_page", "(previous_page missing)")
        self.assertRegexpMatches(previous_page, rf"^http.+/top-albums/\?.*page=2.*$")
        self.assertNotIn("next_page", pagination)

    def test_get_page_without_page_size_is_illegal(self) -> None:
        # when
        response = self.client.get("/top-albums/?page=2")

        # then
        self.assertEquals(response.status_code, HTTPStatus.BAD_REQUEST)

    def _assert_response_has_contents_and_pagination(self, response) -> Tuple[list, dict]:
        data = json.loads(response.content.decode("UTF-8"))
        self.assertIsInstance(data, dict)

        contents = data.get("contents", None)
        pagination = data.get("pagination", None)

        self.assertIsInstance(contents, list)
        self.assertIsInstance(pagination, dict)

        return contents, pagination