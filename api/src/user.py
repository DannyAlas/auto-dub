from unicodedata import name
from api_auth import USER_AUTH, ADMIN_AUTH
from settings import Order
import datetime
import json
class USER:
    def __init__(self, token):
        self.user_auth = USER_AUTH(token)
        self.user = self.user_auth.user

        self.db = self.user_auth.user_db
        self.bucket = self.user_auth.user_store

    def create_download_url(self, path, exp_time: datetime.timedelta=datetime.timedelta(minutes=15)):
        """Creates download url for file in storage
        
        Parameters
            path (str): 
                path to file in storage
        
        Returns
            str:
                download url
        """
        # ensure the first part of the path is the user id
        if path.split("/")[0] != self.user.uid:
            raise Exception("Invalid path, must start with user id")
        
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
            self.order_ref = self.db.collection("orders").document(order.order_id)
        except:
            raise Exception("Error initializing order")

        try:
            self.order_ref.set({
                    f"dubbing_settings": json.loads(order.settings.json()),
                    f"dubbing_instances": [json.loads(instance.json()) for instance in order.dubbing_instances],
                }, merge=True)

            return self.order_ref.get().to_dict()
        except:
            raise Exception("Error setting order settings")
    
    def upload_translated_srt(self, file, order_id, language):
        """Uploads translated srt file to storage and updates order in db
        
        Parameters
            file (str): 
                path to file
            order_id (str): 
                order id
            language (str): 
                language of translation in DEEPL format
        
        Returns
            dict:
                translated_srts: dict of languages and their srt file paths
        
        Raises
            Exception:
                No order info set
                Error updating order
                Error uploading file to storage
        """
        if self.order_ref == None:
            raise Exception("No order info set")

        # update order
        try:
            self.order_ref.set({
                f"translated_srts": {language: f"{self.user.uid}/orders/{order_id}/srt/{language}.srt"}
            }, merge=True)
        except:
            raise Exception("Error updating order")
        
        # upload to storage
        try:
            blob = self.bucket.blob(f"{self.user.uid}/orders/{order_id}/srt/{language}.srt")
            blob.upload_from_filename(file)
        except:
            self.order_ref.set({
                f"translated_srts": {language: "Failed to upload to storage"}
            }, merge=True)
            raise Exception("Error uploading file to storage")
    
        return self.order_ref.get().to_dict().get("translated_srts")



