import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore, storage
import os
from dotenv import load_dotenv

load_dotenv()

# Use a service account.
cred = credentials.Certificate({
    "type": os.environ.get("FIREBASE_TYPE"),
    "project_id": os.environ.get("FIREBASE_PROJECT_ID"),
    "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.environ.get("FIREBASE_PRIVATE_KEY").replace(r'\n', '\n'),
    "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
    "auth_uri": os.environ.get("FIREBASE_AUTH_URI"),
    "token_uri": os.environ.get("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.environ.get("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_X509_CERT_URL"),
    "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET")
})

app = firebase_admin.initialize_app(cred)

db = firestore.client()

# for some reason the storageBucket is not loaded with the app so load here
bucket = storage.bucket(name=os.environ.get("FIREBASE_STORAGE_BUCKET"))

print(bucket.list_blobs())
