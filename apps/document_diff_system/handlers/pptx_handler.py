"""
PPTX Handler using python-pptx
"""
from typing import List
from io import BytesIO
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR
from ..models import BBoxTextData


class PptxService:
    """python-pptxを使用したPowerPoint処理サービス"""
    
    def extract_bbox_data(self, pptx_bytes: bytes) -> List[BBoxTextData]:
        """
        PowerPointからbbox_text_dataを抽出
        
        Args:
            pptx_bytes: PowerPointファイルのバイトデータ
            
        Returns:
            bbox_text_dataのリスト
        """
        bbox_data_list = []
        
        # PowerPointを開く
        prs = Presentation(BytesIO(pptx_bytes))
        
        for slide_num, slide in enumerate(prs.slides):
            # スライド内のすべてのシェイプを処理
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                
                # シェイプの位置とサイズを取得
                left = shape.left
                top = shape.top
                width = shape.width
                height = shape.height
                
                # テキストフレーム内のテキストを処理
                for paragraph in shape.text_frame.paragraphs:
                    # 段落内のテキストを単語に分割
                    words = paragraph.text.split()
                    
                    # 各単語に対して擬似的なbboxを生成
                    y_offset = 0
                    for i, word in enumerate(words):
                        if not word:
                            continue
                        
                        # 単語の幅を推定
                        word_width = len(word) * 12  # 概算
                        line_height = 20
                        
                        # 段落内での相対位置
                        x_offset = i * (word_width + 5)
                        
                        # 行の折り返しを考慮（簡易版）
                        if x_offset + word_width > width:
                            x_offset = 0
                            y_offset += line_height
                        
                        bbox_data = BBoxTextData(
                            bbox=[
                                left + x_offset,
                                top + y_offset,
                                word_width,
                                line_height
                            ],
                            text=word,
                            page=slide_num
                        )
                        bbox_data_list.append(bbox_data)
        
        return bbox_data_list
    
    def add_highlights_to_pptx(self, pptx_bytes: bytes, highlights: List[dict]) -> bytes:
        """
        PowerPointにハイライトを追加
        
        Args:
            pptx_bytes: 元のPowerPointのバイトデータ
            highlights: ハイライト情報のリスト
            
        Returns:
            ハイライトが追加されたPowerPointのバイトデータ
        """
        prs = Presentation(BytesIO(pptx_bytes))
        
        # スライドごとのハイライト情報を整理
        highlights_by_slide = {}
        for highlight in highlights:
            slide_num = highlight['page']
            if slide_num not in highlights_by_slide:
                highlights_by_slide[slide_num] = []
            highlights_by_slide[slide_num].append(highlight)
        
        # 各スライドにハイライトを追加
        for slide_num, slide_highlights in highlights_by_slide.items():
            if slide_num >= len(prs.slides):
                continue
                
            slide = prs.slides[slide_num]
            
            for highlight in slide_highlights:
                # ハイライト用の矩形シェイプを追加
                left = int(highlight['bbox'][0])
                top = int(highlight['bbox'][1])
                width = int(highlight['bbox'][2])
                height = int(highlight['bbox'][3])
                
                # 半透明の矩形を追加
                shape = slide.shapes.add_shape(
                    1,  # 矩形
                    left, top, width, height
                )
                
                # 塗りつぶし色を設定
                fill = shape.fill
                fill.solid()
                fill.fore_color.rgb = self._get_rgb_color(highlight['color'])
                
                # 透明度を設定
                shape.fill.transparency = 0.5
                
                # 枠線を非表示
                shape.line.fill.background()
                
                # ラベルがある場合はテキストボックスを追加
                if highlight.get('label'):
                    textbox = slide.shapes.add_textbox(
                        left, top - 20, width, 20
                    )
                    textbox.text = highlight['label']
                    textbox.text_frame.paragraphs[0].font.size = Pt(10)
                    textbox.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 0, 255)
        
        # バイトデータとして保存
        output = BytesIO()
        prs.save(output)
        output.seek(0)
        return output.read()
    
    def _get_rgb_color(self, color_name: str) -> RGBColor:
        """色名をRGBColorに変換"""
        colors = {
            'red': RGBColor(255, 0, 0),
            'green': RGBColor(0, 255, 0),
            'yellow': RGBColor(255, 255, 0),
            'blue': RGBColor(0, 0, 255)
        }
        return colors.get(color_name, RGBColor(255, 255, 0))