import datetime
import json
import logging
from sys import stdout
from unicodedata import name

from api_auth import USER_AUTH
from settings import Order

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
    datefmt="%d/%b/%Y %H:%M:%S",
    stream=stdout,
)


class USER:
    def __init__(self, token):
        self.user_auth = USER_AUTH(token)
        self.user = self.user_auth.user

        self.db = self.user_auth.user_db
        self.bucket = self.user_auth.user_store

    def create_download_url(
        self, path, exp_time: datetime.timedelta = datetime.timedelta(minutes=15)
    ):
        """Creates download url for file in storage

        Parameters
            path (str):
                path to file in storage

        Returns
            str:
                download url
        """
        logging.debug(f"EXP TIME: {exp_time}, PATH: {path}")
        # ensure the first part of the path is the user id
        if path.split("/")[0] != self.user.uid:
            raise Exception("Invalid path, must start with user id")

        logging.debug("CREATING DOWNLOAD URL")
        return self.bucket.blob(path).generate_signed_url(
            version="v4",
            expiration=exp_time,
            method="GET",
        )

    def initialize_db_order(self, order: Order):
        """Initializes order in db and storage

        Parameters
            order (Order):
                Order object

        Returns
            dict:
                order info

        Raises
            Exception:
                Error initializing order
        """
        try:
            logging.debug("INITIALIZING ORDER")
            self.order_ref = self.db.collection("orders").document(order.order_id)
        except:
            raise Exception("Error initializing order reference")

        try:
            self.order_ref.set(
                {
                    f"dubbing_settings": json.loads(order.settings.json()),
                    f"dubbing_instances": [
                        json.loads(instance.json())
                        for instance in order.dubbing_instances
                    ],
                },
                merge=True,
            )
            logging.debug("ORDER SET")
            return self.order_ref.get().to_dict()
        except:
            raise Exception("Error setting order settings")

    def upload_translation(self, file, order_id, language):
        """Uploads translated order file to storage and updates order in db

        Parameters
        ----------
            data (bytes):
                file data
            order_id (str):
                order id
            language (str):
                language of translation in DEEPL format

        Returns
        -------
            bool:
                True if successful

        Raises
        ------
            Exception: No order info set
            Exception: Error updating order
            Exception: Error uploading file to storage
        """
        if self.order_ref == None:
            raise Exception("No order info set")

        # update order
        try:
            self.order_ref.set(
                {
                    f"translations": {
                        language: f"{self.user.uid}/orders/{order_id}/translations/{language}.json"
                    }
                },
                merge=True,
            )
            logging.debug("ORDER UPDATED")
        except:
            raise Exception("Error updating order")

        # upload to storage
        try:
            blob = self.bucket.blob(
                f"{self.user.uid}/orders/{order_id}/translations/{language}.json"
            )
            logging.debug(f"BLOB: {blob}")
            blob.upload_from_string(file)
            # blob.upload_from_filename(file)
            logging.debug("FILE UPLOADED")
        except:
            self.order_ref.set(
                {f"translations": {language: "Failed to upload to storage"}},
                merge=True,
            )
            raise Exception("Error uploading file to storage")

        return True
    
    def upload_translated_audio(self, data, order_id, language):
        """Uploads translated order file to storage and updates order in db
        
        Parameters
        ----------
            data (dict):
                file data {file_name: file_data}
            order_id (str):
                order id
            language (str):
                language of translation in DEEPL format
            
        """
        if self.order_ref == None:
            raise Exception("No order info set")
        
        try:
            self.order_ref.set(
                {
                    f"dubs": {
                        language: f"{self.user.uid}/orders/{order_id}/dubs/{language}"
                    }
                },
                merge=True,
            )
            logging.debug("ORDER UPDATED")
        except:
            raise Exception("Error updating order")


        for file_name, file_data in data.items():
            # upload to storage
            try:
                blob = self.bucket.blob(
                    f"{self.user.uid}/orders/{order_id}/dubs/{language}/{file_name}"
                )
                logging.debug(f"BLOB: {blob}")
                blob.upload_from_string(file_data, content_type='audio/mp3')

                logging.debug("FILE UPLOADED")
            except:
                self.order_ref.set(
                    {f"dubs": {language: "Failed to upload to storage"}},
                    merge=True,
                )
                raise Exception("Error uploading file to storage")

        return True
        
