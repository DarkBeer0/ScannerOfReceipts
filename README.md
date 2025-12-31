📄 Invoice Data Extractor

Invoice Data Extractor is a Python application that automatically extracts data from invoices in PDF, JPG, or PNG formats using Mistral Vision. It processes multiple invoices, validates the data, and saves results as JSON, CSV, and Excel files.

🚀 Features

-Upload and process multiple invoices at once
-Extract key invoice data:
  -Invoice number
  -Issue date
  -Supplier and customer
  -Line items with quantity, unit price, and value
  -Net amount, VAT, and gross amount
  
-Validate calculations (net + VAT = gross)
-Create a summary DataFrame with all invoices
-Save results to CSV and Excel
-Cache system to avoid redundant API calls
-Logging for processing and errors

Tech Stack

Python 3.9+

Mistral API

pandas, openpyxl, pdf2image, tqdm
