import pyodbc

# PAS DIT AAN NAAR JOUW SQL SERVER INSTANCE
SQL_SERVER = r"localhost\SQLEXPRESS"          # of "SERVERNAAM\\SQLEXPRESS"
SQL_DATABASE = "LogoGateway"
SQL_USER = "logogw_user"
SQL_PASSWORD = "SterkWachtwoord"  # zelfde als in SQL script

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    f"UID={SQL_USER};"
    f"PWD={SQL_PASSWORD};"
    "Trusted_Connection=yes;"
    "Encrypt=Yes;"
    "TrustServerCertificate=yes;"
)

def get_connection():
    return pyodbc.connect(CONN_STR)
