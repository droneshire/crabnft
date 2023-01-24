import contextlib
import os
import typing as T

from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.scoping import ScopedSessionMixin
from sqlalchemy_utils import database_exists

from utils import logger
from utils.file_util import make_sure_path_exists

ENGINE = {}
THREAD_SAFE_SESSION_FACTORY = {}

AccountBase = declarative_base(name="AccountBase")
GameBase = declarative_base(name="GameBase")



def init_engine(uri: str, db: str, **kwargs: T.Any) -> Engine:
    global ENGINE
    if db not in ENGINE:
        uri.split(".")[0]
        ENGINE[db] = create_engine(uri, **kwargs)
    return ENGINE[db]


def init_session_factory(db: str) -> ScopedSessionMixin:
    """Initialize the THREAD_SAFE_SESSION_FACTORY."""
    global ENGINE, THREAD_SAFE_SESSION_FACTORY
    if db not in ENGINE:
        raise ValueError(
            "Initialize ENGINE by calling init_engine before calling init_session_factory!"
        )
    if db not in THREAD_SAFE_SESSION_FACTORY:
        THREAD_SAFE_SESSION_FACTORY[db] = scoped_session(sessionmaker(bind=ENGINE[db]))
    return THREAD_SAFE_SESSION_FACTORY[db]


@contextlib.contextmanager
def ManagedSession(db: str = None):
    """Get a session object whose lifecycle, commits and flush are managed for you.
    Expected to be used as follows:
    ```
    with ManagedSession() as session:            # multiple db_operations are done within one session.
        db_operations.select(session, **kwargs)  # db_operations is expected not to worry about session handling.
        db_operations.insert(session, **kwargs)  # after the with statement, the session commits to the database.
    ```
    """
    global THREAD_SAFE_SESSION_FACTORY
    if db is None:
        # assume we're just using the default db
        db = list(THREAD_SAFE_SESSION_FACTORY.keys())[0]

    if db not in THREAD_SAFE_SESSION_FACTORY:
        raise ValueError("Call init_session_factory before using ManagedSession!")
    session = THREAD_SAFE_SESSION_FACTORY[db]()
    try:
        yield session
        session.commit()
        session.flush()
    except Exception:
        session.rollback()
        # When an exception occurs, handle session session cleaning,
        # but raise the Exception afterwards so that user can handle it.
        raise
    finally:
        # source:
        # https://stackoverflow.com/questions/21078696/why-is-my-scoped-session-raising-an-attributeerror-session-object-has-no-attr
        THREAD_SAFE_SESSION_FACTORY[db].remove()


def init_database(log_dir: str, db_name: str, db_model_class: T.Any) -> None:
    db_file = os.path.join(log_dir, "database", db_name)
    sql_db = "sqlite:///" + db_file

    make_sure_path_exists(db_file)
    engine = init_engine(sql_db, db_name)
    if database_exists(engine.url):
        logger.print_bold(f"Found existing database")
    else:
        logger.print_ok_blue(f"Creating new database!")
        db_model_class.metadata.create_all(bind=engine)
    init_session_factory(db_name)
