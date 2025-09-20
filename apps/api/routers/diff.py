"""PDF diff detection endpoint router."""

import sys
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import logging
import io
import importlib.util
from datetime import datetime

# プロジェクトルートをPATHに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "llm_docs_diff_v3.4"))

# LLM差分検出のAPIファンクションをインポート - 遅延インポート
process_pdf_bytes_api = None


def get_process_pdf_bytes_api():
    """API関数を遅延インポートで取得"""
    global process_pdf_bytes_api
    if process_pdf_bytes_api is None:
        spec = importlib.util.spec_from_file_location(
            "test_llm_diff_v3_4",
            project_root / "llm_docs_diff_v3.4" / "test_llm_diff_v3_4.py",
        )
        test_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(test_module)
        process_pdf_bytes_api = test_module.process_pdf_bytes_api
    return process_pdf_bytes_api


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/diff")
async def detect_pdf_diff(
    document1: UploadFile = File(..., description="First PDF document to compare"),
    document2: UploadFile = File(..., description="Second PDF document to compare"),
    pages: str = None,
) -> StreamingResponse:
    """
    2つのPDFファイルの差分を検出し、注釈付きPDFをZIP形式で返す。

    Args:
        document1: 比較する最初のPDFファイル
        document2: 比較する2番目のPDFファイル
        pages: オプションのページ範囲 (例: "1-5" または "1,3,5")

    Returns:
        StreamingResponse: 注釈付きPDFと差分結果を含むZIPファイル
    """
    # PDFファイルの検証
    if not document1.filename or not document1.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="document1 must be a PDF file")

    if not document2.filename or not document2.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="document2 must be a PDF file")

    # ファイルサイズ制限（100MB）
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    try:
        # ファイルのバイナリデータを読み取り
        logger.info(f"Reading PDF files: {document1.filename}, {document2.filename}")

        pdf1_bytes = await document1.read()
        pdf2_bytes = await document2.read()

        # ファイルサイズチェック
        if len(pdf1_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"document1 is too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)",
            )
        if len(pdf2_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"document2 is too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)",
            )

        # 基本的なPDFファイル検証
        if not pdf1_bytes.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400, detail="document1 is not a valid PDF file"
            )
        if not pdf2_bytes.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400, detail="document2 is not a valid PDF file"
            )

        logger.info(f"File sizes: {len(pdf1_bytes)} bytes, {len(pdf2_bytes)} bytes")

        # インプロセスでPDF差分検出を実行
        logger.info("Starting in-process PDF diff detection")
        api_func = get_process_pdf_bytes_api()
        zip_data = api_func(
            pdf1_bytes=pdf1_bytes,
            pdf2_bytes=pdf2_bytes,
            filename1=document1.filename,
            filename2=document2.filename,
            pages=pages,
        )

        logger.info(f"PDF diff detection completed, ZIP size: {len(zip_data)} bytes")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"pdf_diff_result_{timestamp}.zip"

        return StreamingResponse(
            io.BytesIO(zip_data),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}",
                "Content-Length": str(len(zip_data)),
            },
        )
    except HTTPException:
        # HTTPExceptionはそのまま再発生
        raise
    except Exception as e:
        logger.error(f"Error during PDF diff detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during PDF diff detection: {str(e)}",
        )
