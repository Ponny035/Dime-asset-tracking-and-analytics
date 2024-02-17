import os
import datetime
import email
import email.message
from email.header import decode_header
import imaplib


def connect_to_server(username: str, app_password: str) -> imaplib.IMAP4_SSL:
    """
    Connects to the IMAP server.

    Args:
        username (str): The email account username.
        app_password (str): The email account app password.

    Returns:
        imaplib.IMAP4_SSL: An IMAP4_SSL object connected to the email server.
    """
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(username, app_password)
    except Exception as e:
        print(f"Error connecting to the mail server: {e}")
        return None
    return mail


def search_emails(mail: imaplib.IMAP4_SSL, start_date: datetime.datetime, end_date: datetime.datetime,
                  subject_keyword: str, from_email: str) -> list:
    """
    Searches for emails that match the given criteria.

    Args:
        mail (imaplib.IMAP4_SSL): An IMAP4_SSL object connected to the email server.
        start_date (datetime.datetime): The start date for the email search.
        end_date (datetime.datetime): The end date for the email search.
        subject_keyword (str): The subject keyword to search for.
        from_email (str): The email address to search for in the "from" field.

    Returns:
        list: A list of email IDs that match the given criteria.
    """
    since_date = start_date.strftime('%d-%b-%Y')
    before_date = (end_date + datetime.timedelta(days=1)).strftime('%d-%b-%Y')
    search_criteria = f'SINCE "{since_date}" BEFORE "{before_date}" SUBJECT "{subject_keyword}" FROM "{from_email}"'
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
    subject, encoding = decode_header(email_message['Subject'])[0]
    if encoding:
        subject = subject.decode(encoding)
    return subject


def extract_attachment_info(part: email.message.Message) -> str:
    """
    Extracts the filename and date from an email attachment.

    Args:
        part (email.message.Message): The email message object representing the attachment.

    Returns:
        str: The extracted filename.
    """
    if part.get_filename():
        filename_parts = part.get_filename().split("_")
        date_str = filename_parts[4][:8]
        date = datetime.datetime.strptime(date_str, '%d%m%Y').date()
        filename = f"{str(date)}_{filename_parts[4][8:-4]}_confirmationNote.pdf"
    else:
        filename = 'attachment.pdf'
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
    file_path = os.path.join('data', filename)
    with open(file_path, 'wb') as f:
        f.write(part.get_payload(decode=True))
    print(f"Downloaded attachment: {file_path}")


def read_emails(start_date: datetime.datetime, end_date: datetime.datetime, username: str,
                app_password: str, from_email: str, subject_keyword: str) -> list:
    """
    Searches for and processes emails that match the given criteria.

    Args:
        start_date (datetime.datetime): The start date for the email search.
        end_date (datetime.datetime): The end date for the email search.
        username (str): The email account username.
        app_password (str): The email account app password.
        from_email (str): The email address to search for in the "from" field.
        subject_keyword (str): The subject keyword to search for.

    Returns:
        list: A list of filenames of the downloaded attachments.
    """
    file_list = []
    try:
        print("Connecting to mail server.")
        with connect_to_server(username, app_password) as mail:
            print("Mail server connected.")
            mail.select('inbox')
            print("Searching E-mail.")
            matching_emails = search_emails(mail, start_date, end_date, subject_keyword, from_email)
            print("Found", str(len(matching_emails)), "E-mail.")

            for num in matching_emails:
                try:
                    status, email_data = mail.fetch(num, '(RFC822)')
                    email_message = email.message_from_bytes(email_data[0][1])
                    subject = decode_email_subject(email_message)
                    print(f"Subject: {subject}")
                    print(f"From: {email_message['From']}")

                    for part in email_message.walk():
                        if part.get_content_disposition() == 'attachment':
                            filename = extract_attachment_info(part)
                            save_attachment(part, filename)
                            file_list.append("data/" + filename)
                except Exception as e:
                    print(f"Error processing email: {e}")

    except Exception as e:
        print(f"Error connecting to the mail server: {e}")

    return file_list
