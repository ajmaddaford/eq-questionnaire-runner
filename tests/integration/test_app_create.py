import unittest
from uuid import UUID
from contextlib import contextmanager
from mock import patch

from flask import Flask, request
from flask_babel import Babel

from app.setup import create_app, EmulatorCredentials
from app.storage.datastore import DatastoreStorage
from app.storage.dynamodb import DynamodbStorage
from app.submitter.submitter import LogSubmitter, RabbitMQSubmitter, GCSSubmitter


class TestCreateApp(unittest.TestCase):  # pylint: disable=too-many-public-methods
    def setUp(self):
        self._setting_overrides = {}

    @contextmanager
    def override_settings(self):
        """ Required because although the settings are overriden on the application
        by passing _setting_overrides in, there are many funtions which use the
        imported settings object - this does not get the overrides merged in. This
        helper does that.

        Note - this is not very nice, however it's better than polluting the global
        settings.

        Returns a list of contexts."""
        patches = [
            patch("app.setup.settings.{}".format(k), v)
            for k, v in self._setting_overrides.items()
        ]
        for p in patches:
            p.start()
        yield patches
        for p in patches:
            p.stop()

    def test_returns_application(self):
        self.assertIsInstance(create_app(self._setting_overrides), Flask)

    def test_sets_content_length(self):
        self.assertGreater(
            create_app(self._setting_overrides).config["MAX_CONTENT_LENGTH"], 0
        )

    def test_enforces_secure_session(self):
        application = create_app(self._setting_overrides)
        self.assertTrue(application.secret_key)
        self.assertTrue(application.permanent_session_lifetime)
        self.assertTrue(application.session_interface)

        # This is derived from EQ_ENABLE_SECURE_SESSION_COOKIE which is false
        # when running tests
        self.assertFalse(application.config["SESSION_COOKIE_SECURE"])

    # localisation may not be used but is currently attached...
    def test_adds_i18n_to_application(self):
        babel = create_app(self._setting_overrides).babel  # pylint: disable=no-member
        self.assertIsInstance(babel, Babel)

    def test_adds_logging_of_request_ids(self):
        with patch("app.setup.logger") as logger:
            self._setting_overrides.update(
                {"EQ_DEV_MODE": True, "EQ_APPLICATION_VERSION": False}
            )
            application = create_app(self._setting_overrides)

            application.test_client().get("/")
            self.assertEqual(1, logger.new.call_count)
            _, kwargs = logger.new.call_args
            self.assertTrue(UUID(kwargs["request_id"], version=4))

    def test_adds_logging_of_span_and_trace(self):
        with patch("app.setup.logger") as logger:
            self._setting_overrides.update(
                {"EQ_DEV_MODE": True, "EQ_APPLICATION_VERSION": False}
            )
            application = create_app(self._setting_overrides)

            x_cloud_headers = {
                "X-Cloud-Trace-Context": "0123456789/0123456789012345678901;o=1"
            }
            application.test_client().get("/", headers=x_cloud_headers)

            self.assertEqual(1, logger.bind.call_count)
            _, kwargs = logger.bind.call_args
            self.assertTrue(kwargs["span"] == "0123456789012345678901")
            self.assertTrue(kwargs["trace"] == "0123456789")

    def test_enforces_secure_headers(self):
        self._setting_overrides["EQ_ENABLE_LIVE_RELOAD"] = False

        with create_app(self._setting_overrides).test_client() as client:
            headers = client.get(
                "/",
                headers={
                    "X-Forwarded-Proto": "https"
                },  # set protocal so that talisman sets HSTS headers
            ).headers

            self.assertEqual(
                "no-cache, no-store, must-revalidate", headers["Cache-Control"]
            )
            self.assertEqual("no-cache", headers["Pragma"])
            self.assertEqual(
                "max-age=31536000; includeSubDomains",
                headers["Strict-Transport-Security"],
            )
            self.assertEqual("DENY", headers["X-Frame-Options"])
            self.assertEqual("1; mode=block", headers["X-Xss-Protection"])
            self.assertEqual("nosniff", headers["X-Content-Type-Options"])

            csp_policy_parts = headers["Content-Security-Policy"].split("; ")
            self.assertIn("default-src 'self' https://cdn.ons.gov.uk", csp_policy_parts)
            self.assertIn(
                f"script-src 'self' https://cdn.ons.gov.uk https://www.googletagmanager.com 'unsafe-inline' 'unsafe-eval' 'nonce-{request.csp_nonce}'",
                csp_policy_parts,
            )
            self.assertIn(
                "style-src 'self' https://cdn.ons.gov.uk https://tagmanager.google.com https://fonts.googleapis.com 'unsafe-inline'",
                csp_policy_parts,
            )
            self.assertIn(
                "img-src 'self' data: https://cdn.ons.gov.uk https://www.google-analytics.com https://ssl.gstatic.com https://www.gstatic.com",
                csp_policy_parts,
            )
            self.assertIn(
                "font-src 'self' data: https://cdn.ons.gov.uk https://fonts.gstatic.com",
                csp_policy_parts,
            )
            self.assertIn(
                "frame-src https://www.googletagmanager.com", csp_policy_parts
            )
            self.assertIn(
                "connect-src 'self' https://cdn.ons.gov.uk https://cdn.eq.census-gcp.onsdigital.uk",
                csp_policy_parts,
            )

    # Indirectly covered by higher level integration
    # tests, keeping to highlight that create_app is where
    # it happens.
    def test_adds_blueprints(self):
        self.assertGreater(len(create_app(self._setting_overrides).blueprints), 0)

    def test_eq_submission_backend_not_set(self):
        # Given
        self._setting_overrides["EQ_SUBMISSION_BACKEND"] = ""

        # When
        with self.assertRaises(Exception) as ex:
            create_app(self._setting_overrides)

        # Then
        assert "Unknown EQ_SUBMISSION_BACKEND" in str(ex.exception)

    def test_adds_gcs_submitter_to_the_application(self):
        # Given
        self._setting_overrides["EQ_SUBMISSION_BACKEND"] = "gcs"
        self._setting_overrides["EQ_GCS_SUBMISSION_BUCKET_ID"] = "123"

        # When
        with patch("google.cloud.storage.Client"):
            application = create_app(self._setting_overrides)

        # Then
        assert isinstance(application.eq["submitter"], GCSSubmitter)

    def test_gcs_submitter_bucket_id_not_set_raises_exception(self):
        # Given
        self._setting_overrides["EQ_SUBMISSION_BACKEND"] = "gcs"

        # WHEN
        with self.assertRaises(Exception) as ex:
            create_app(self._setting_overrides)

        # Then
        assert "Setting EQ_GCS_SUBMISSION_BUCKET_ID Missing" in str(ex.exception)

    def test_adds_rabbit_submitter_to_the_application(self):
        # Given
        self._setting_overrides["EQ_SUBMISSION_BACKEND"] = "rabbitmq"
        self._setting_overrides["EQ_RABBITMQ_HOST"] = "host-1"
        self._setting_overrides["EQ_RABBITMQ_HOST_SECONDARY"] = "host-2"

        # When
        application = create_app(self._setting_overrides)

        # Then
        assert isinstance(application.eq["submitter"], RabbitMQSubmitter)

    def test_rabbit_submitter_host_not_set_raises_exception(self):
        # Given
        self._setting_overrides["EQ_SUBMISSION_BACKEND"] = "rabbitmq"
        self._setting_overrides["EQ_RABBITMQ_HOST"] = ""

        # When
        with self.assertRaises(Exception) as ex:
            create_app(self._setting_overrides)

        # Then
        assert "Setting EQ_RABBITMQ_HOST Missing" in str(ex.exception)

    def test_rabbit_submitter_secondary_host_not_set_raises_exception(self):
        # Given
        self._setting_overrides["EQ_SUBMISSION_BACKEND"] = "rabbitmq"
        self._setting_overrides["EQ_RABBITMQ_HOST"] = "host-1"
        self._setting_overrides["EQ_RABBITMQ_HOST_SECONDARY"] = ""

        # When
        with self.assertRaises(Exception) as ex:
            create_app(self._setting_overrides)

        # Then
        assert "Setting EQ_RABBITMQ_HOST_SECONDARY Missing" in str(ex.exception)

    def test_defaults_to_adding_the_log_submitter_to_the_application(self):
        # When
        application = create_app(self._setting_overrides)

        # Then
        assert isinstance(application.eq["submitter"], LogSubmitter)

    def test_emulator_credentials(self):
        creds = EmulatorCredentials()

        self.assertTrue(creds.valid)

        with self.assertRaises(RuntimeError):
            creds.refresh(None)

    def test_setup_datastore(self):
        self._setting_overrides["EQ_STORAGE_BACKEND"] = "datastore"

        with patch("google.cloud.datastore.Client"):
            application = create_app(self._setting_overrides)

        self.assertIsInstance(application.eq["storage"], DatastoreStorage)

    def test_setup_dynamodb(self):
        self._setting_overrides["EQ_STORAGE_BACKEND"] = "dynamodb"

        application = create_app(self._setting_overrides)

        self.assertIsInstance(application.eq["storage"], DynamodbStorage)

    def test_invalid_storage(self):
        self._setting_overrides["EQ_STORAGE_BACKEND"] = "invalid"

        with self.assertRaises(Exception):
            create_app(self._setting_overrides)
