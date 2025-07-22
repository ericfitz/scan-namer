# scan-namer
Rename scanned documents in Google Drive, to have descriptive names based on content

## overview
I have a Raven document scanner.  It scans my documents, performs OCR on them, and then saves them in Google drive as PDFs.

All the PDFs have generic names like "20240108_Raven_Scan.pdf".

I wanted to build a tool that would read the documents and rename them to something meaningful and indicative of the contents of the document.

## script
This script does the following:

- Lists the files from a defined path in Google Drive.
- For each file, see if it has a "generic" document name, using configurable heuristics.  If so:
    - Download the document
    - If the document is larger than N pages, extract the first N pages into a temporary doc (default is 3 pages)
    - Send the doc to an LLM with a prompt to suggest a new name for the document, with specific guidelines for file name format
    - Waits for the response
    - If in dry run mode, prints the suggested name without renaming the document, otherwise:
        - Renames the document in Google Drive
        - Logs the activity
    - Deletes the temporary doc

## alternative uses
With small modifications, you could point this to any document store you want, and let it rename your documents more meaningfully.  I will probably add a "local" mode at some point, or you can send me a pull request.

## ai-generated code
For this project:
- A human did:
    - specification
    - testing
    - debugging
    - documentation review and revision
    - minor code tweaks
    - prompt tuning

- A Claude model by Anthropic did:
    - coding (initial and bugfixing)
    - prompt generation
    - initial documentation
