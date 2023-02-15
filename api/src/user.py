from unicodedata import name
from api_auth import USER_AUTH, ADMIN_AUTH


class USER:
    def __init__(self, token):
        self.user_auth = USER_AUTH(token)
        self.user = self.user_auth.user

        self.db = self.user_auth.user_db
        self.bucket = self.user_auth.user_store


    def set_order_info(self, order_id):
        self.order_ref = self.db.collection("orders").document(order_id)
        return self.order_ref.get().to_dict()
    
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


"""
auth user
get order 
check params - params dictate translation, transcriptiopn, etc

"""
