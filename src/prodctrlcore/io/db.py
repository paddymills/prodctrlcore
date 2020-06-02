
import os
import pyodbc

from string import Template

SNDB_PRD = "HIIWINBL18"
SNDB_DEV = "HIIWINBL5"

CONN_STR_TEMPLATE = Template(
    "DRIVER={$driver};SERVER=$server;UID=$user;PWD=$pwd;")
DB_TEMPLATE = Template("DATABASE=$db;")

cs_kwargs = dict(
    driver="SQL Server",
    server=SNDB_DEV,
    db="SNDBase91",
    user=os.getenv('SNDB_USER'),
    pwd=os.getenv('SNDB_PWD'),
)


def get_sndb_conn(dev=False, **kwargs):
    cs_kwargs.update(kwargs)

    if dev:
        cs_kwargs['server'] = SNDB_PRD
        cs_kwargs['db'] = "SNDBaseDev"

    connection_string = CONN_STR_TEMPLATE.substitute(**cs_kwargs)

    return pyodbc.connect(connection_string)