import pypdf
import datetime


def process_pdf(pdf_file_path: str, password: str) -> tuple:
    """
    Process a PDF file containing stock transaction information.

    Args:
        pdf_file_path (str): The path to the PDF file.
        password (str): The password to unlock the PDF file.

    Returns:
        tuple: A tuple containing the date of the transactions and a list of transactions.

    """

    # Open the locked PDF file with the given password
    with open(pdf_file_path, 'rb') as pdf_file:
        # Create a PDF reader object
        pdf_reader = pypdf.PdfReader(pdf_file, password=password)

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
                date_str = lines[20][0:10]
                date = datetime.datetime.strptime(date_str, '%d/%m/%Y').date()

            # Create a set of stock exchanges
            us_stock_exchanges = {"[XNYS]", "[XNAS]", "[ARCX]"}

            # Loop over each line in the page
            for line_num, line in enumerate(lines):
                # Check if the line contains a stock exchange
                for exchange in us_stock_exchanges:
                    if exchange in line:
                        # Extract transaction details from the order header and order detail lines
                        order_header = lines[line_num - 2].split(" ")
                        transaction_type = order_header[2]
                        stock_name = lines[line_num - 1]

                        order_detail = lines[line_num + 1]
                        order_detail = order_detail.split(" ")
                        share = order_detail[0]
                        price = order_detail[1]
                        amount = float(order_detail[3])
                        commission_and_tax = float(order_detail[4])
                        calculate_withholding_tax = 0

                        # Calculate the commission and tax
                        commission = 0
                        if commission_and_tax != 0:
                            commission = round((amount * (0.15 / 100)), 2)
                            calculate_withholding_tax = round(commission * (7 / 100), 2)
                            if (calculate_withholding_tax + commission) != commission_and_tax:
                                calculate_withholding_tax = commission_and_tax - commission

                        # Get the withholding tax from the next line
                        pdf_withholding_tax = lines[line_num + 3]

                        if pdf_withholding_tax == calculate_withholding_tax:
                            withholding_tax = calculate_withholding_tax
                        else:
                            withholding_tax = calculate_withholding_tax

                        # Add the transaction to the list of transactions
                        transactions.append(
                            [transaction_type, stock_name, share, price, commission, withholding_tax, amount])

        # Return the date and transactions as a tuple
        return date, transactions
