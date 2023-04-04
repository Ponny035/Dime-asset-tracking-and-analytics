import os
import imaplib
import datetime

import email
from email.header import decode_header

from dotenv import load_dotenv

# load the variables from .env
load_dotenv()
username = os.getenv('USERNAME')
app_password = os.getenv('APP_PASSWORD')

def read_emails(start_date, end_date):
    # connect to the IMAP server
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(username, app_password)

    # select the mailbox you want to read emails from (in this case, the inbox)
    mail.select('inbox')

    # search for emails that contain the word "Dime" and were sent only in the specified date range
    since_date = start_date.strftime('%d-%b-%Y')
    before_date = end_date.strftime('%d-%b-%Y')
    search_criteria = f'SINCE "{since_date}" BEFORE "{before_date}" SUBJECT "Confirmation Note" FROM "no-reply@dime.co.th"'
    status, data = mail.search(None, search_criteria)

    # loop through all the matching emails and process any PDF attachments found
    for num in data[0].split():
        status, email_data = mail.fetch(num, '(RFC822)')
        email_message = email.message_from_bytes(email_data[0][1])

        # decode the subject and print it along with the sender
        subject = decode_header(email_message['Subject'])[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()
        print('Subject:', subject)
        print('From:', email_message['From'])

        # Loop over each part of the email message
        for part in email_message.walk():
            # If the part is an attachment
            if part.get_content_disposition() == 'attachment':
                # Check if the attachment has a file name
                if part.get_filename():
                    filename = part.get_filename()
                    filename = filename.split("_")[4]
                    date = filename[:8]
                    year = date[4:]
                    month = date[2:4]
                    day = date[:2]
                    filename = year + "_" + month + "_" + day + "_" + filename[8:].split(".")[0] + "_confirmationNote.pdf"
                else:
                    filename = 'attachment.pdf'

                # Construct the file path
                file_path = os.path.join('data', filename)

                # Save the attachment
                with open(file_path, 'wb') as f:
                    f.write(part.get_payload(decode=True))
                print('Downloaded attachment:', file_path)

    # close the mailbox and logout from the server
    mail.close()
    mail.logout()

# calculate the dates for the beginning and end of the last month
today = datetime.date.today()
last_month = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1) 
start_date = last_month.replace(day=1)
end_date = last_month.replace(day=last_month.day)

# call the read_emails function with the start and end dates
read_emails(start_date, end_date)
