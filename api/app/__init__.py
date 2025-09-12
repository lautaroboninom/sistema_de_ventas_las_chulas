# app/_init_.py
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except Exception:
    # If mysqlclient is available, this is harmless; if not, PyMySQL provides MySQLdb
    pass
