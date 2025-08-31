# coding: utf-8

"""
FILE: analyze_page2_with_coordinates.py

DESCRIPTION:
    Page 2 analysis with coordinate information for sections and paragraphs.
"""

import os
import json
from datetime import datetime


def get_polygon_bbox(polygon):
    """
    ポリゴンからbounding boxを計算
    """
    if not polygon:
        return None
    
    # ポリゴンがfloatのリストの場合（x1, y1, x2, y2, ...形式）
    if len(polygon) >= 4:
        x_coords = [polygon[i] for i in range(0, len(polygon), 2)]
        y_coords = [polygon[i] for i in range(1, len(polygon), 2)]
        
        return {
            "left": min(x_coords),
            "top": min(y_coords),
            "right": max(x_coords),
            "bottom": max(y_coords),
            "width": max(x_coords) - min(x_coords),
            "height": max(y_coords) - min(y_coords)
        }
    return None


def get_spans_bbox(spans, full_content):
    """
    スパンから座標情報を取得
    """
    if not spans:
        return None, ""
    
    bboxes = []
    contents = []
    
    for span in spans:
        if hasattr(span, 'offset') and hasattr(span, 'length'):
            start = span.offset
            end = span.offset + span.length
            content = full_content[start:end]
            contents.append(content)
        
        # スパンに座標情報がある場合
        if hasattr(span, 'polygon') and span.polygon:
            bbox = get_polygon_bbox(span.polygon)
            if bbox:
                bboxes.append(bbox)
    
    # 複数のbboxを統合
    if bboxes:
        combined_bbox = {
            "left": min(bbox["left"] for bbox in bboxes),
            "top": min(bbox["top"] for bbox in bboxes),
            "right": max(bbox["right"] for bbox in bboxes),
            "bottom": max(bbox["bottom"] for bbox in bboxes)
        }
        combined_bbox["width"] = combined_bbox["right"] - combined_bbox["left"]
        combined_bbox["height"] = combined_bbox["bottom"] - combined_bbox["top"]
        return combined_bbox, " ".join(contents)
    
    return None, " ".join(contents)


def find_paragraph_in_lines(paragraph, lines):
    """
    段落に対応する行を見つけて座標情報を取得
    """
    if not lines or not paragraph.content:
        return None
    
    para_content = paragraph.content.strip()
    
    # 段落内容に一致する行を探す
    matching_lines = []
    for line in lines:
        if hasattr(line, 'content') and line.content.strip() in para_content:
            matching_lines.append(line)
    
    if not matching_lines:
        return None
    
    # 行のポリゴン情報から座標を計算
    bboxes = []
    for line in matching_lines:
        if hasattr(line, 'polygon') and line.polygon:
            bbox = get_polygon_bbox(line.polygon)
            if bbox:
                bboxes.append(bbox)
    
    if bboxes:
        combined_bbox = {
            "left": min(bbox["left"] for bbox in bboxes),
            "top": min(bbox["top"] for bbox in bboxes),
            "right": max(bbox["right"] for bbox in bboxes),
            "bottom": max(bbox["bottom"] for bbox in bboxes)
        }
        combined_bbox["width"] = combined_bbox["right"] - combined_bbox["left"]
        combined_bbox["height"] = combined_bbox["bottom"] - combined_bbox["top"]
        return combined_bbox
    
    return None


