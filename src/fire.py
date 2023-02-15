import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os
from google.oauth2 import service_account
from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

# Use a service account.
creds = {
    "type": os.environ.get("TYPE"),
    "project_id": os.environ.get("PROJECT_ID"),
    "private_key_id": os.environ.get("PRIVATE_KEY_ID"),
    "private_key": os.environ.get("PRIVATE_KEY").replace(r'\n', '\n'), # type: ignore
    "client_email": os.environ.get("CLIENT_EMAIL"),
    "client_id": os.environ.get("CLIENT_ID"),
    "auth_uri": os.environ.get("AUTH_URI"),
    "token_uri": os.environ.get("TOKEN_URI"),
    "auth_provider_x509_cert_url": os.environ.get("AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.environ.get("CLIENT_X509_CERT_URL"),
    "storageBucket": os.environ.get("STORAGE_BUCKET")
}


app = firebase_admin.initialize_app(credentials.Certificate(creds))

db = firestore.client()

sa_creds = service_account.Credentials.from_service_account_info(creds)
store = storage.Client(credentials=sa_creds)

# for some reason the storageBucket is not loaded with the app so load here
bucket = store.bucket(os.environ.get("STORAGE_BUCKET"))

def upload_srt(file, file_name):
    blob = bucket.blob(file_name)
    blob.upload_from_file(file)

with open(r"C:\dev\projects\test-app\testing\test.srt", "rb") as f:
    upload_srt(f, "test1.srt")