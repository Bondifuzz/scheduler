class DatabaseError(Exception):
    """Base exception for all database errors"""


class DBRecordNotFoundError(DatabaseError):
    pass


class DBFuzzerNotFoundError(DBRecordNotFoundError):
    pass