def analyze_page2_with_coordinates():
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.documentintelligence import DocumentIntelligenceClient

    endpoint = os.environ["AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"]
    key = os.environ["AZURE_DOCUMENT_INTELLIGENCE_KEY"]
    
    pdf_file_path = "data/data2/sougou/サンプル②2025.pdf"

    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    
    with open(pdf_file_path, "rb") as f:
        document_content = f.read()
        
    # Page 2のみを指定して分析
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=document_content,
        content_type="application/pdf",
        pages="2"
    )
    result = poller.result()
    
    print("=== PAGE 2 ANALYSIS WITH COORDINATES ===")
    
    full_content = result.content if hasattr(result, 'content') else ""
    paragraphs = result.paragraphs if hasattr(result, 'paragraphs') else []
    lines = result.pages[0].lines if (hasattr(result, 'pages') and result.pages and 
                                     hasattr(result.pages[0], 'lines')) else []
    
    print(f"Total paragraphs: {len(paragraphs)}")
    print(f"Total lines: {len(lines)}")
    
    # 段落の役割に基づいてセクションを識別（座標情報付き）
    sections = []
    current_section = None
    
    for i, para in enumerate(paragraphs):
        role = getattr(para, 'role', None)
        content = para.content.strip()
        
        # 段落の座標情報を取得
        para_bbox = None
        if hasattr(para, 'spans') and para.spans:
            para_bbox, _ = get_spans_bbox(para.spans, full_content)
        
        # 行レベルから座標情報を取得（fallback）
        if not para_bbox:
            para_bbox = find_paragraph_in_lines(para, lines)
        
        para_info = {
            "content": content,
            "role": str(role) if role else None,
            "length": len(content),
            "paragraph_index": i,
            "coordinates": para_bbox
        }
        
        # セクション見出しまたはタイトルの場合、新しいセクションを開始
        if (role and str(role) in ['ParagraphRole.TITLE', 'ParagraphRole.SECTION_HEADING']):
            if current_section is not None:
                sections.append(current_section)
            
            current_section = {
                "title": content,
                "paragraphs": [],
                "start_paragraph_index": i,
                "coordinates": para_bbox  # セクションの座標はタイトル段落の座標
            }
            
            current_section["paragraphs"].append(para_info)
        else:
            # 現在のセクションに段落を追加
            if current_section is not None:
                current_section["paragraphs"].append(para_info)
                
                # セクションの座標を拡張（全ての段落を含むように）
                if current_section["coordinates"] and para_bbox:
                    current_bbox = current_section["coordinates"]
                    current_section["coordinates"] = {
                        "left": min(current_bbox["left"], para_bbox["left"]),
                        "top": min(current_bbox["top"], para_bbox["top"]),
                        "right": max(current_bbox["right"], para_bbox["right"]),
                        "bottom": max(current_bbox["bottom"], para_bbox["bottom"])
                    }
                    current_section["coordinates"]["width"] = (
                        current_section["coordinates"]["right"] - current_section["coordinates"]["left"]
                    )
                    current_section["coordinates"]["height"] = (
                        current_section["coordinates"]["bottom"] - current_section["coordinates"]["top"]
                    )
                elif para_bbox and not current_section["coordinates"]:
                    current_section["coordinates"] = para_bbox
            else:
                # 最初のセクションが見つかる前の段落は「前置き」セクションに
                if not sections:
                    sections.append({
                        "title": "前置き",
                        "paragraphs": [],
                        "start_paragraph_index": 0,
                        "coordinates": para_bbox
                    })
                sections[0]["paragraphs"].append(para_info)
                
                # 前置きセクションの座標を拡張
                if sections[0]["coordinates"] and para_bbox:
                    current_bbox = sections[0]["coordinates"]
                    sections[0]["coordinates"] = {
                        "left": min(current_bbox["left"], para_bbox["left"]),
                        "top": min(current_bbox["top"], para_bbox["top"]),
                        "right": max(current_bbox["right"], para_bbox["right"]),
                        "bottom": max(current_bbox["bottom"], para_bbox["bottom"])
                    }
                    sections[0]["coordinates"]["width"] = (
                        sections[0]["coordinates"]["right"] - sections[0]["coordinates"]["left"]
                    )
                    sections[0]["coordinates"]["height"] = (
                        sections[0]["coordinates"]["bottom"] - sections[0]["coordinates"]["top"]
                    )
    
    # 最後のセクションを追加
    if current_section is not None:
        sections.append(current_section)
    
    # 分析結果をまとめる
    coord_analysis = {
        "source_file": pdf_file_path,
        "analyzed_at": datetime.now().isoformat(),
        "target_page": 2,
        "summary": {
            "total_sections": len(sections),
            "total_paragraphs": len(paragraphs),
            "paragraphs_with_coordinates": sum(1 for s in sections for p in s["paragraphs"] if p["coordinates"]),
            "sections_with_coordinates": sum(1 for s in sections if s["coordinates"])
        },
        "sections": []
    }
    
    print(f"\n=== COORDINATE ANALYSIS ===")
    for i, section in enumerate(sections):
        section_content = " ".join([p["content"] for p in section["paragraphs"]])
        
        section_analysis = {
            "section_number": i + 1,
            "title": section["title"],
            "content_length": len(section_content),
            "word_count": len(section_content.split()),
            "paragraph_count": len(section["paragraphs"]),
            "coordinates": section["coordinates"],
            "paragraphs": section["paragraphs"]
        }
        
        coord_analysis["sections"].append(section_analysis)
        
        print(f"\nSection {i+1}: {section['title']}")
        print(f"  Paragraphs: {len(section['paragraphs'])}")
        print(f"  Content length: {len(section_content)}")
        
        if section["coordinates"]:
            coords = section["coordinates"]
            print(f"  Coordinates: left={coords['left']:.3f}, top={coords['top']:.3f}, "
                  f"right={coords['right']:.3f}, bottom={coords['bottom']:.3f}")
            print(f"  Size: width={coords['width']:.3f}, height={coords['height']:.3f}")
        else:
            print(f"  Coordinates: Not available")
        
        # 段落の詳細表示（座標情報含む）
        for j, para in enumerate(section["paragraphs"][:3]):
            role_text = f"({para['role']}) " if para['role'] else ""
            print(f"    {j+1}. {role_text}{para['content'][:80]}...")
            
            if para["coordinates"]:
                coords = para["coordinates"]
                print(f"        coords: ({coords['left']:.3f}, {coords['top']:.3f}) - "
                      f"({coords['right']:.3f}, {coords['bottom']:.3f})")
            else:
                print(f"        coords: Not available")
        
        if len(section["paragraphs"]) > 3:
            print(f"    ... その他 {len(section['paragraphs']) - 3} 段落")
    
    # 結果をファイルに保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON形式
    json_output_file = f"playground/page2_coordinates_{timestamp}.json"
    with open(json_output_file, "w", encoding="utf-8") as f:
        json.dump(coord_analysis, f, ensure_ascii=False, indent=2)
    
    # Markdown形式
    md_output_file = f"playground/page2_coordinates_{timestamp}.md"
    with open(md_output_file, "w", encoding="utf-8") as f:
        f.write("# Page 2 座標情報付き分析レポート\n\n")
        f.write(f"**ソースファイル:** {pdf_file_path}\n")
        f.write(f"**対象ページ:** Page 2\n")
        f.write(f"**分析日時:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 概要\n\n")
        summary = coord_analysis["summary"]
        f.write(f"- セクション数: {summary['total_sections']}\n")
        f.write(f"- 総段落数: {summary['total_paragraphs']}\n")
        f.write(f"- 座標情報付き段落数: {summary['paragraphs_with_coordinates']}\n")
        f.write(f"- 座標情報付きセクション数: {summary['sections_with_coordinates']}\n\n")
        
        f.write("## セクション詳細（座標情報付き）\n\n")
        for section in coord_analysis["sections"]:
            f.write(f"### {section['section_number']}. {section['title']}\n\n")
            
            # セクション統計と座標
            f.write(f"**統計:**\n")
            f.write(f"- 文字数: {section['content_length']:,}\n")
            f.write(f"- 単語数: {section['word_count']:,}\n")
            f.write(f"- 段落数: {section['paragraph_count']}\n")
            
            if section['coordinates']:
                coords = section['coordinates']
                f.write(f"- 座標: ({coords['left']:.3f}, {coords['top']:.3f}) - ({coords['right']:.3f}, {coords['bottom']:.3f})\n")
                f.write(f"- サイズ: {coords['width']:.3f} × {coords['height']:.3f}\n")
            else:
                f.write(f"- 座標: 取得不可\n")
            f.write("\n")
            
            # 段落詳細（座標情報付き）
            f.write(f"**段落詳細:**\n")
            for para in section['paragraphs']:
                role_text = f"({para['role']}) " if para['role'] else ""
                content_preview = para['content'][:100] + "..." if len(para['content']) > 100 else para['content']
                f.write(f"- {role_text}{content_preview}\n")
                
                if para['coordinates']:
                    coords = para['coordinates']
                    f.write(f"  - 座標: ({coords['left']:.3f}, {coords['top']:.3f}) - ({coords['right']:.3f}, {coords['bottom']:.3f})\n")
                    f.write(f"  - サイズ: {coords['width']:.3f} × {coords['height']:.3f}\n")
                else:
                    f.write(f"  - 座標: 取得不可\n")
                f.write("\n")
            
            f.write("---\n\n")
        
        f.write("## 座標情報の活用方法\n\n")
        f.write("この座標情報により以下が可能になります：\n")
        f.write("1. **視覚的な位置関係の理解**: 各セクション・段落のページ内での配置\n")
        f.write("2. **差分検出の精度向上**: 位置情報に基づく対応関係の特定\n")
        f.write("3. **レイアウト分析**: 文書のデザイン構造の理解\n")
        f.write("4. **OCR品質評価**: 座標精度による認識品質の評価\n")
    
    print(f"\n=== RESULTS SAVED ===")
    print(f"座標情報付き分析結果（JSON）: {json_output_file}")
    print(f"座標情報付き分析結果（Markdown）: {md_output_file}")
    
    # ファイルサイズとデータ品質確認
    json_size = os.path.getsize(json_output_file)
    md_size = os.path.getsize(md_output_file)
    print(f"JSON file size: {json_size:,} bytes")
    print(f"Markdown file size: {md_size:,} bytes")
    print(f"Coordinate coverage: {summary['paragraphs_with_coordinates']}/{summary['total_paragraphs']} paragraphs")
    
    return result, coord_analysis


if __name__ == "__main__":
    from azure.core.exceptions import HttpResponseError
    from dotenv import find_dotenv, load_dotenv

    try:
        load_dotenv(find_dotenv())
        analyze_page2_with_coordinates()
    except HttpResponseError as error:
        if error.error is not None:
            if error.error.code == "InvalidImage":
                print(f"Received an invalid image error: {error.error}")
            if error.error.code == "InvalidRequest":
                print(f"Received an invalid request error: {error.error}")
            raise
        if "Invalid request".casefold() in error.message.casefold():
            print(f"Uh-oh! Seems there was an invalid request: {error}")
        raise