import os
import datetime

import email
import email.message
from email.header import decode_header

import imaplib
from imaplib import IMAP4_SSL


def connect_to_server(email_address: str, app_password: str) -> IMAP4_SSL | None:
    """
    Connects to the IMAP server.

    Args:
        email_address (str): The email account.
        app_password (str): The email account app password.

    Returns:
        imaplib.IMAP4_SSL: An IMAP4_SSL object connected to the email server.
    """
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, app_password)
    except Exception as e:
        print(f"Error connecting to the mail server: {e}")
        return None
    return mail


def search_emails(
    mail: imaplib.IMAP4_SSL,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    subject_keyword: str,
    email_address: str,
) -> list:
    """
    Searches for emails that match the given criteria.

    Args:
        mail (imaplib.IMAP4_SSL): An IMAP4_SSL object connected to the email server.
        start_date (datetime.datetime): The start date for the email search.
        end_date (datetime.datetime): The end date for the email search.
        subject_keyword (str): The subject keyword to search for.
        email_address (str): The email address to search for in the "from" field.

    Returns:
        list: A list of email IDs that match the given criteria.
    """
    since_date = start_date.strftime("%d-%b-%Y")
    before_date = (end_date + datetime.timedelta(days=1)).strftime("%d-%b-%Y")
    search_criteria = f'SINCE "{since_date}" BEFORE "{before_date}" SUBJECT "{subject_keyword}" FROM "{email_address}"'
    try:
        status, data = mail.search(None, search_criteria)
    except Exception as e:
        print(f"Error searching emails: {e}")
        return []
    return data[0].split()


def decode_email_subject(email_message: email.message.Message) -> str:
    """
    Decodes the subject of an email.

    Args:
        email_message (email.message.Message): The email message object.

    Returns:
        str: The decoded email subject as a string.
    """
    subject, encoding = decode_header(email_message["Subject"])[0]
    if encoding:
        subject = subject.decode(encoding)
    return subject


def extract_attachment_info(part: email.message.Message) -> str:
    """
    Extracts the filename and date from an email attachment.

    Args:
        part (email.message.Message): The email message object representing the attachment.

    Returns:
        str: The extracted filename in the format: 'YYYY-MM-DD_confirmationNote.pdf'.
    """
    if part.get_filename():
        filename_parts = part.get_filename().split("_")
        # Ensure the filename has enough parts before accessing indices
        if len(filename_parts) > 4 and len(filename_parts[4]) >= 8:
            # 2024-09 format
            date_str = filename_parts[4][:8]
            try:
                # Parse the date string
                date = datetime.datetime.strptime(date_str, "%d%m%Y").date()
                # Construct the new filename
                filename = f"{str(date)}_{filename_parts[4][8:-4]}_confirmationNote.pdf"
            except ValueError:
                # Handle incorrect date formatting
                print(f"Invalid date format in filename: {filename_parts[4]}")
                filename = "attachment_confirmationNote.pdf"

        if len(filename_parts) == 4 and len(filename_parts[3]) >= 8:
            # 2024-10 format
            date_str = filename_parts[3][6:-10]

            try:
                # Parse the date string
                date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                # Construct the new filename
                filename = (
                    f"{str(date)}_{filename_parts[3][13:-4]}_confirmationNote.pdf"
                )
            except ValueError:
                # Handle incorrect date formatting
                print(f"Invalid date format in filename: {filename_parts[3]}")
                filename = "attachment_confirmationNote.pdf"
        else:
            # Fallback if filename doesn't have enough parts
            print(f"Filename doesn't match expected format: {part.get_filename()}")
            filename = "attachment_confirmationNote.pdf"
    else:
        filename = "attachment_confirmationNote.pdf"

    return filename


def save_attachment(part: email.message.Message, filename: str) -> None:
    """
    Saves an email attachment to a file.

    Args:
        part (email.message.Message): The email message object representing the attachment.
        filename (str): The name of the file to save the attachment to.

    Returns:
        None
    """
    file_path = os.path.join("data", filename)
    with open(file_path, "wb") as f:
        f.write(part.get_payload(decode=True))
    print(f"Downloaded attachment: {file_path}")


def query_emails(
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    email_address: str,
    app_password: str,
    from_email: str,
    subject_keyword: str,
) -> list:
    """
    Searches for and processes emails that match the given criteria.

    Args:
        start_date (datetime.datetime): The start date for the email search.
        end_date (datetime.datetime): The end date for the email search.
        email_address (str): The email account.
        app_password (str): The email account app password.
        from_email (str): The email address to search for in the "from" field.
        subject_keyword (str): The subject keyword to search for.

    Returns:
        list: A list of filenames of the downloaded attachments.
    """
    file_list = []
    try:
        print("Connecting to mail server.")
        with connect_to_server(email_address, app_password) as mail:
            print("Mail server connected.")
            mail.select("inbox")
            print("Searching E-mail.")
            matching_emails = search_emails(
                mail, start_date, end_date, subject_keyword, from_email
            )

            if len(matching_emails) > 1:
                print(f"Found {len(matching_emails)} E-mails.")
            elif len(matching_emails) == 1:
                print("Found 1 E-mail.")
            else:
                print("No matching E-mail found.")

            for num in matching_emails:
                try:
                    status, email_data = mail.fetch(num, "(RFC822)")

                    # Ensure email_data exists and is properly structured
                    if (
                        len(email_data) > 0
                        and isinstance(email_data[0], tuple)
                        and len(email_data[0]) > 1
                    ):

                        # Parse the email
                        email_message = email.message_from_bytes(email_data[0][1])
                        subject = decode_email_subject(email_message)
                        print(f"Subject: {subject}")
                        print(f"From: {email_message['From']}")

                        # Walk through email parts for attachments
                        if email_message.is_multipart():
                            for part in email_message.walk():
                                if part.get_content_disposition() == "attachment":
                                    filename = extract_attachment_info(part)
                                    print(f"Found attachment: {filename}")
                                    save_attachment(part, filename)
                                    file_list.append(f"data/{filename}")
                        else:
                            print("This email is not multipart; no attachments found.")
                    else:
                        print("Unexpected email data structure.")
                except Exception as e:
                    print(f"Error processing email: {e}")

    except Exception as e:
        print(f"Error connecting to the mail server: {e}")

    return file_list
