# Dime Asset Tracking and Analytics

## Description
Dime Asset Tracking and Analytics helps you run a summary on your investment in the Dime application.

## Features
- Log your investment in Dime (US stock) from Dime's stock receipt.
- Summarize your assets (US stock assets) on each date.
- Provide additional US stock information based on the finviz.com website.

## Installation Instructions
1. Clone the project from the repository:
    ```sh
    git clone https://github.com/Ponny035/Dime-asset-tracking-and-analytics.git
    ```
2. Install system requirements:
    ```sh
    pip install -r requirements.txt
    ```
3. Set up Google Sheet (for v1.0.0):
   [Google Sheet Link](https://docs.google.com/spreadsheets/d/1NFUh-1MYeRrTTz9rFvLhIpFDu3EMzaWTG5hKF6gW5cM/edit?usp=sharing)
4. Set up .env based on the example:
    ```sh
    cp .env.example .env
    ```
5. Optional: Set up visualization (for v1.0.0):
   [Visualization Link](https://lookerstudio.google.com/reporting/4accde1c-47a9-49fe-aec0-b83c6ddcffb9)

## Usage
1. Set up `main.py` based on your local time zone and the date you want to run.
2. Run the project:
    ```sh
    python main.py
    ```

## Contributing
Currently, there are no specific guidelines for contributing. Suggestions are welcome.

## License
<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png" /></a><br />
This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License</a>.