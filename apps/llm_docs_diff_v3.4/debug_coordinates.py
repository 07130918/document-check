# coding: utf-8
"""
座標取得デバッグスクリプト - v3.4用
Document Intelligence API から取得する座標情報の詳細を確認
"""

import os
import json
import logging
from services.azure_service_structured import StructuredAzureService

# ログ設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_coordinate_extraction():
    """座標取得をデバッグ"""
    
    # テスト用PDFファイル
    test_file = "/home/dev/prj-ms-document-check.worktree/worktree1/data/data2/sougou/サンプル②2024 .pdf"
    
    # Azure Document Intelligenceサービス初期化
    service = StructuredAzureService()
    
    print("=== 座標取得デバッグ開始 ===")
    print(f"対象ファイル: {test_file}")
    print()
    
    # Document Intelligence API の生レスポンスを確認
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    
    client = DocumentIntelligenceClient(
        endpoint=service.endpoint,
        credential=AzureKeyCredential(service.key)
    )
    
    with open(test_file, "rb") as f:
        document_content = f.read()
    
    # 分析実行
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=document_content,
        content_type="application/pdf",
        pages="2"
    )
    result = poller.result()
    
    print("=== Document Intelligence 生レスポンス情報 ===")
    print(f"段落数: {len(result.paragraphs) if result.paragraphs else 0}")
    print(f"ページ数: {len(result.pages) if result.pages else 0}")
    
    # 最初のいくつかの段落を詳細確認
    if result.paragraphs:
        print("\n=== 最初の3段落の詳細情報 ===")
        for i, para in enumerate(result.paragraphs[:3]):
            print(f"\n段落 {i+1}:")
            print(f"  テキスト: {para.content[:50]}...")
            print(f"  役割: {para.role if hasattr(para, 'role') else 'None'}")
            
            # スパン情報確認
            if hasattr(para, 'spans') and para.spans:
                print(f"  スパン数: {len(para.spans)}")
                for j, span in enumerate(para.spans[:2]):  # 最初の2スパン
                    print(f"    スパン {j+1}:")
                    print(f"      オフセット: {span.offset if hasattr(span, 'offset') else 'None'}")
                    print(f"      長さ: {span.length if hasattr(span, 'length') else 'None'}")
                    if hasattr(span, 'polygon') and span.polygon:
                        print(f"      ポリゴン: {span.polygon[:8]}...")  # 最初の8座標
                    else:
                        print(f"      ポリゴン: None")
            else:
                print("  スパン情報: None")
    
    # ページ情報確認
    if result.pages:
        page = result.pages[0]
        print(f"\n=== ページ情報 ===")
        print(f"ページ番号: {page.page_number if hasattr(page, 'page_number') else 'None'}")
        print(f"幅: {page.width if hasattr(page, 'width') else 'None'}")
        print(f"高さ: {page.height if hasattr(page, 'height') else 'None'}")
        print(f"行数: {len(page.lines) if hasattr(page, 'lines') and page.lines else 0}")
        
        # 最初のいくつかの行を確認
        if hasattr(page, 'lines') and page.lines:
            print(f"\n=== 最初の3行の詳細情報 ===")
            for i, line in enumerate(page.lines[:3]):
                print(f"\n行 {i+1}:")
                print(f"  テキスト: {line.content if hasattr(line, 'content') else 'None'}")
                if hasattr(line, 'polygon') and line.polygon:
                    print(f"  ポリゴン: {line.polygon}")
                else:
                    print(f"  ポリゴン: None")
    
    print("\n=== 構造化分析実行 ===")
    
    # 実際の構造化分析を実行
    structured_result = service.analyze_document_structured(test_file, pages="2")
    
    # 結果の座標情報を確認
    print(f"\nセクション数: {structured_result['summary']['total_sections']}")
    print(f"段落数: {structured_result['summary']['total_paragraphs']}")
    
    # 最初のいくつかのセクションの座標情報を確認
    for i, section in enumerate(structured_result['sections'][:3]):
        print(f"\nセクション {i+1}: {section['title']}")
        print(f"  セクション座標: {section['coordinates']}")
        
        # 段落の座標も確認
        for j, para in enumerate(section['paragraphs'][:2]):
            print(f"  段落 {j+1}: {para['content'][:30]}...")
            print(f"    座標: {para['coordinates']}")
    
    print("\n=== デバッグ完了 ===")

if __name__ == "__main__":
    debug_coordinate_extraction()