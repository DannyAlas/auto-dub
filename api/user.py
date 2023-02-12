from api_auth import USER_AUTH

class USER:

    def __init__(self, token):
        self.user_auth = USER_AUTH(token)
        self.user = self.user_auth.user

        self.db = self.user_auth.user_db
        self.store = self.user_auth.user_store
        self.user = self.user_auth.user

    def set_order_info(self, order_id):
        order_ref = self.db.collection("orders").document(order_id)
        self.order_ref = order_ref.get().to_dict()
