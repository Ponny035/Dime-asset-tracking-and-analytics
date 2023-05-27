import PyPDF2
import datetime


def processing_pdf(pdf_file_path: str, password: str):
    # Open the locked PDF file with password
    pdf_file = open(pdf_file_path, 'rb')

    # Create a PDF reader object with password
    pdf_reader = PyPDF2.PdfReader(pdf_file, password=password)

    # Create an empty list to store the transactions
    transactions = []
    date = None

    # Iterate over each page in the PDF file
    for page in pdf_reader.pages:
        # Extract the text from the page
        page_text = page.extract_text()

        # Split the text into lines
        lines = page_text.split("\n")

        # Get the date from the 15th line
        if date is None:
            date_str = lines[14][0:10]
            date = datetime.datetime.strptime(date_str, '%d/%m/%Y').date()

        # Create a list of stock exchanges
        stock_exchanges = ["[XNYS]", "[XNAS]", "[ARCX]"]

        # Loop over each line in the page
        for line_num, line in enumerate(lines):
            # Check if the line contains a stock exchange
            for exchange in stock_exchanges:
                if exchange in line:
                    # Extract transaction details from the order header and order detail lines
                    order_header = lines[line_num - 1].split(" ")
                    transaction_type = order_header[2][:3]
                    stock_name = order_header[2][3:]

                    order_detail = line.split(" ")
                    share = order_detail[0][6:]
                    price = order_detail[1]
                    amount = float(order_detail[2][3:])
                    commission_and_tax = float(order_detail[3])

                    # Calculate the commission and tax
                    commission = 0
                    tax = 0
                    if commission_and_tax != 0:
                        commission = round((amount * (0.15 / 100)), 2)
                        tax = round(commission * (7 / 100), 2)
                        if (tax + commission) != commission_and_tax:
                            tax = commission_and_tax - commission

                    # Get the withholding tax from the next line
                    withholding_tax = lines[line_num + 1][4:9]

                    # Add the transaction to the list of transactions
                    transactions.append([transaction_type, stock_name, share, price, commission, tax, amount])

    # Close the PDF file
    pdf_file.close()
    return date, transactions