import json
from datetime import date, timedelta
from unittest.mock import Mock, patch

import requests
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from kyc.mapping import map_verification
from kyc.models import Account

API_KEY = "test-didit-key"
WORKFLOW_ID = "11111111-2222-3333-4444-555555555555"
SESSION_ID = "4c5c7f3a-1f82-4f3b-8d8e-1a8d2d2f9b7a"
VERIFY_URL = "https://verify.didit.me/session/abc"

CONFIGURED = override_settings(
    DIDIT_API_KEY=API_KEY,
    DIDIT_WORKFLOW_ID=WORKFLOW_ID,
    PUBLIC_APP_URL="http://localhost:4200",
)

VALID_BODY = {
    "firstName": "Awa",
    "lastName": "Diop",
    "email": "awa@example.com",
    "phone": "+221770000000",
    "dateOfBirth": "1992-04-12",
    "consent": True,
}


def make_account(**overrides):
    values = {
        "first_name": "Awa",
        "last_name": "Diop",
        "email": "awa@example.com",
        "phone": "+221770000000",
        "date_of_birth": date(1992, 4, 12),
        "consent": True,
        "status": "Not Started",
    }
    values.update(overrides)
    return Account.objects.create(**values)


def didit_response(status, body):
    response = Mock()
    response.status_code = status
    response.json.return_value = body
    return response


def decision_payload(**overrides):
    payload = {
        "status": "Approved",
        "session_url": VERIFY_URL,
        "session_token": "secret-session-token",
        "features": ["ID_VERIFICATION", "LIVENESS", "FACE_MATCH", "AML"],
        "id_verifications": [
            {
                "status": "Approved",
                "document_type": "Identity Card",
                "full_name": "Awa Diop",
                "nationality": "SEN",
                "date_of_birth": "1992-04-12",
                "document_number": "CAA0001234",
                "expiration_date": "2031-06-02",
                "portrait_image": "https://media.example/portrait.jpg",
                "front_image": "https://media.example/front.jpg",
                "back_image": "https://media.example/back.jpg",
                "mrz": {"document_number": "CAA0001234"},
                "barcodes": ["raw-barcode"],
                "warnings": [
                    {
                        "short_description": f"alerte-{index}",
                        "long_description": "NE_PAS_RENVOYER_IMAGE",
                    }
                    for index in range(7)
                ],
            }
        ],
        "liveness_checks": [
            {
                "status": "Approved",
                "score": 98.2,
                "reference_image": "https://media.example/reference.jpg",
                "video_url": "https://media.example/liveness.mp4",
            }
        ],
        "face_matches": [
            {
                "status": "Approved",
                "score": 94.1,
                "source_image": "https://media.example/source.jpg",
                "target_image": "https://media.example/target.jpg",
            }
        ],
        "aml_screenings": [
            {
                "status": "Approved",
                "total_hits": 2,
                "hits": [{"id": "secret-hit", "caption": "personne"}],
            }
        ],
    }
    payload.update(overrides)
    return payload


