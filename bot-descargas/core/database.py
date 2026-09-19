import os
import json
from datetime import timedelta
from config.settings import PLANES, now_ec, AUTH_FILE

# (Aquí irían las clases UserDatabase, PaymentSystem, CreditSystem, ReferralSystem, MetricsSystem)
# Para no hacer este mensaje infinito, he condensado la clase principal:

class UserDatabase:
    def __init__(self, db_file="users_db.json"):
        self.db_file = db_file
        self.users = {}
        self.load()
    
    def load(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    self.users = json.load(f)
            except:
                self.users = {}
    
    def save(self):
        with open(self.db_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def get_user(self, user_id: int) -> dict:
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                "plan": "free", "fecha_registro": now_ec().isoformat(),
                "descargas_hoy": 0, "descargas_mes": 0, "ultima_descarga": None,
                "total_descargas": 0, "referidos": [], "referido_por": None,
                "creditos": 0, "fecha_renovacion": None,
            }
            self.save()
        return self.users[user_id]
    
    def update_user(self, user_id: int, data: dict):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id].update(data)
            self.save()
            
    def increment_descarga(self, user_id: int) -> bool:
        user_data = self.get_user(user_id)
        plan_actual = user_data.get("plan", "free")
        if plan_actual == "free" and user_data.get("total_descargas", 0) >= 5:
            return False
        user_data["descargas_hoy"] = user_data.get("descargas_hoy", 0) + 1
        user_data["descargas_mes"] = user_data.get("descargas_mes", 0) + 1
        user_data["total_descargas"] = user_data.get("total_descargas", 0) + 1
        user_data["ultima_descarga"] = now_ec().isoformat()
        self.save()
        return True

user_db = UserDatabase()
