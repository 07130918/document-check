"""PDF diff detection endpoint router."""
import subprocess
import tempfile
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# 出力ディレクトリの設定
OUTPUT_DIR = Path("/app/llm_docs_diff_v3.4/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/diff")
async def detect_pdf_diff(
    file1: UploadFile = File(..., description="First PDF file"),
    file2: UploadFile = File(..., description="Second PDF file"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Detect differences between two PDF files.

    Args:
        file1: First PDF file to compare
        file2: Second PDF file to compare

    Returns:
        dict: Result of the diff detection including status and output location
    """
    # PDFファイルの検証
    if not file1.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File1 must be a PDF file")
    if not file2.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File2 must be a PDF file")

    # 一時ディレクトリを作成してPDFを保存
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # PDFファイルを一時保存
        file1_path = temp_path / file1.filename
        file2_path = temp_path / file2.filename

        try:
            # ファイル保存
            with open(file1_path, "wb") as f:
                content = await file1.read()
                f.write(content)

            with open(file2_path, "wb") as f:
                content = await file2.read()
                f.write(content)

            logger.info(f"Saved PDFs: {file1_path}, {file2_path}")

            # スクリプトを実行
            script_path = "/app/llm_docs_diff_v3.4/test_llm_diff_v3_4.py"

            # Python実行コマンド
            cmd = [
                "uv", "run", "python",
                script_path,
                str(file1_path),
                str(file2_path)
            ]

            logger.info(f"Executing command: {' '.join(cmd)}")

            # スクリプトを実行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd="/app",
                timeout=300  # 5分のタイムアウト
            )

            # 実行結果をログ
            if result.stdout:
                logger.info(f"Script output: {result.stdout[:500]}")
            if result.stderr:
                logger.error(f"Script error: {result.stderr[:500]}")

            # 結果を解析
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Script execution failed: {result.stderr}"
                )

            # 出力ファイルを探す
            output_files = list(OUTPUT_DIR.glob("*.json"))
            latest_output = None
            if output_files:
                # 最新のファイルを取得
                latest_output = max(output_files, key=lambda p: p.stat().st_mtime)

                # JSONファイルを読み込む
                try:
                    with open(latest_output, 'r', encoding='utf-8') as f:
                        diff_result = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to read output JSON: {e}")
                    diff_result = None
            else:
                diff_result = None

            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "PDF diff detection completed",
                    "files": {
                        "file1": file1.filename,
                        "file2": file2.filename
                    },
                    "output": {
                        "stdout": result.stdout[-1000:] if result.stdout else "",
                        "output_file": str(latest_output) if latest_output else None,
                        "summary": diff_result.get("summary") if diff_result else None
                    }
                }
            )

        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=504,
                detail="Script execution timeout (exceeded 5 minutes)"
            )
        except Exception as e:
            logger.error(f"Error during diff detection: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error during diff detection: {str(e)}"
            )


@router.post("/diff/simple")
async def detect_pdf_diff_simple():
    """
    Detect differences between default sample PDF files.

    Returns:
        dict: Result of the diff detection including status and output location
    """
    # デフォルトのサンプルPDFパス
    sample1_path = Path("/app/sample/sample-1.pdf")
    sample2_path = Path("/app/sample/sample-2.pdf")

    # サンプルファイルが存在するか確認
    if not sample1_path.exists() or not sample2_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Sample PDF files not found in /app/sample directory"
        )

    try:
        # スクリプトを実行
        script_path = "/app/llm_docs_diff_v3.4/test_llm_diff_v3_4.py"

        # Python実行コマンド
        cmd = [
            "uv", "run", "python",
            script_path,
            str(sample1_path),
            str(sample2_path)
        ]

        logger.info(f"Executing command: {' '.join(cmd)}")

        # スクリプトを実行
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd="/app",
            timeout=300  # 5分のタイムアウト
        )

        # 実行結果をログ
        if result.stdout:
            logger.info(f"Script output: {result.stdout[:500]}")
        if result.stderr:
            logger.error(f"Script error: {result.stderr[:500]}")

        # 結果を解析
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Script execution failed: {result.stderr}"
            )

        # 出力ファイルを探す
        output_files = list(OUTPUT_DIR.glob("*.json"))
        latest_output = None
        if output_files:
            # 最新のファイルを取得
            latest_output = max(output_files, key=lambda p: p.stat().st_mtime)

            # JSONファイルを読み込む
            try:
                with open(latest_output, 'r', encoding='utf-8') as f:
                    diff_result = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read output JSON: {e}")
                diff_result = None
        else:
            diff_result = None

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "PDF diff detection completed",
                "files": {
                    "file1": sample1_path.name,
                    "file2": sample2_path.name
                },
                "output": {
                    "stdout": result.stdout[-1000:] if result.stdout else "",
                    "output_file": str(latest_output) if latest_output else None,
                    "summary": diff_result.get("summary") if diff_result else None
                }
            }
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Script execution timeout (exceeded 5 minutes)"
        )
    except Exception as e:
        logger.error(f"Error during diff detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error during diff detection: {str(e)}"
        )
