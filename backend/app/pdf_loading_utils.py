import os
import base64
import glob
import logging

logger = logging.getLogger(__name__)

MAX_INLINE_MB = 10     # keep token usage reasonable

def load_pdf_as_blocks(pdf_root='./files', filenames: list[str] | None = None) -> list[dict]:
    """Return a list of {'type':'document', ...} blocks for PDFs in ./files.
    
    Args:
        filenames: Optional list of filenames (without extension) to load.
                   If None, loads all PDFs in the pdf_root.
                   Example: ['document1', 'report_final']
    
    Returns:
        A list of document blocks.
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
        size_mb = os.path.getsize(path) / 1_048_576
        if size_mb > MAX_INLINE_MB:
            logger.warning(f"⚠️  Skipping {os.path.basename(path)} – {size_mb:.1f} MB > {MAX_INLINE_MB} MB inline limit")
            continue

        try:
            with open(path, "rb") as f:
                # Read original content
                original_content = f.read()

            # Prepend filename information - NOTE: This might corrupt the PDF structure for some parsers.
            # Consider adding filename context as a separate text block in the message if issues arise.
            # filename_info = f"Content of file: {name}.pdf\n\n---\n\n".encode('utf-8')
            # combined_content = filename_info + original_content
            # b64_pdf = base64.b64encode(combined_content).decode('utf-8')

            # Encode the original content directly as per standard practice
            b64_pdf = base64.b64encode(original_content).decode('utf-8')

            # Structure the document block according to Anthropic API spec (no top-level 'name')
            pdf_block = {
                "type": "document",
                # The 'name' field caused the BadRequestError and is removed.
                # Filename context should be provided elsewhere, e.g., in a preceding text block.
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64_pdf
                }
            }
            # Add a text block *before* the document block to provide filename context
            filename_context_block = {
                "type": "text",
                "text": f"--- Attached PDF: {name}.pdf ---"
            }
            blocks.append(filename_context_block)
            blocks.append(pdf_block)
            logger.info(f"Added document block for {name}.pdf")

        except Exception as e:
            logger.error(f"Error processing file {path}: {e}", exc_info=True)

    return blocks
