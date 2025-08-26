import mysql.connector

# Paramètres DB (mettre ceux de Railway ou autre hébergeur)
db_config = {
    'host': 'switchback.proxy.rlwy.net',
    'user': 'root',
    'password': 'hWDpSRbnJWvAXRlvfDzkvIKSbEcAAvmn',
    'database': 'railway',
    'port': 54201
}

# Connexion à la DB
conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

# Lire le fichier SQL
with open('init_db.sql', 'r', encoding='utf-8') as f:
    sql_commands = f.read().split(';')  # séparer chaque commande

# Exécuter chaque commande
for command in sql_commands:
    cmd = command.strip()
    if cmd:
        cursor.execute(cmd)

conn.commit()
cursor.close()
conn.close()
print("DB initialisée avec succès !")
