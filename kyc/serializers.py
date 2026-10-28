import re

from rest_framework import serializers

_PHONE = re.compile(r"[0-9+\s().\-]+")


class AccountCreateSerializer(serializers.Serializer):
    firstName = serializers.CharField(
        error_messages={
            "required": "Le prénom est obligatoire.",
            "blank": "Le prénom doit contenir entre 2 et 80 caractères.",
        }
    )
    lastName = serializers.CharField(
        error_messages={
            "required": "Le nom est obligatoire.",
            "blank": "Le nom doit contenir entre 2 et 80 caractères.",
        }
    )
    email = serializers.EmailField(
        error_messages={
            "required": "L'adresse e-mail est obligatoire.",
            "blank": "L'adresse e-mail est obligatoire.",
            "invalid": "L'adresse e-mail n'est pas valide.",
        }
    )
    phone = serializers.CharField(
        error_messages={
            "required": "Le téléphone est obligatoire.",
            "blank": "Le téléphone doit contenir entre 8 et 20 caractères.",
        }
    )
    dateOfBirth = serializers.DateField(
        input_formats=["%Y-%m-%d"],
        error_messages={
            "required": "La date de naissance est obligatoire.",
            "invalid": "La date de naissance doit être au format AAAA-MM-JJ.",
        },
    )
    consent = serializers.BooleanField(
        error_messages={
            "required": "Le consentement est requis pour ouvrir le compte.",
            "invalid": "Le consentement est requis pour ouvrir le compte.",
        }
    )

    def validate_firstName(self, value):
        return _person_name(value, "Le prénom")

    def validate_lastName(self, value):
        return _person_name(value, "Le nom")

    def validate_email(self, value):
        return value.strip()

    def validate_phone(self, value):
        phone = value.strip()
        if not 8 <= len(phone) <= 20 or _PHONE.fullmatch(phone) is None:
            raise serializers.ValidationError(
                "Le téléphone doit contenir entre 8 et 20 caractères "
                "parmi les chiffres, +, espaces, parenthèses, points et tirets."
            )
        return phone

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Le consentement est requis pour ouvrir le compte."
            )
        return value


class ErrorSerializer(serializers.Serializer):
    message = serializers.CharField()


class HealthSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    diditConfigured = serializers.BooleanField()


class DocumentSerializer(serializers.Serializer):
    status = serializers.CharField(allow_blank=True)
    type = serializers.CharField(allow_blank=True)
    fullName = serializers.CharField(allow_blank=True)
    nationality = serializers.CharField(allow_blank=True)
    dateOfBirth = serializers.CharField(allow_blank=True)
    documentNumber = serializers.CharField(allow_blank=True)
    expirationDate = serializers.CharField(allow_blank=True)
    warnings = serializers.ListField(child=serializers.CharField())


class CheckSerializer(serializers.Serializer):
    status = serializers.CharField(allow_blank=True)
    score = serializers.FloatField(allow_null=True)
    present = serializers.BooleanField()


class AmlSerializer(serializers.Serializer):
    status = serializers.CharField(allow_blank=True)
    totalHits = serializers.IntegerField()


class VerificationSerializer(serializers.Serializer):
    status = serializers.CharField(allow_blank=True)
    document = DocumentSerializer(allow_null=True)
    liveness = CheckSerializer(allow_null=True)
    faceMatch = CheckSerializer(allow_null=True)
    accountReady = serializers.BooleanField()
    workflowGap = serializers.CharField(allow_null=True)
    aml = AmlSerializer(allow_null=True)


class AccountSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    firstName = serializers.CharField()
    lastName = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    dateOfBirth = serializers.DateField()
    status = serializers.CharField()
    sessionId = serializers.CharField(allow_null=True)
    verificationUrl = serializers.CharField(allow_null=True)
    verification = VerificationSerializer(allow_null=True)
    verificationError = serializers.CharField(allow_null=True)
    createdAt = serializers.DateTimeField()
    updatedAt = serializers.DateTimeField()


class AccountListSerializer(serializers.Serializer):
    accounts = AccountSerializer(many=True)


class AccountEnvelopeSerializer(serializers.Serializer):
    account = AccountSerializer()


class AccountCreatedSerializer(serializers.Serializer):
    account = AccountSerializer()
    verificationUrl = serializers.CharField()


def _person_name(value, label):
    name = value.strip()
    if not 2 <= len(name) <= 80:
        raise serializers.ValidationError(
            f"{label} doit contenir entre 2 et 80 caractères."
        )
    return name
