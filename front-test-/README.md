# Claude Trusted tames hallucination

> Our MCP‑powered verification layer forces Claude to cite real evidence, reducing error‑rates on PDFs

This project is a fork of [Open WebUI](https://github.com/open-webui/open-webui), an extensible, feature-rich, and user-friendly self-hosted AI platform.

## Introduction

This hackathon project extends Open WebUI with PDF search capabilities, allowing users to:

- Upload PDF files directly from the chat interface
- Attach PDFs to conversations for contextual search
- Maintain persistent PDF references throughout chat sessions
- Query information from PDF documents using natural language

The implementation seamlessly integrates with Open WebUI's existing interface while adding specialized PDF processing functionality through a dedicated backend service.

## Setup Instructions

### Prerequisites

- Node.js and npm installed
- Python environment for the backend service
- Conda package manager installed

### Running the Project

1. **API Backend:**
   Refer to the [Anthropic MCP-powered backend](https://github.com/nlyu1/anthropic-2025-spongebob/tree/fusion) for detailed setup instructions. Make sure this service is running before proceeding to the next step.

   **Install Chat Backend Dependencies:**
   ```bash
   cd backend
   conda create --name open-webui python=3.11
   conda activate open-webui
   pip install -r requirements.txt -U
   ```
   This creates a dedicated Conda environment and installs all required dependencies.

2. **Chat Backend:**
   ```bash
   sh dev.sh
   ```
   This starts the chat backend service that connects with the API backend.

3. **Chat Frontend:**
   ```bash
   npm run dev
   ```
   This launches the Open WebUI frontend with our PDF search extensions.

4. **Access the Application:**
   Open your browser and navigate to the URL displayed in the terminal (typically http://localhost:5173).

## Using PDF Search

1. Click the "+" button in the chat input area
2. Select a PDF file to upload
3. Once uploaded, the PDF will be attached to your conversation
4. Ask questions about the content of the PDF in natural language
5. The system will automatically search the PDF and provide relevant answers

## Development Notes

See [our hackathon memo](0-our-hackathon-memo.md) for implementation details and troubleshooting information.

## Credits

This project builds upon the excellent work of [Open WebUI](https://github.com/open-webui/open-webui), created by [Timothy Jaeryang Baek](https://github.com/tjbck).

## Team Members

This project was developed by Harvard College CS students during the Anthropic x WiCS Hackathon 2025 (April):

- Xingjian (Nicholas) Lyu
- Bozhen Peng
- Aghyad Deeb
- Jay Choi
- Aldo Stefanoni

## License

This project is licensed under the [BSD-3-Clause License](LICENSE). Our modifications are Copyright (c) 2025, Claude Trusted Team, while the original Open WebUI components remain Copyright (c) 2023, Timothy Jaeryang Baek.
