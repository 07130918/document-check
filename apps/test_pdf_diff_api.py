#!/usr/bin/env python3
# coding: utf-8
"""
PDF差分検出API テストスクリプト (Python版)
"""

import requests
import os
import zipfile
from pathlib import Path
import tempfile
import time

# 設定
API_BASE_URL = "http://localhost:8000/api"
SAMPLE_DIR = Path("./sample")
OUTPUT_DIR = Path("./test_output")

def test_api_health():
    """APIサーバーの動作確認"""
    print("1. APIサーバーの動作確認...")
    try:
        response = requests.get(f"{API_BASE_URL}/../health", timeout=10)
        if response.status_code == 200:
            print("✓ APIサーバーが動作しています")
            return True
        else:
            print(f"✗ APIサーバーエラー: HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ APIサーバーに接続できません")
        return False
    except Exception as e:
        print(f"✗ APIサーバー確認エラー: {e}")
        return False

def check_sample_files():
    """サンプルPDFファイルの確認"""
    print("\n2. サンプルPDFファイルの確認...")

    sample1 = SAMPLE_DIR / "sample-1.pdf"
    sample2 = SAMPLE_DIR / "sample-2.pdf"

    if not sample1.exists():
        print(f"✗ サンプルPDFが見つかりません: {sample1}")
        return False, None, None

    if not sample2.exists():
        print(f"✗ サンプルPDFが見つかりません: {sample2}")
        return False, None, None

    print("✓ サンプルPDFファイルが見つかりました")
    print(f"  - {sample1} ({sample1.stat().st_size} bytes)")
    print(f"  - {sample2} ({sample2.stat().st_size} bytes)")

    return True, sample1, sample2

# Note: test_simple_diff() has been removed as /api/diff/simple endpoint no longer exists
# The main upload-based test covers the primary functionality

def test_upload_diff(sample1_path, sample2_path):
    """ファイルアップロード形式のPDF差分検出のテスト"""
    print("\n3. テスト1: ファイルアップロード形式のPDF差分検出 (/api/diff)")

    try:
        start_time = time.time()

        with open(sample1_path, 'rb') as f1, open(sample2_path, 'rb') as f2:
            files = {
                'document1': (sample1_path.name, f1, 'application/pdf'),
                'document2': (sample2_path.name, f2, 'application/pdf')
            }

            response = requests.post(
                f"{API_BASE_URL}/diff",
                files=files,
                headers={"Accept": "application/zip"},
                timeout=300  # 5分のタイムアウト
            )

        end_time = time.time()

        if response.status_code == 200:
            # ZIPファイルを保存
            output_path = OUTPUT_DIR / "upload_test_result.zip"
            with open(output_path, 'wb') as f:
                f.write(response.content)

            print(f"✓ テスト1成功 - ZIPファイルを受信しました ({end_time - start_time:.2f}秒)")
            print(f"  出力ファイル: {output_path}")
            print(f"  ZIPサイズ: {len(response.content)} bytes")

            # ZIPファイルの内容確認
            try:
                with zipfile.ZipFile(output_path, 'r') as zip_ref:
                    file_list = zip_ref.namelist()
                    print("  ZIPファイルの内容:")
                    for file_name in file_list:
                        print(f"    {file_name}")

                return True
            except Exception as e:
                print(f"  ⚠ ZIPファイル内容確認エラー: {e}")
                return True

        else:
            print(f"✗ テスト1失敗 - HTTPステータス: {response.status_code}")
            print(f"レスポンス: {response.text[:500]}")
            return False

    except requests.exceptions.Timeout:
        print("✗ テスト1失敗 - タイムアウト (5分)")
        return False
    except Exception as e:
        print(f"✗ テスト1失敗 - エラー: {e}")
        return False

