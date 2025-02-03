# Cerebras Documentation Tester

This project automates the testing of coding workflows found in our documentation.

## How It Works
* **Scanning Documentation:** The script scans the docs folder for .mdx files containing <Steps></Steps> tags.
  * Extracting Code Snippets: It extracts code blocks inside the <Steps> tags and writes them to code files.
  * If a tutorial includes workflows in multiple languages, each language is treated as a separate branch, generating a distinct code file.
  * If workflows are split into sections (e.g., pretraining, finetuning, continuous pretraining) using tabs, each section is also treated as an individual branch with its own file.
* **Testing Code Execution:** All generated code files are saved in the temp_code directory and executed to check for errors.
* **Generating a Report:** The script outputs a report.txt file containing test results and the execution output of each file.

## Usage

1. **Arrange Docs Folder**  
   Put `.mdx` files in the `docs` folder. You can also simply clone the entirety of `inference-docs` or `training-docs` in the `docs/` folder.
   
2. **Run the Script**
   
   To generate and execute the workflow files, run:
   ```bash
   python docs_tester.py
   ```
To only extract the files without executing them, run:

   ```bash
   python docs_tester.py  --extract_only
   ```

## Output:
* Generated code files are saved in the temp_code folder.
* An execution report is saved to report.txt.
