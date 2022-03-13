import typing as T
import yagmail

from utils import logger


class Email(T.TypedDict):
    address: str
    password: str


def send_email(
    email: Email,
    to_addresses: T.List[str],
    subject: str,
    content: T.List[str],
) -> None:
    with yagmail.SMTP(email["address"], email["password"]) as email_sender:
        if isinstance(to_addresses, str):
            to_addresses = [to_addresses]
        email_sender.send(to_addresses, subject, content)
        logger.print_ok(f"To: {', '.join(to_addresses)}\nFrom: {email['address']}")
        logger.print_ok(f"Subject: {subject}")
        logger.print_ok(f"{content}")