def test_pages_diff(sample1_path, sample2_path):
    """ページ指定付きのPDF差分検出のテスト"""
    print("\n4. テスト2: ページ指定付きのPDF差分検出 (/api/diff with pages=1)")

    try:
        start_time = time.time()

        with open(sample1_path, 'rb') as f1, open(sample2_path, 'rb') as f2:
            files = {
                'document1': (sample1_path.name, f1, 'application/pdf'),
                'document2': (sample2_path.name, f2, 'application/pdf')
            }
            data = {'pages': '1'}

            response = requests.post(
                f"{API_BASE_URL}/diff",
                files=files,
                data=data,
                headers={"Accept": "application/zip"},
                timeout=300
            )

        end_time = time.time()

        if response.status_code == 200:
            output_path = OUTPUT_DIR / "pages_test_result.zip"
            with open(output_path, 'wb') as f:
                f.write(response.content)

            print(f"✓ テスト2成功 - ページ指定付きZIPファイルを受信しました ({end_time - start_time:.2f}秒)")
            print(f"  出力ファイル: {output_path}")
            print(f"  ZIPサイズ: {len(response.content)} bytes")

            return True

        else:
            print(f"✗ テスト2失敗 - HTTPステータス: {response.status_code}")
            print(f"レスポンス: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"✗ テスト2失敗 - エラー: {e}")
        return False

def test_invalid_file():
    """無効なファイル形式のテスト"""
    print("\n5. テスト3: 無効なファイル形式のテスト")

    try:
        # 一時的な非PDFファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write("This is not a PDF file")
            temp_path = temp_file.name

        try:
            with open(temp_path, 'rb') as invalid_file, open(SAMPLE_DIR / "sample-1.pdf", 'rb') as valid_file:
                files = {
                    'document1': ('test.txt', invalid_file, 'text/plain'),
                    'document2': ('sample-1.pdf', valid_file, 'application/pdf')
                }

                response = requests.post(
                    f"{API_BASE_URL}/diff",
                    files=files,
                    headers={"Accept": "application/zip"},
                    timeout=30
                )

            if response.status_code == 400:
                print("✓ テスト3成功 - 無効なファイル形式を正しく検出しました")
                print(f"  HTTPステータス: {response.status_code}")
                return True
            else:
                print(f"✗ テスト3失敗 - 期待したHTTPステータス400を受信できませんでした")
                print(f"  受信したHTTPステータス: {response.status_code}")
                return False

        finally:
            # 一時ファイルを削除
            os.unlink(temp_path)

    except Exception as e:
        print(f"✗ テスト3失敗 - エラー: {e}")
        return False

def main():
    """メイン処理"""
    print("=== PDF差分検出API テストスクリプト (Python版) ===")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Output Directory: {OUTPUT_DIR}")

    # 出力ディレクトリを作成
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # テスト実行
    results = []

    # 1. APIサーバーの動作確認
    if not test_api_health():
        print("\nAPIサーバーに接続できないため、テストを中止します")
        return

    # 2. サンプルファイルの確認
    has_samples, sample1, sample2 = check_sample_files()
    if not has_samples:
        print("\nサンプルPDFファイルが見つからないため、テストを中止します")
        return

    # 3. 各テストを実行
    results.append(("アップロード差分検出", test_upload_diff(sample1, sample2)))
    results.append(("ページ指定差分検出", test_pages_diff(sample1, sample2)))
    results.append(("無効ファイル形式", test_invalid_file()))

    # 結果サマリー
    print("\n=== テスト結果サマリー ===")
    success_count = 0
    for test_name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {test_name}: {'成功' if result else '失敗'}")
        if result:
            success_count += 1

    print(f"\n成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")

    print(f"\n出力ディレクトリ: {OUTPUT_DIR}")
    print("生成されたファイル:")
    for file_path in OUTPUT_DIR.iterdir():
        if file_path.is_file():
            print(f"  {file_path} ({file_path.stat().st_size} bytes)")

    print("\nテスト完了！")

if __name__ == "__main__":
    main()
