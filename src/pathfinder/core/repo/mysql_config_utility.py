from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    user: str
    database: str
    password: Optional[str] = None
    ssl_required: bool = True
    port: int = 3306


def parse_mysql_config(config_str: str) -> MySQLConfig:
    """
    Expected formats:
      mysql:host:user:database
      mysql:host:user:password:database
      mysql:host:port:user:database
      mysql:host:port:user:password:database
    """

    if not config_str:
        raise ValueError("Empty MySQL config string")

    parts = config_str.split(":")

    if parts[0].lower() != "mysql":
        raise ValueError(f"Unsupported config scheme: {parts[0]}")

    # mysql:host:user:db
    if len(parts) == 4:
        _, host, user, database = parts
        return MySQLConfig(
            host=host,
            user=user,
            database=database,
        )

    # mysql:host:user:password:db
    if len(parts) == 5 and parts[2].isdigit() is False:
        _, host, user, password, database = parts
        return MySQLConfig(
            host=host,
            user=user,
            password=password,
            database=database,
        )

    # mysql:host:port:user:db
    if len(parts) == 5 and parts[2].isdigit():
        _, host, port, user, database = parts
        return MySQLConfig(
            host=host,
            port=int(port),
            user=user,
            database=database,
        )

    # mysql:host:port:user:password:db
    if len(parts) == 6:
        _, host, port, user, password, database = parts
        return MySQLConfig(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
        )

    raise ValueError(
        "Invalid MySQL config format. "
        "Expected mysql:host:user:db "
        "or mysql:host:user:password:db "
        "or mysql:host:port:user:db "
        "or mysql:host:port:user:password:db"
    )