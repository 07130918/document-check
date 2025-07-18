"""
OpenAI LLMサービス
"""
import openai
from typing import List, Dict, Any, Optional
import json
import time
from dataclasses import dataclass
import logging

from ..config.settings import settings
from ..models.bbox_models import BBoxTextData, DiffResult

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLMレスポンスのラッパー"""
    content: str
    usage: Dict[str, int]
    model: str

    def parse_json(self) -> Optional[Dict[str, Any]]:
        """JSON形式のレスポンスをパース"""
        try:
            # JSONブロックを抽出
            content = self.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None


class LLMService:
    """OpenAI LLMサービス"""

    def __init__(self):
        """初期化"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set")

        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        self.temperature = settings.OPENAI_TEMPERATURE

    def _call_api(self, messages: List[Dict[str, str]],
                  response_format: Optional[Dict] = None) -> LLMResponse:
        """OpenAI APIを呼び出す"""
        for attempt in range(settings.LLM_RETRY_COUNT):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature
                }

                # response_formatが指定されている場合は追加
                if response_format:
                    kwargs["response_format"] = response_format

                response = self.client.chat.completions.create(**kwargs)

                return LLMResponse(
                    content=response.choices[0].message.content,
                    usage=response.usage.model_dump(),
                    model=response.model
                )

            except Exception as e:
                logger.error(f"LLM API call failed (attempt {attempt + 1}): {e}")
                if attempt < settings.LLM_RETRY_COUNT - 1:
                    time.sleep(settings.LLM_RETRY_DELAY * (attempt + 1))
                else:
                    raise

    def estimate_reading_order(self, bbox_list: List[BBoxTextData],
                             page_layout_description: str = "",
                             is_spread: bool = False,
                             start_number: int = 1) -> List[int]:
        """LLMを使用して読み順序を推定"""
        # BBoxデータを簡潔な形式に変換
        simplified_data = []
        for idx, bbox_data in enumerate(bbox_list):
            simplified_data.append({
                "index": idx,
                "text": bbox_data["text"],
                "x": bbox_data["bbox"][0],
                "y": bbox_data["bbox"][1],
                "width": bbox_data["bbox"][2],
                "height": bbox_data["bbox"][3]
            })

        # 見開きページ用の特別な指示
        spread_instruction = ""
        if is_spread:
            spread_instruction = """
これは見開き2ページの文書です。以下の点に注意してください：
1. 左ページ（偶数ページ）から右ページ（奇数ページ）への自然な読み順序を考慮してください
2. 各ページ内では上から下、左から右の順序を基本とします
3. 見開き全体でのコンテンツの流れを重視してください
4. 左右のページでコンテンツが対応している場合は、その関係性を考慮してください
"""

        prompt = f"""
あなたは文書の読み順序を推定する専門家です。
以下の文書要素の読み順序を推定してください。
各要素には位置情報（x, y座標）とテキストが含まれています。

{spread_instruction}

特に以下の点に注意してください：
- 「団体総合生活補償保険（MS&AD型）」のように、同じ文章内でy座標が若干異なる場合でも、一連の文章として扱ってください
- 日本語の文書では、縦書きと横書きが混在することがあります
- タイトルや見出しは、本文より先に読まれるべきです
- このページ/見開きは全体文書の一部です。前のページまでで{start_number - 1}個の要素が既に読まれています

要素リスト:
{json.dumps(simplified_data, ensure_ascii=False, indent=2)}

{page_layout_description}

人間にとって自然な読み順序でインデックス番号のリストを返してください。
すべての要素を含めてください。
注意：返すのは要素リストのインデックス番号（0から始まる）であり、全体の通し番号ではありません。
レスポンスはJSON形式で、以下の形式にしてください：
{{"reading_order": [インデックス番号のリスト]}}
"""

        messages = [
            {"role": "system", "content": "あなたは文書レイアウト解析の専門家です。"},
            {"role": "user", "content": prompt}
        ]

        response = self._call_api(messages)
        result = response.parse_json()

        if result and "reading_order" in result:
            return result["reading_order"]
        else:
            # フォールバック: 元の順序を返す
            logger.warning("Failed to get reading order from LLM, using original order")
            return list(range(len(bbox_list)))


    def analyze_document_structure(self, bbox_list: List[BBoxTextData]) -> Dict[str, Any]:
        """文書構造を解析"""
        # ページごとにテキストを結合
        page_texts = {}
        for bbox_data in bbox_list:
            page = bbox_data["page"]
            if page not in page_texts:
                page_texts[page] = []
            page_texts[page].append(bbox_data["text"])

        # 各ページのテキストを結合
        full_text = ""
        for page, texts in sorted(page_texts.items()):
            full_text += f"[ページ {page + 1}]\n"
            full_text += " ".join(texts) + "\n\n"

        prompt = f"""
以下の文書の構造を解析してください。

{full_text[:3000]}  # 最初の3000文字のみ

以下の項目を含むJSON形式で回答してください：
{{
    "document_type": "文書タイプ（契約書、仕様書、報告書など）",
    "sections": ["主要なセクション名のリスト"],
    "key_elements": ["重要な要素（金額、日付、条件など）"],
    "summary": "文書の簡潔な要約（100文字以内）"
}}
"""

        messages = [
            {"role": "system", "content": "あなたは文書構造解析の専門家です。"},
            {"role": "user", "content": prompt}
        ]

        response = self._call_api(messages)
        result = response.parse_json()

        return result or {
            "document_type": "不明",
            "sections": [],
            "key_elements": [],
            "summary": "解析に失敗しました"
        }

    def summarize_changes(self, diff_results: List[DiffResult]) -> List[str]:
        """変更内容を要約"""
        if not diff_results:
            return ["変更はありません"]

        # 変更を整理
        changes_text = []
        for diff in diff_results[:20]:  # 最初の20件のみ
            original = diff.original_bbox["text"] if diff.original_bbox else "なし"
            modified = diff.modified_bbox["text"] if diff.modified_bbox else "なし"
            changes_text.append(f"{diff.change_type.value}: '{original}' → '{modified}'")

        prompt = f"""
以下の文書変更を要約してください。
箇条書きで3-5項目にまとめてください。

変更リスト:
{chr(10).join(changes_text)}

レスポンスはJSON形式で、以下の形式にしてください：
{{"key_changes": ["変更点1", "変更点2", ...]}}
"""

        messages = [
            {"role": "system", "content": "あなたは文書変更の要約専門家です。"},
            {"role": "user", "content": prompt}
        ]

        response = self._call_api(messages)
        result = response.parse_json()

        if result and "key_changes" in result:
            return result["key_changes"]
        else:
            return ["変更内容の要約に失敗しました"]