class MappingTests(TestCase):
    def test_decision_is_reduced_to_the_frontend_contract(self):
        verification = map_verification(decision_payload())

        self.assertEqual(
            verification,
            {
                "status": "Approved",
                "document": {
                    "status": "Approved",
                    "type": "Identity Card",
                    "fullName": "Awa Diop",
                    "nationality": "SEN",
                    "dateOfBirth": "1992-04-12",
                    "documentNumber": "••••••1234",
                    "expirationDate": "2031-06-02",
                    "warnings": [f"alerte-{index}" for index in range(5)],
                },
                "liveness": {"status": "Approved", "score": 98.2, "present": True},
                "faceMatch": {"status": "Approved", "score": 94.1, "present": True},
                "accountReady": True,
                "workflowGap": None,
                "aml": {"status": "Approved", "totalHits": 2},
            },
        )
        encoded = json.dumps(verification)
        self.assertNotIn("portrait", encoded)
        self.assertNotIn("mrz", encoded)
        self.assertNotIn("barcode", encoded)
        self.assertNotIn("secret-hit", encoded)
        self.assertNotIn("NE_PAS_RENVOYER_IMAGE", encoded)
        self.assertNotIn("CAA0001234", encoded)

    def test_missing_blocks_stay_null_and_account_is_not_ready(self):
        verification = map_verification({"status": "In Progress"})

        self.assertIsNone(verification["document"])
        self.assertIsNone(verification["liveness"])
        self.assertIsNone(verification["faceMatch"])
        self.assertIsNone(verification["aml"])
        self.assertIsNone(verification["workflowGap"])
        self.assertFalse(verification["accountReady"])

    def test_workflow_gap_explains_missing_steps_in_french(self):
        gap = map_verification({"status": "Not Started", "features": "AML"})
        self.assertEqual(
            gap["workflowGap"],
            "Le workflow Didit publié ne contient pas la vérification d'identité "
            "(ID Verification), la détection de présence (Liveness) et la "
            "correspondance faciale (Face Match). Ajoutez ces étapes dans la "
            "console Didit.",
        )

        partial = map_verification(
            {"status": "Not Started", "features": ["ID_VERIFICATION", "FACE_MATCH"]}
        )
        self.assertEqual(
            partial["workflowGap"],
            "Le workflow Didit publié ne contient pas la détection de présence "
            "(Liveness). Ajoutez cette étape dans la console Didit.",
        )

        complete = map_verification(
            {
                "status": "Approved",
                "features": "ID_VERIFICATION,LIVENESS,FACE_MATCH",
            }
        )
        self.assertIsNone(complete["workflowGap"])

    def test_account_ready_requires_three_approvals(self):
        payload = decision_payload()
        payload["liveness_checks"][0]["status"] = "Declined"
        self.assertFalse(map_verification(payload)["accountReady"])


