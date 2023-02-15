import os
from multiprocessing import AuthenticationError

import deepl
from dotenv import load_dotenv
from firebase_admin import _apps, auth, credentials, firestore, initialize_app
from google.cloud import storage
from google.oauth2 import service_account
from googleapiclient.discovery import build
from httplib2 import Authentication
from pydantic import PrivateAttr

# load enviorment variables
load_dotenv()

CREDS = {
    "type": os.environ.get("TYPE"),
    "project_id": os.environ.get("PROJECT_ID"),
    "private_key_id": os.environ.get("PRIVATE_KEY_ID"),
    "private_key": os.environ.get("PRIVATE_KEY").replace(r"\n", "\n"),  # type: ignore
    "client_email": os.environ.get("CLIENT_EMAIL"),
    "client_id": os.environ.get("CLIENT_ID"),
    "auth_uri": os.environ.get("AUTH_URI"),
    "token_uri": os.environ.get("TOKEN_URI"),
    "auth_provider_x509_cert_url": os.environ.get("AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.environ.get("CLIENT_X509_CERT_URL"),
    "storageBucket": os.environ.get("STORAGE_BUCKET"),
}


def google_auth(api_key: str):

    # GOOGLE_TTS_API = build('texttospeech', 'v1', developerKey=api_key)
    GOOGLE_TRANSLATE_API = build("translate", "v3beta1", developerKey=api_key)

    return GOOGLE_TRANSLATE_API


class Singleton(type):
    def __init__(self, *args, **kwargs):
        self.__instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        if self.__instance is None:
            self.__instance = super().__call__(*args, **kwargs)
            return self.__instance
        else:
            return self.__instance


class DEEPL_AUTH:
    """DEEPL API Authentication Class"""

    def __init__(self):
        self.deeplApiKey = os.environ.get("DEEPL_API_KEY")
        if self.deeplApiKey:
            self.deepl_auth_object = deepl.Translator(self.deeplApiKey)
        else:
            raise Exception("DEEPL_API_KEY not found in .env file")


class ADMIN_AUTH(metaclass=Singleton):
    """Admin Authentication Class. This class is a singleton and should only be initialized once."""

    def __init__(self):
        self.fb_creds = credentials.Certificate(CREDS)
        self.sa_creds = service_account.Credentials.from_service_account_info(CREDS)

        self.firebase = self._firebase()

    @property
    def STORAGE_CLIENT(self):
        return storage.Client(credentials=self.sa_creds)

    def app_bucket(self):
        return self.STORAGE_CLIENT.bucket(f'{CREDS.get("storageBucket")}')

    def _firebase(self):
        # Initialize the app with a service account, granting admin privileges, only if not already initialized
        if not len(_apps):
            return initialize_app(credential=self.fb_creds)
        elif len(_apps) == 1:
            return _apps
        else:
            raise Exception("Error: Multiple Apps Initialized")

    @property
    def _firestore_client(self):
        return firestore.client()


class USER_AUTH:
    """User Authentication Class

    Parameters:
        uid (str): User ID

    Returns:
        User Object
    """

    def __init__(self, token):
        # verify token
        self.user = self.get_user_from_token(token)
        self.uid = self.user.uid # type: ignore

        # initialize admin auth
        self._admin_auth = ADMIN_AUTH()

    def verify_user_token(self, id_token) -> dict:
        """Verify User Token

        Parameters:
            id_token (str): User Token

        Returns:
            user (dict): parsed JWT token

        Raises:
            ValueError: If `id_token` is a not a string or is empty.
            InvalidIdTokenError: If `id_token` is not a valid Firebase ID token.
            ExpiredIdTokenError: If the specified `id_token` has expired.
            RevokedIdTokenError: If the `id_token` has been revoked.
            CertificateFetchError: If an error occurs while fetching the public key certificates required to verify the `id_token`.
            UserDisabledError: If the corresponding user record is disabled.
        """
        try:
            user: dict = auth.verify_id_token(id_token, check_revoked=True)
            return user
        except Exception as e:
            raise AuthenticationError(e)

    def get_user_from_token(self, token) -> auth.UserRecord:
        """
        Parameters:
            token (str): User Token

        Returns:
            User Object

        Raises:
            Exception: if user can't be verified
        """

        # check that the firebase app is initialized
        if not len(_apps):
            ADMIN_AUTH().firebase

        try:
            uid = self.verify_user_token(token).get("uid")
        except Exception as e:
            raise AuthenticationError(e)

        return auth.get_user(uid)

    @property
    def user_db(self) -> firestore.firestore.DocumentReference:
        """The Users Firestore Document Reference"""
        return self._admin_auth._firestore_client.collection("users").document(self.uid)

    @property
    def user_store(self) -> storage.Bucket:
        """The Users Storage Bucket"""
        return self._admin_auth.app_bucket()
