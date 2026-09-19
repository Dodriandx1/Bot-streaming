"""
Base de Datos con MongoDB (Migración completa)
────────────────────────────────────────────────
Reemplaza los archivos .json por MongoDB.
Mantiene la misma API pública para no romper el bot.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional
import pymongo
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config.settings import MONGO_URI, PLANES, now_ec


# ═══════════════════════════════════════════════════════════════════
#  CONEXIÓN CENTRAL
# ═══════════════════════════════════════════════════════════════════

class Database:
    _client: Optional[MongoClient] = None
    _db = None
    _connected: bool = False

    @classmethod
    def connect(cls) -> bool:
        if cls._connected:
            return True
        if not MONGO_URI:
            print("[db] ⚠️ MONGO_URI no configurada. Modo offline.")
            return False
        try:
            cls._client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            cls._client.admin.command("ping")
            cls._db = cls._client["bot_descargas"]
            cls._connected = True
            cls._create_indexes()
            print("[db] ✓ Conectado a MongoDB")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"[db] ❌ Error conectando a MongoDB: {e}")
            cls._connected = False
            return False

    @classmethod
    def _create_indexes(cls):
        try:
            cls._db.users.create_index([("user_id", ASCENDING)], unique=True)
            cls._db.users.create_index([("plan", ASCENDING)])
            cls._db.users.create_index([("total_descargas", ASCENDING)])
            cls._db.pending_payments.create_index([("user_id", ASCENDING)], unique=True)
            cls._db.telefonos.create_index([("phone_hash", ASCENDING)], unique=True)
            print("[db] ✓ Índices creados")
        except Exception as e:
            print(f"[db] ⚠️ Error creando índices: {e}")

    @classmethod
    def get_collection(cls, name: str):
        if not cls._connected:
            cls.connect()
        if cls._db is None:
            raise RuntimeError("No hay conexión a MongoDB.")
        return cls._db[name]

    @classmethod
    def is_connected(cls) -> bool:
        return cls._connected


# ═══════════════════════════════════════════════════════════════════
#  USER DATABASE
# ═══════════════════════════════════════════════════════════════════

class UserDatabase:
    def __init__(self):
        self._cache = {}
        self._loaded = False

    def _load_cache(self):
        if self._loaded:
            return
        try:
            col = Database.get_collection("users")
            for doc in col.find({}, {"user_id": 1, "plan": 1}):
                self._cache[str(doc["user_id"])] = doc
            self._loaded = True
            print(f"[db] ✓ {len(self._cache)} usuarios en caché")
        except Exception as e:
            print(f"[db] error caché: {e}")
            self._loaded = True

    def _default_user(self, user_id: int) -> dict:
        return {
            "user_id": user_id,
            "plan": "free",
            "fecha_registro": now_ec().isoformat(),
            "descargas_hoy": 0,
            "descargas_mes": 0,
            "total_descargas": 0,
            "ultima_descarga": None,
            "ultima_descarga_date": None,
            "referidos": [],
            "referido_por": None,
            "creditos": 0,
            "fecha_renovacion": None,
            "usos_por_plataforma": {},
            "username": None,
            "first_name": None,
            "telefono_verificado": False,
            "multicuenta_sospechosa": False,
            "multicuenta_de": None,
            "ultimo_uso_tipo": None,
            "ultimo_uso_fecha": None,
        }

    def get_user(self, user_id: int) -> dict:
        uid_str = str(user_id)
        if not Database.is_connected():
            if uid_str not in self._cache:
                self._cache[uid_str] = self._default_user(user_id)
            return self._cache[uid_str]
        try:
            col = Database.get_collection("users")
            doc = col.find_one({"user_id": user_id})
            if not doc:
                doc = self._default_user(user_id)
                col.insert_one(doc)
            doc.pop("_id", None)
            self._cache[uid_str] = doc
            return doc
        except Exception as e:
            print(f"[db] error get_user: {e}")
            return self._default_user(user_id)

    def update_user(self, user_id: int, data: dict):
        uid_str = str(user_id)
        try:
            if Database.is_connected():
                col = Database.get_collection("users")
                col.update_one({"user_id": user_id}, {"$set": data}, upsert=True)
            if uid_str not in self._cache:
                self._cache[uid_str] = self._default_user(user_id)
            self._cache[uid_str].update(data)
        except Exception as e:
            print(f"[db] error update_user: {e}")

    def increment_descarga(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        plan = user.get("plan", "free")
        if plan == "free" and user.get("total_descargas", 0) >= 5:
            return False
        try:
            if Database.is_connected():
                col = Database.get_collection("users")
                col.update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"descargas_hoy": 1, "descargas_mes": 1, "total_descargas": 1},
                        "$set": {
                            "ultima_descarga": now_ec().isoformat(),
                            "ultima_descarga_date": now_ec().date().isoformat(),
                        },
                    },
                )
            return True
        except Exception as e:
            print(f"[db] error increment: {e}")
            return False

    def get_limites(self, user_id: int) -> dict:
        user = self.get_user(user_id)
        plan_actual = user.get("plan", "free")
        if plan_actual.startswith("creditos_") or plan_actual not in PLANES:
            plan_actual = "free"
        plan = PLANES.get(plan_actual, PLANES["free"])
        return {
            "plan": plan_actual,
            "plan_nombre": plan["nombre"],
            "descargas_hoy": user.get("descargas_hoy", 0),
            "limite_total": 5 if plan_actual == "free" else "Ilimitado",
            "descargas_mes": user.get("descargas_mes", 0),
            "limite_mensual": plan.get("limite_mensual", 50),
            "total_descargas": user.get("total_descargas", 0),
            "calidad_maxima": plan.get("calidad_maxima", "480p"),
            "torrent": plan.get("torrent_soportado", False),
            "publicidad": plan.get("publicidad", True),
            "creditos": user.get("creditos", 0),
        }

    def reset_contadores_diarios(self):
        hoy = now_ec().date().isoformat()
        try:
            if Database.is_connected():
                col = Database.get_collection("users")
                col.update_many(
                    {"ultima_descarga_date": {"$ne": hoy}},
                    {"$set": {"descargas_hoy": 0, "ultima_descarga_date": hoy}},
                )
            print("[db] ✓ Contadores diarios reseteados")
        except Exception as e:
            print(f"[db] error reset: {e}")

    @property
    def users(self) -> dict:
        self._load_cache()
        return self._cache


# ═══════════════════════════════════════════════════════════════════
#  CREDIT / PAYMENT / REFERRAL
# ═══════════════════════════════════════════════════════════════════

class CreditSystem:
    def __init__(self):
        self.precio_credito = 0.10
        self.paquetes = {
            "10":  {"creditos": 10,  "precio": 1.00,  "bonus": 0},
            "25":  {"creditos": 25,  "precio": 5.00,  "bonus": 0},
            "50":  {"creditos": 50,  "precio": 10.00, "bonus": 0},
            "100": {"creditos": 100, "precio": 20.00, "bonus": 0},
        }

    def comprar_creditos(self, user_id: int, paquete: str) -> dict | None:
        if paquete not in self.paquetes:
            return None
        pkg = self.paquetes[paquete]
        total = pkg["creditos"] + pkg["bonus"]
        user = user_db.get_user(user_id)
        nuevo = user.get("creditos", 0) + total
        user_db.update_user(user_id, {"creditos": nuevo})
        return {
            "creditos_adquiridos": pkg["creditos"], "bonus": pkg["bonus"],
            "total_creditos": total, "precio": pkg["precio"], "nuevo_saldo": nuevo,
        }

    def usar_credito(self, user_id: int) -> bool:
        user = user_db.get_user(user_id)
        if user.get("creditos", 0) > 0:
            user_db.update_user(user_id, {"creditos": user["creditos"] - 1})
            return True
        return False


class PaymentSystem:
    def get_payment_info(self, plan: str, metodo: str) -> dict | None:
        if plan not in PLANES:
            return None
        precio = PLANES[plan]["precio"]
        if metodo == "binance":
            return {"nombre": "Binance Pay", "uid": "1121153030", "precio": precio}
        elif metodo == "paypal":
            return {"nombre": "PayPal",
                    "link": f"https://www.paypal.me/DodrianDx14/{precio}",
                    "precio": precio}
        return None


class ReferralSystem:
    def __init__(self):
        self.bonus_referido = 5
        self.bonus_referidor = 5

    def procesar_referido(self, referrer_id: int, nuevo_id: int) -> bool:
        if not referrer_id or referrer_id == nuevo_id:
            return False
        ref = user_db.get_user(referrer_id)
        nuevo = user_db.get_user(nuevo_id)
        if nuevo.get("referido_por"):
            return False
        referidos = ref.get("referidos", [])
        if nuevo_id in referidos:
            return False
        referidos.append(nuevo_id)
        user_db.update_user(referrer_id, {
            "referidos": referidos,
            "creditos": ref.get("creditos", 0) + self.bonus_referidor,
        })
        user_db.update_user(nuevo_id, {
            "referido_por": referrer_id,
            "creditos": nuevo.get("creditos", 0) + self.bonus_referido,
        })
        return True


# ═══════════════════════════════════════════════════════════════════
#  TELEFONOS + PAGOS PENDIENTES
# ═══════════════════════════════════════════════════════════════════

class TelefonoDB:
    def get_owner(self, phone_hash: str) -> int | None:
        try:
            col = Database.get_collection("telefonos")
            doc = col.find_one({"phone_hash": phone_hash})
            return doc["user_id"] if doc else None
        except Exception:
            return None

    def set_owner(self, phone_hash: str, user_id: int):
        try:
            col = Database.get_collection("telefonos")
            col.update_one(
                {"phone_hash": phone_hash},
                {"$set": {"user_id": user_id, "fecha": now_ec().isoformat()}},
                upsert=True,
            )
        except Exception as e:
            print(f"[db] error telefono: {e}")


class PendingPayments:
    def add(self, user_id: int, data: dict):
        try:
            col = Database.get_collection("pending_payments")
            doc = {"user_id": user_id, **data}
            col.update_one({"user_id": user_id}, {"$set": doc}, upsert=True)
        except Exception as e:
            print(f"[db] error pending: {e}")

    def remove(self, user_id: int):
        try:
            col = Database.get_collection("pending_payments")
            col.delete_one({"user_id": user_id})
        except Exception as e:
            print(f"[db] error pending: {e}")

    def get_all(self) -> dict:
        try:
            col = Database.get_collection("pending_payments")
            result = {}
            for doc in col.find({}):
                uid = str(doc.pop("user_id"))
                doc.pop("_id", None)
                result[uid] = doc
            return result
        except Exception:
            return {}


# ═══════════════════════════════════════════════════════════════════
#  INSTANCIAS GLOBALES
# ═══════════════════════════════════════════════════════════════════

user_db = UserDatabase()
credit_system = CreditSystem()
payment_system = PaymentSystem()
referral_system = ReferralSystem()
telefono_db = TelefonoDB()
pending_payments = PendingPayments()
