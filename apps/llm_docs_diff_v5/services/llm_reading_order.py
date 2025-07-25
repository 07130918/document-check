"""
LLMベースの読み順序決定サービス
ブロック画像とOCR結果を使って、LLMで読み順序を決定
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
import base64
from io import BytesIO
from PIL import Image
import numpy as np

from openai import OpenAI
from ..config.settings import settings
from ..models.block_models import Block, TextElement, BoundingBox

logger = logging.getLogger(__name__)


class LLMReadingOrderService:
    """LLMを使った読み順序決定サービス"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Args:
            api_key: OpenAI APIキー
            model: 使用するモデル
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.client = OpenAI(api_key=self.api_key)
    
    def determine_reading_order(self, 
                              block_image: np.ndarray,
                              ocr_elements: List[Dict[str, Any]]) -> List[TextElement]:
        """
        ブロック画像とOCR要素から読み順序を決定
        
        Args:
            block_image: ブロックの画像
            ocr_elements: OCRで抽出されたテキスト要素のリスト
                         各要素は {'text': str, 'bbox': [x, y, w, h]} の形式
        
        Returns:
            読み順序でソートされたTextElementのリスト
        """
        if not ocr_elements:
            return []
        
        # 画像をbase64エンコード
        image_base64 = self._image_to_base64(block_image)
        
        # プロンプトを構築
        prompt = self._build_prompt(ocr_elements)
        
        try:
            # LLMに問い合わせ
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in document layout analysis. Your task is to determine the correct reading order of text elements in a document block based on visual layout."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            # レスポンスをパース
            result_text = response.choices[0].message.content
            reading_order = self._parse_llm_response(result_text, ocr_elements)
            
            # TextElementオブジェクトに変換
            ordered_elements = []
            for idx in reading_order:
                if 0 <= idx < len(ocr_elements):
                    elem = ocr_elements[idx]
                    text_element = TextElement(
                        text=elem['text'],
                        bbox=BoundingBox(
                            x=elem['bbox'][0],
                            y=elem['bbox'][1],
                            width=elem['bbox'][2],
                            height=elem['bbox'][3]
                        ),
                        confidence=elem.get('confidence', 1.0)
                    )
                    ordered_elements.append(text_element)
            
            return ordered_elements
            
        except Exception as e:
            logger.error(f"Error determining reading order with LLM: {e}")
            # フォールバックとして位置ベースのソート
            return self._fallback_ordering(ocr_elements)
    
    def _image_to_base64(self, image: np.ndarray) -> str:
        """画像をbase64エンコード"""
        # NumPy配列をPIL Imageに変換
        if len(image.shape) == 2:
            # グレースケール
            pil_image = Image.fromarray(image, mode='L')
        else:
            # カラー
            pil_image = Image.fromarray(image, mode='RGB')
        
        # PNGとして保存
        buffer = BytesIO()
        pil_image.save(buffer, format='PNG')
        buffer.seek(0)
        
        # base64エンコード
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    def _build_prompt(self, ocr_elements: List[Dict[str, Any]]) -> str:
        """LLM用のプロンプトを構築"""
        # 要素情報を整形
        elements_info = []
        for i, elem in enumerate(ocr_elements):
            elements_info.append(f"{i}: \"{elem['text']}\" at position ({elem['bbox'][0]}, {elem['bbox'][1]})")
        
        prompt = f"""I have detected the following text elements in this document block image:

{chr(10).join(elements_info)}

Please analyze the visual layout of these text elements in the image and determine their correct reading order. Consider:
1. The typical reading flow (left-to-right, top-to-bottom for English/Japanese)
2. Column layouts (multi-column texts should be read column by column)
3. Headers, footers, and side notes
4. Table structures (read row by row)
5. Any visual cues like indentation, bullets, or numbering

Return ONLY a JSON array of indices representing the correct reading order. For example: [0, 2, 1, 3, 4]

Do not include any explanation, just the JSON array."""
        
        return prompt
    
    def _parse_llm_response(self, response: str, ocr_elements: List[Dict[str, Any]]) -> List[int]:
        """LLMのレスポンスをパース"""
        try:
            # JSONを抽出
            response = response.strip()
            
            # コードブロックを除去
            if "```" in response:
                # ```json ... ``` または ``` ... ``` を探す
                import re
                json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1)
            
            # 配列以外のテキストを除去（配列の前後の説明文など）
            import re
            array_match = re.search(r'\[[\d,\s]+\]', response)
            if array_match:
                response = array_match.group(0)
            
            # JSONパース
            reading_order = json.loads(response.strip())
            
            # 検証
            if isinstance(reading_order, list) and all(isinstance(x, int) for x in reading_order):
                # 範囲チェック
                valid_indices = [idx for idx in reading_order if 0 <= idx < len(ocr_elements)]
                
                # 全要素が含まれているか確認（重複も許可）
                if len(valid_indices) > 0:
                    # 不足している要素を追加
                    included = set(valid_indices)
                    for i in range(len(ocr_elements)):
                        if i not in included:
                            valid_indices.append(i)
                    
                    return valid_indices
            
            logger.warning("Invalid reading order from LLM, using fallback")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response was: {response[:200]}...")
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
        
        # パース失敗時はインデックスの順番を返す
        return list(range(len(ocr_elements)))
    
    def _fallback_ordering(self, ocr_elements: List[Dict[str, Any]]) -> List[TextElement]:
        """フォールバック用の位置ベース順序付け"""
        # Y座標、次にX座標でソート
        sorted_elements = sorted(
            enumerate(ocr_elements),
            key=lambda x: (x[1]['bbox'][1], x[1]['bbox'][0])
        )
        
        ordered_elements = []
        for _, elem in sorted_elements:
            text_element = TextElement(
                text=elem['text'],
                bbox=BoundingBox(
                    x=elem['bbox'][0],
                    y=elem['bbox'][1],
                    width=elem['bbox'][2],
                    height=elem['bbox'][3]
                ),
                confidence=elem.get('confidence', 1.0)
            )
            ordered_elements.append(text_element)
        
        return ordered_elements
    
    def analyze_block_type(self, block_image: np.ndarray, text_content: str) -> str:
        """ブロックのタイプをLLMで分析"""
        # 画像をbase64エンコード
        image_base64 = self._image_to_base64(block_image)
        
        prompt = f"""Analyze this document block image and its text content to determine its type.

Text content: "{text_content[:200]}{'...' if len(text_content) > 200 else ''}"

Possible types:
- title: Main title or document title
- subtitle: Section title or subtitle
- paragraph: Normal text paragraph
- table: Table structure
- figure: Figure or image with caption
- list: Bulleted or numbered list
- header: Page header
- footer: Page footer
- sidebar: Side note or margin content
- caption: Figure/table caption

Return ONLY the type name, nothing else."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=50,
                temperature=0.3
            )
            
            block_type = response.choices[0].message.content.strip().lower()
            
            # 有効なタイプかチェック
            valid_types = ['title', 'subtitle', 'paragraph', 'table', 'figure', 
                          'list', 'header', 'footer', 'sidebar', 'caption']
            
            if block_type in valid_types:
                return block_type
            
        except Exception as e:
            logger.error(f"Error analyzing block type with LLM: {e}")
        
        return 'paragraph'  # デフォルト