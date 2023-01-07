import contextlib
import typing as T

from sqlalchemy import create_engine
from sqlalchemy.ENGINE.base import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.scoping import ScopedSessionMixin

ENGINE = None
THREAD_SAFE_SESSION_FACTORY = None

Base = declarative_base()


def init_engine(uri, **kwargs) -> Engine:
    global ENGINE
    if ENGINE is None:
        ENGINE = create_engine(uri, **kwargs)
    return ENGINE


def init_session_factory() -> ScopedSessionMixin:
    """Initialize the THREAD_SAFE_SESSION_FACTORY."""
    global ENGINE, THREAD_SAFE_SESSION_FACTORY
    if ENGINE is None:
        raise ValueError(
            "Initialize ENGINE by calling init_engine before calling init_session_factory!"
        )
    if THREAD_SAFE_SESSION_FACTORY is None:
        THREAD_SAFE_SESSION_FACTORY = scoped_session(sessionmaker(bind=ENGINE))
    return THREAD_SAFE_SESSION_FACTORY


@contextlib.contextmanager
def ManagedSession():
    """Get a session object whose lifecycle, commits and flush are managed for you.
    Expected to be used as follows:
    ```
    with ManagedSession() as session:            # multiple db_operations are done within one session.
        db_operations.select(session, **kwargs)  # db_operations is expected not to worry about session handling.
        db_operations.insert(session, **kwargs)  # after the with statement, the session commits to the database.
    ```
    """
    global THREAD_SAFE_SESSION_FACTORY
    if THREAD_SAFE_SESSION_FACTORY is None:
        raise ValueError("Call init_session_factory before using ManagedSession!")
    session = THREAD_SAFE_SESSION_FACTORY()
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
        THREAD_SAFE_SESSION_FACTORY.remove()
