import os
import glob
import logging
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

def pdf_to_text(path: str) -> str:
    """
    Extract text from a PDF file and save it to a text file.
    
    Args:
        path: Path to the PDF file
        
    Returns:
        str: The extracted text
    """
    # Extract text from PDF
    doc = fitz.open(path)
    parts = []
    for page in doc:
        parts.append(page.get_text())      # 'text' is default; returns UTF‑8 str
    text = "\n".join(parts)
    
    # Create parsed_pdfs directory if it doesn't exist
    parsed_dir = "parsed_pdfs"
    os.makedirs(parsed_dir, exist_ok=True)
    
    # Get PDF filename without extension
    pdf_name = os.path.splitext(os.path.basename(path))[0]
    
    # Save text to file
    output_path = os.path.join(parsed_dir, f"{pdf_name}.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    return text

def load_pdf_as_blocks(pdf_root='./files', filenames: list[str] | None = None) -> list[dict]:
    """Return a list of {'type':'text', ...} blocks for PDFs in ./files.
    
    Args:
        filenames: Optional list of filenames (without extension) to load.
                   If None, loads all PDFs in the pdf_root.
                   Example: ['document1', 'report_final']
    
    Returns:
        A list of text blocks containing the extracted PDF content.
    """
    blocks: list[dict] = []
    pdf_paths_to_load: list[str] = []

    if filenames is None:
        # Load all PDFs in the directory
        pdf_paths_to_load = glob.glob(f"{pdf_root}/*.pdf")
        logger.info(f'[INFO / pdf_loading_utils / load_pdf_as_blocks] Loading all PDF files from {os.path.abspath(pdf_root)}, found: {pdf_paths_to_load}')
        filenames = [os.path.basename(path).split('.')[0] for path in pdf_paths_to_load]
    else:
        # Load specific PDFs
        requested_files_str = ", ".join(filenames)
        logger.info(f'[INFO / pdf_loading_utils / load_pdf_as_blocks] Attempting to load specific PDF files: {requested_files_str} from {os.path.abspath(pdf_root)}')
        for name in filenames:
            potential_path = os.path.join(pdf_root, f"{name}.pdf")
            if os.path.exists(potential_path) and potential_path.lower().endswith('.pdf'):
                pdf_paths_to_load.append(potential_path)
            else:
                logger.warning(f"[WARN / pdf_loading_utils / load_pdf_as_blocks] Requested file not found or not a PDF: {potential_path}")
        logger.info(f'[INFO / pdf_loading_utils / load_pdf_as_blocks] Found matching PDF files: {pdf_paths_to_load}')

    for path, name in zip(pdf_paths_to_load, filenames):
        try:
            # Extract text from PDF using PyMuPDF
            extracted_text = pdf_to_text(path)
            
            # Add a text block with the extracted content
            filename_context_block = {
                "type": "text",
                "text": f"--- Content from PDF: {name}.pdf ---\n\n{extracted_text}"
            }
            blocks.append(filename_context_block)
            logger.info(f"Added text block for {name}.pdf")

        except Exception as e:
            logger.error(f"Error processing file {path}: {e}", exc_info=True)

    return blocks
