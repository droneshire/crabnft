import typing as T
import yagmail

from utils import logger


class Email(T.TypedDict):
    address: str
    password: str


def send_email_raw(
    email: Email,
    to_addresses: T.List[str],
    subject: str,
    content: T.List[str],
    verbose: bool = False,
) -> None:
    with yagmail.SMTP(email["address"], email["password"]) as email_sender:
        if isinstance(to_addresses, str):
            to_addresses = [to_addresses]
        email_sender.send(to_addresses, subject, content)
        if verbose:
            logger.print_ok(f"To: {', '.join(to_addresses)}\nFrom: {email['address']}")
            logger.print_ok(f"Subject: {subject}")
            logger.print_ok(f"{content}")


def send_email(
    emails: T.List[Email],
    to_addresses: T.List[str],
    subject: str,
    content: T.List[str],
    verbose: bool = False,
) -> None:
    for email in emails:
        try:
            send_email_raw(email, to_addresses, subject, content)
            return
        except KeyboardInterrupt:
            raise
        except:
            pass

    logger.print_fail("Failed to send email alert")