@CONFIGURED
class AccountApiTests(APITestCase):
    def test_health_reports_configuration(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "diditConfigured": True})

    @override_settings(DIDIT_API_KEY="", DIDIT_WORKFLOW_ID="")
    def test_health_is_false_without_key_and_workflow(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.json()["diditConfigured"], False)

    def test_cors_allows_the_angular_origin(self):
        response = self.client.get("/api/health/", HTTP_ORIGIN="http://localhost:4200")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:4200")

    def test_validation_errors_use_a_message(self):
        response = self.client.post(
            "/api/accounts/",
            {
                "firstName": "A",
                "lastName": "Diop",
                "email": "pas-un-email",
                "phone": "77",
                "dateOfBirth": "12-04-1992",
                "consent": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"message"})
        message = response.json()["message"]
        self.assertIn("prénom", message)
        self.assertIn("e-mail", message)
        self.assertIn("téléphone", message)
        self.assertIn("AAAA-MM-JJ", message)
        self.assertIn("consentement", message)
        self.assertEqual(Account.objects.count(), 0)

    @override_settings(DIDIT_API_KEY="", DIDIT_WORKFLOW_ID="pas-un-uuid")
    @patch("kyc.didit.requests.request")
    def test_create_requires_key_and_workflow_uuid(self, request_mock):
        response = self.client.post("/api/accounts/", VALID_BODY, format="json")
        self.assertEqual(response.status_code, 503)
        message = response.json()["message"]
        self.assertIn("DIDIT_API_KEY", message)
        self.assertIn("DIDIT_WORKFLOW_ID", message)
        self.assertEqual(Account.objects.count(), 0)
        request_mock.assert_not_called()

    @patch("kyc.didit.requests.request")
    def test_create_opens_a_didit_session_without_leaking_secrets(self, request_mock):
        request_mock.return_value = didit_response(
            201,
            {
                "session_id": SESSION_ID,
                "url": VERIFY_URL,
                "status": "Not Started",
                "session_token": "secret-session-token",
            },
        )

        response = self.client.post("/api/accounts/", VALID_BODY, format="json")

        self.assertEqual(response.status_code, 201)
        body = response.json()
        account = body["account"]
        self.assertEqual(body["verificationUrl"], VERIFY_URL)
        self.assertEqual(account["firstName"], "Awa")
        self.assertEqual(account["lastName"], "Diop")
        self.assertEqual(account["dateOfBirth"], "1992-04-12")
        self.assertEqual(account["status"], "Not Started")
        self.assertEqual(account["sessionId"], SESSION_ID)
        self.assertEqual(account["verificationUrl"], VERIFY_URL)
        self.assertIsNone(account["verification"])
        self.assertIsNone(account["verificationError"])
        self.assertRegex(account["createdAt"], r"^\d{4}-\d{2}-\d{2}T.+Z$")
        encoded = response.content.decode()
        self.assertNotIn("secret-session-token", encoded)
        self.assertNotIn(API_KEY, encoded)
        self.assertNotIn("session_token", encoded)
        self.assertNotIn("first_name", encoded)

        sent = request_mock.call_args.kwargs["json"]
        self.assertEqual(sent["workflow_id"], WORKFLOW_ID)
        self.assertEqual(sent["callback"], "http://localhost:4200/verification")
        self.assertNotIn("?", sent["callback"])
        self.assertEqual(sent["callback_method"], "both")
        self.assertEqual(sent["language"], "fr")
        self.assertEqual(sent["contact_details"]["email"], "awa@example.com")
        self.assertFalse(sent["contact_details"]["send_notification_emails"])
        self.assertEqual(sent["expected_details"]["expected_document_types"], ["ID"])
        self.assertEqual(sent["metadata"]["source"], "ouverture-compte")
        self.assertEqual(sent["vendor_data"], account["id"])
        self.assertEqual(request_mock.call_args.kwargs["headers"]["x-api-key"], API_KEY)
        self.assertNotIn("x-api-key", sent)

    @patch("kyc.didit.requests.request")
    def test_create_returns_502_when_didit_omits_the_url(self, request_mock):
        request_mock.return_value = didit_response(
            201,
            {"session_id": SESSION_ID, "session_token": "secret-session-token"},
        )
        response = self.client.post("/api/accounts/", VALID_BODY, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertIn("URL", response.json()["message"])
        self.assertNotIn("secret-session-token", response.content.decode())
        self.assertEqual(Account.objects.count(), 0)

    @patch("kyc.didit.requests.request")
    def test_create_hides_the_api_key_when_didit_echoes_it(self, request_mock):
        request_mock.return_value = didit_response(401, {"detail": f"clé refusée {API_KEY}"})
        response = self.client.post("/api/accounts/", VALID_BODY, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(API_KEY, response.content.decode())
        self.assertEqual(Account.objects.count(), 0)

    @patch("kyc.didit.requests.request")
    def test_list_does_not_call_didit_and_is_newest_first(self, request_mock):
        older = make_account(email="old@example.com", session_id="session-old", status="In Progress")
        newer = make_account(email="new@example.com", session_id="session-new", status="In Progress")
        Account.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=1))

        response = self.client.get("/api/accounts/")

        self.assertEqual(response.status_code, 200)
        emails = [item["email"] for item in response.json()["accounts"]]
        self.assertEqual(emails, ["new@example.com", "old@example.com"])
        request_mock.assert_not_called()
        self.assertEqual(newer.email, "new@example.com")

    @patch("kyc.didit.requests.request")
    def test_detail_refreshes_until_the_status_is_terminal(self, request_mock):
        account = make_account(session_id=SESSION_ID, status="In Progress")
        request_mock.return_value = didit_response(200, decision_payload())

        response = self.client.get(f"/api/accounts/{account.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["account"]
        self.assertEqual(payload["status"], "Approved")
        self.assertTrue(payload["verification"]["accountReady"])
        self.assertEqual(payload["verification"]["document"]["documentNumber"], "••••••1234")
        self.assertIsNone(payload["verificationError"])
        stored = Account.objects.get(pk=account.id)
        self.assertNotIn("portrait_image", json.dumps(stored.verification))
        self.assertNotIn("hits", json.dumps(stored.verification))

        request_mock.reset_mock()
        second = self.client.get(f"/api/accounts/{account.id}/")
        self.assertEqual(second.status_code, 200)
        request_mock.assert_not_called()

    @patch("kyc.didit.requests.request")
    def test_failed_refresh_keeps_the_last_known_dossier(self, request_mock):
        previous = {
            "status": "In Progress",
            "document": None,
            "liveness": None,
            "faceMatch": None,
            "accountReady": False,
            "workflowGap": None,
            "aml": None,
        }
        account = make_account(
            session_id=SESSION_ID,
            status="In Progress",
            verification=previous,
            verification_url=VERIFY_URL,
        )
        request_mock.side_effect = requests.ConnectionError("réseau indisponible")

        response = self.client.get(f"/api/accounts/{account.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["account"]
        self.assertEqual(payload["verification"], previous)
        self.assertEqual(payload["status"], "In Progress")
        self.assertEqual(payload["verificationUrl"], VERIFY_URL)
        self.assertEqual(payload["verificationError"], "Impossible de récupérer la décision Didit.")
        self.assertNotIn("réseau indisponible", response.content.decode())
        self.assertTrue(Account.objects.filter(pk=account.id).exists())

    def test_unknown_account_is_404(self):
        response = self.client.get("/api/accounts/11111111-1111-1111-1111-111111111111/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"message": "Dossier introuvable."})

    @patch("kyc.didit.requests.request")
    def test_verification_lookup_attaches_vendor_data(self, request_mock):
        account = make_account(status="Not Started")
        request_mock.return_value = didit_response(
            200,
            decision_payload(vendor_data=str(account.id), status="In Review"),
        )

        response = self.client.get(f"/api/verifications/{SESSION_ID}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["account"]
        self.assertEqual(payload["id"], str(account.id))
        self.assertEqual(payload["sessionId"], SESSION_ID)
        self.assertEqual(payload["status"], "In Review")
        self.assertEqual(payload["verificationUrl"], VERIFY_URL)
        self.assertEqual(payload["verification"]["aml"], {"status": "Approved", "totalHits": 2})

    @patch("kyc.didit.requests.request")
    def test_verification_without_a_dossier_is_404(self, request_mock):
        request_mock.return_value = didit_response(404, {"detail": "introuvable"})
        response = self.client.get(f"/api/verifications/{SESSION_ID}/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "Dossier introuvable.")

    def test_post_does_not_require_a_csrf_token(self):
        response = Client(enforce_csrf_checks=True).post(
            "/api/accounts/",
            data=json.dumps({**VALID_BODY, "consent": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotEqual(response.status_code, 403)

    def test_public_routes_do_not_use_session_authentication(self):
        from kyc.views import AccountListCreateView

        self.assertEqual(AccountListCreateView.authentication_classes, [])
        field_names = {field.name for field in Account._meta.fields}
        self.assertNotIn("api_key", field_names)
        self.assertNotIn("didit_api_key", field_names)

    def test_swagger_ui_is_available(self):
        page = self.client.get("/swagger/")
        schema = self.client.get("/api/schema/", {"format": "json"})
        self.assertEqual(page.status_code, 200)
        self.assertIn("swagger", page.content.decode().lower())
        self.assertEqual(schema.status_code, 200)
        body = schema.json()
        self.assertIn("/api/accounts/", body["paths"])
        self.assertIn("/api/health/", body["paths"])
        self.assertIn("/api/verifications/{session_id}/", body["paths"])
