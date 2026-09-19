"""
Script de migración de archivos JSON a MongoDB.
Ejecutar UNA SOLA VEZ después de configurar MongoDB.

Uso:
    python migrate_to_mongo.py
"""
import os
import json
from core.database import Database, user_db, telefono_db, pending_payments


def migrate():
    print("=" * 60)
    print("  MIGRACIÓN DE JSON A MONGODB")
    print("=" * 60)

    if not Database.connect():
        print("❌ No se pudo conectar a MongoDB. Abortando.")
        return

    # 1. Usuarios
    if os.path.exists("users_db.json"):
        with open("users_db.json", "r") as f:
            users_data = json.load(f)
        count = 0
        for uid_str, data in users_data.items():
            uid = int(uid_str)
            existing = user_db.get_user(uid)
            if existing.get("total_descargas", 0) == 0:
                data["user_id"] = uid
                user_db.update_user(uid, data)
                count += 1
        print(f"✅ {count} usuarios migrados")

    # 2. Teléfonos
    if os.path.exists("telefonos_registrados.json"):
        with open("telefonos_registrados.json", "r") as f:
            tels = json.load(f)
        for phone_hash, uid in tels.items():
            telefono_db.set_owner(phone_hash, uid)
        print(f"✅ {len(tels)} teléfonos migrados")

    # 3. Pagos pendientes
    if os.path.exists("pending_payments.json"):
        with open("pending_payments.json", "r") as f:
            pendings = json.load(f)
        for uid_str, data in pendings.items():
            pending_payments.add(int(uid_str), data)
        print(f"✅ {len(pendings)} pagos migrados")

    print("=" * 60)
    print("  ✅ MIGRACIÓN COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
