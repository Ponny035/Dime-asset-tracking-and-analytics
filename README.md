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
2. Install Python:
   We recommend Python v3.13.3. You can follow the guide on [Real Python](https://realpython.com/installing-python/) for detailed instructions on installing Python on your operating system.

3. Install system requirements:
    ```sh
    pip install -r requirements.txt
    ```
4. Set up Google Sheet (for v1.0.0):
   [Google Sheet Link](https://docs.google.com/spreadsheets/d/1NFUh-1MYeRrTTz9rFvLhIpFDu3EMzaWTG5hKF6gW5cM/edit?usp=sharing)
5. Set up .env based on the example:
    ```sh
    cp .env.example .env
    ```
6. Optional: Set up visualization (for v1.0.0):
   [Visualization Link](https://lookerstudio.google.com/reporting/4accde1c-47a9-49fe-aec0-b83c6ddcffb9)

## Usage
1. Set up `main.py` based on your local time zone and the date you want to run.
2. Run the project:
    ```sh
    python main.py
    ```

## Contributing

We welcome contributions to the Dime-asset-tracking-and-analytics project! Here are some ways you can contribute:

1. **Report Bugs:** If you encounter any issues or bugs, please report them using the [GitHub Issues](https://github.com/Ponny035/Dime-asset-tracking-and-analytics/issues) section.

2. **Feature Requests:** Have an idea for a new feature? We'd love to hear about it! Submit your suggestions via the [GitHub Issues](https://github.com/Ponny035/Dime-asset-tracking-and-analytics/issues) section.

3. **Code Contributions:**
   - Fork the repository.
   - Create a new branch for your feature or bug fix.
   - Make your changes in the new branch.
   - Ensure your code follows the project's coding standards and includes appropriate tests.
   - Submit a pull request with a clear description of your changes.

4. **Documentation:** Help improve the documentation by suggesting changes or adding new sections that you think would be helpful.

5. **Review and Testing:** Review pull requests and test new features or bug fixes. Your feedback is valuable to ensure the quality of the project.

6. **Spread the Word:** If you find this project useful, let others know about it! Share it with your colleagues, friends, and social media networks.

Please make sure to follow our [Code of Conduct](link-to-code-of-conduct) in all your interactions with the project.

Thank you for contributing!
## License
<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png" /></a><br />
This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License</a>.