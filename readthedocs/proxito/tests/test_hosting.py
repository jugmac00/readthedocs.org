"""Test hosting views."""

import json
from pathlib import Path

import django_dynamic_fixture as fixture
import pytest
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from readthedocs.builds.constants import LATEST
from readthedocs.builds.models import Build, Version
from readthedocs.projects.constants import PRIVATE, PUBLIC
from readthedocs.projects.models import Feature, Project


@override_settings(
    PRODUCTION_DOMAIN="readthedocs.org",
    PUBLIC_DOMAIN="dev.readthedocs.io",
    PUBLIC_DOMAIN_USES_HTTPS=True,
    GLOBAL_ANALYTICS_CODE=None,
    RTD_ALLOW_ORGANIZATIONS=False,
)
@pytest.mark.proxito
class TestReadTheDocsConfigJson(TestCase):
    def setUp(self):
        self.user = fixture.get(User, username="testuser")
        self.user.set_password("testuser")
        self.user.save()

        self.project = fixture.get(
            Project,
            slug="project",
            name="project",
            language="en",
            privacy_level=PUBLIC,
            external_builds_privacy_level=PUBLIC,
            repo="https://github.com/readthedocs/project",
            programming_language="words",
            single_version=False,
            users=[self.user],
            main_language_project=None,
            project_url="http://project.com",
        )

        for tag in ("tag", "project", "test"):
            self.project.tags.add(tag)

        self.project.versions.update(
            privacy_level=PUBLIC,
            built=True,
            active=True,
            type="tag",
            identifier="a1b2c3",
        )
        self.version = self.project.versions.get(slug=LATEST)
        self.build = fixture.get(
            Build,
            project=self.project,
            version=self.version,
            commit="a1b2c3",
            length=60,
            state="finished",
            success=True,
        )

    def _get_response_dict(self, view_name, filepath=None):
        filepath = filepath or __file__
        filename = Path(filepath).absolute().parent / "responses" / f"{view_name}.json"
        return json.load(open(filename))

    def _normalize_datetime_fields(self, obj):
        obj["projects"]["current"]["created"] = "2019-04-29T10:00:00Z"
        obj["projects"]["current"]["modified"] = "2019-04-29T12:00:00Z"
        obj["builds"]["current"]["created"] = "2019-04-29T10:00:00Z"
        obj["builds"]["current"]["finished"] = "2019-04-29T10:01:00Z"
        return obj

    def test_get_config_v0(self):
        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/en/latest/",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200
        assert self._normalize_datetime_fields(r.json()) == self._get_response_dict(
            "v0"
        )

    def test_get_config_v1(self):
        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/en/latest/",
                "api-version": "1.0.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200
        assert r.json() == self._get_response_dict("v1")

    def test_get_config_unsupported_version(self):
        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/en/latest/",
                "api-version": "2.0.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 400
        assert r.json() == self._get_response_dict("v2")

    def test_disabled_addons_via_feature_flags(self):
        fixture.get(
            Feature,
            projects=[self.project],
            feature_id=Feature.ADDONS_ANALYTICS_DISABLED,
        )
        fixture.get(
            Feature,
            projects=[self.project],
            feature_id=Feature.ADDONS_EXTERNAL_VERSION_WARNING_DISABLED,
        )
        fixture.get(
            Feature,
            projects=[self.project],
            feature_id=Feature.ADDONS_NON_LATEST_VERSION_WARNING_DISABLED,
        )
        fixture.get(
            Feature,
            projects=[self.project],
            feature_id=Feature.ADDONS_DOC_DIFF_DISABLED,
        )
        fixture.get(
            Feature,
            projects=[self.project],
            feature_id=Feature.ADDONS_FLYOUT_DISABLED,
        )
        fixture.get(
            Feature,
            projects=[self.project],
            feature_id=Feature.ADDONS_SEARCH_DISABLED,
        )
        fixture.get(
            Feature,
            projects=[self.project],
            feature_id=Feature.ADDONS_HOTKEYS_DISABLED,
        )

        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/en/latest/",
                "client-version": "0.6.0",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200
        assert r.json()["addons"]["analytics"]["enabled"] is False
        assert r.json()["addons"]["external_version_warning"]["enabled"] is False
        assert r.json()["addons"]["non_latest_version_warning"]["enabled"] is False
        assert r.json()["addons"]["doc_diff"]["enabled"] is False
        assert r.json()["addons"]["flyout"]["enabled"] is False
        assert r.json()["addons"]["search"]["enabled"] is False
        assert r.json()["addons"]["hotkeys"]["enabled"] is False

    def test_non_latest_version_warning_versions(self):
        fixture.get(
            Version,
            project=self.project,
            privacy_level=PRIVATE,
            slug="private",
            verbose_name="private",
            built=True,
            active=True,
        )
        fixture.get(
            Version,
            project=self.project,
            privacy_level=PUBLIC,
            slug="public-built",
            verbose_name="public-built",
            built=True,
            active=True,
        )
        fixture.get(
            Version,
            project=self.project,
            privacy_level=PUBLIC,
            slug="public-not-built",
            verbose_name="public-not-built",
            built=False,
            active=True,
        )

        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/en/latest/",
                "client-version": "0.6.0",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200

        expected = ["latest", "public-built"]
        assert r.json()["addons"]["non_latest_version_warning"]["versions"] == expected

    def test_flyout_versions(self):
        fixture.get(
            Version,
            project=self.project,
            privacy_level=PRIVATE,
            slug="private",
            verbose_name="private",
            built=True,
            active=True,
        )
        fixture.get(
            Version,
            project=self.project,
            privacy_level=PUBLIC,
            slug="public-built",
            verbose_name="public-built",
            built=True,
            active=True,
        )
        fixture.get(
            Version,
            project=self.project,
            privacy_level=PUBLIC,
            slug="public-not-built",
            verbose_name="public-not-built",
            built=False,
            active=True,
        )
        fixture.get(
            Version,
            project=self.project,
            privacy_level=PUBLIC,
            slug="hidden",
            verbose_name="hidden",
            built=False,
            hidden=True,
            active=True,
        )

        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/en/latest/",
                "client-version": "0.6.0",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200

        expected = [
            {"slug": "latest", "url": "https://project.dev.readthedocs.io/en/latest/"},
            {
                "slug": "public-built",
                "url": "https://project.dev.readthedocs.io/en/public-built/",
            },
        ]
        assert r.json()["addons"]["flyout"]["versions"] == expected

    def test_flyout_translations(self):
        fixture.get(
            Project,
            slug="translation",
            main_language_project=self.project,
            language="ja",
        )

        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/en/latest/",
                "client-version": "0.6.0",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200

        expected = [
            {"slug": "ja", "url": "https://project.dev.readthedocs.io/ja/latest/"},
        ]
        assert r.json()["addons"]["flyout"]["translations"] == expected

    def test_flyout_downloads(self):
        fixture.get(
            Version,
            project=self.project,
            privacy_level=PUBLIC,
            slug="offline",
            verbose_name="offline",
            built=True,
            has_pdf=True,
            has_epub=True,
            has_htmlzip=True,
            active=True,
        )

        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/en/offline/",
                "client-version": "0.6.0",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200

        expected = [
            {
                "name": "PDF",
                "url": "//project.dev.readthedocs.io/_/downloads/en/offline/pdf/",
            },
            {
                "name": "HTML",
                "url": "//project.dev.readthedocs.io/_/downloads/en/offline/htmlzip/",
            },
            {
                "name": "Epub",
                "url": "//project.dev.readthedocs.io/_/downloads/en/offline/epub/",
            },
        ]
        assert r.json()["addons"]["flyout"]["downloads"] == expected

    def test_flyout_single_version_project(self):
        self.version.has_pdf = True
        self.version.has_epub = True
        self.version.has_htmlzip = True
        self.version.save()

        self.project.single_version = True
        self.project.save()

        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/",
                "client-version": "0.6.0",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200

        expected = []
        assert r.json()["addons"]["flyout"]["versions"] == expected

        expected = [
            {
                "name": "PDF",
                "url": "//project.dev.readthedocs.io/_/downloads/en/latest/pdf/",
            },
            {
                "name": "HTML",
                "url": "//project.dev.readthedocs.io/_/downloads/en/latest/htmlzip/",
            },
            {
                "name": "Epub",
                "url": "//project.dev.readthedocs.io/_/downloads/en/latest/epub/",
            },
        ]
        assert r.json()["addons"]["flyout"]["downloads"] == expected

    def test_project_subproject(self):
        subproject = fixture.get(
            Project, slug="subproject", repo="https://github.com/readthedocs/subproject"
        )
        self.project.add_subproject(subproject)

        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/projects/subproject/en/latest/",
                "client-version": "0.6.0",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200

        assert r.json()["projects"]["current"]["id"] == subproject.pk
        assert r.json()["projects"]["current"]["slug"] == subproject.slug
        assert (
            r.json()["projects"]["current"]["repository"]["url"]
            == "https://github.com/readthedocs/subproject"
        )

    def test_flyout_subproject_urls(self):
        translation = fixture.get(
            Project,
            slug="translation",
            language="es",
            repo="https://github.com/readthedocs/subproject",
        )
        translation.versions.update(
            built=True,
            active=True,
        )
        subproject = fixture.get(
            Project, slug="subproject", repo="https://github.com/readthedocs/subproject"
        )
        self.project.add_subproject(subproject)
        subproject.translations.add(translation)
        subproject.save()

        fixture.get(Version, slug="v1", project=subproject)
        fixture.get(Version, slug="v2.3", project=subproject)
        subproject.versions.update(
            privacy_level=PUBLIC,
            built=True,
            active=True,
            hidden=False,
        )

        r = self.client.get(
            reverse("proxito_readthedocs_docs_addons"),
            {
                "url": "https://project.dev.readthedocs.io/projects/subproject/en/latest/",
                "client-version": "0.6.0",
                "api-version": "0.1.0",
            },
            secure=True,
            headers={
                "host": "project.dev.readthedocs.io",
            },
        )
        assert r.status_code == 200

        expected_versions = [
            {
                "slug": "latest",
                "url": "https://project.dev.readthedocs.io/projects/subproject/en/latest/",
            },
            {
                "slug": "v1",
                "url": "https://project.dev.readthedocs.io/projects/subproject/en/v1/",
            },
            {
                "slug": "v2.3",
                "url": "https://project.dev.readthedocs.io/projects/subproject/en/v2.3/",
            },
        ]
        assert r.json()["addons"]["flyout"]["versions"] == expected_versions

        expected_translations = [
            {
                "slug": "es",
                "url": "https://project.dev.readthedocs.io/projects/subproject/es/latest/",
            },
        ]
        assert r.json()["addons"]["flyout"]["translations"] == expected_translations
