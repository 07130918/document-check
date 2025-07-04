"""
読み順序評価スクリプト（アノテーションファイル対応版）
正解の読み順序とPDF抽出結果を比較
"""
import sys
from pathlib import Path
import json
import csv
import numpy as np
from scipy.stats import spearmanr
from typing import List, Dict, Tuple, Optional
import logging
from datetime import datetime
import re

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.pdf_diff_system.app.modules.reading_order.pdf_text_extractor import PDFTextExtractor

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ReadingOrderAnnotation:
    """読み順序アノテーション"""
    def __init__(self, order_id: str, page: int, text: str, note: str = ""):
        self.order_id = order_id
        self.page = page
        self.text = text
        self.note = note
        self.order_number = int(order_id)  # 順序番号


class ReadingOrderEvaluatorWithAnnotation:
    """アノテーションベースの読み順序評価クラス"""
    
    def __init__(self):
        self.pdf_extractor = PDFTextExtractor()
        self.annotations: List[ReadingOrderAnnotation] = []
    
    def load_reading_order_annotations(self, csv_path: Path) -> List[ReadingOrderAnnotation]:
        """読み順序アノテーションをCSVから読み込み"""
        logger.info(f"読み順序アノテーションを読み込み: {csv_path}")
        
        annotations = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get('順序ID') and row.get('テキスト内容'):
                        # ページ番号の処理（"6-7"のような範囲は最初のページを使用）
                        page_str = row['ページ数']
                        if '-' in page_str:
                            page_num = int(page_str.split('-')[0])
                        else:
                            page_num = int(page_str)
                        
                        ann = ReadingOrderAnnotation(
                            order_id=row['順序ID'],
                            page=page_num,
                            text=row['テキスト内容'].strip(),
                            note=row.get('備考', '')
                        )
                        annotations.append(ann)
        except Exception as e:
            logger.error(f"アノテーション読み込みエラー: {e}")
            return []
        
        logger.info(f"{len(annotations)}件のアノテーションを読み込みました")
        return annotations
    
    def extract_pdf_text_blocks(self, pdf_path: Path, page_num: int) -> List[Dict]:
        """PDFから詳細なテキストブロックを抽出"""
        try:
            # PyMuPDFで直接ページを解析
            import fitz
            doc = fitz.open(str(pdf_path))
            
            if page_num < 1 or page_num > len(doc):
                return []
            
            page = doc[page_num - 1]
            blocks = page.get_text("dict")["blocks"]
            
            text_blocks = []
            block_id = 0
            
            for block in blocks:
                if "lines" in block:  # テキストブロック
                    for line in block["lines"]:
                        line_text = ""
                        for span in line["spans"]:
                            line_text += span["text"]
                        
                        if line_text.strip():
                            text_blocks.append({
                                'id': block_id,
                                'text': line_text.strip(),
                                'bbox': line["bbox"],
                                'y': line["bbox"][1],  # Y座標（上からの位置）
                                'x': line["bbox"][0]   # X座標（左からの位置）
                            })
                            block_id += 1
            
            doc.close()
            
            # Y座標でソート（上から下へ）、同じY座標ならX座標でソート
            text_blocks.sort(key=lambda b: (round(b['y'] / 10), b['x']))
            
            return text_blocks
            
        except Exception as e:
            logger.error(f"PDF解析エラー: {e}")
            return []
    
    def normalize_fullwidth_chars(self, text: str) -> str:
        """全角英数字を半角に変換"""
        # 全角数字を半角に変換（０-９ → 0-9）
        text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        
        # 全角英字（大文字）を半角に変換（Ａ-Ｚ → A-Z）
        text = text.translate(str.maketrans(
            'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ',
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        ))
        
        # 全角英字（小文字）を半角に変換（ａ-ｚ → a-z）
        text = text.translate(str.maketrans(
            'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            'abcdefghijklmnopqrstuvwxyz'
        ))
        
        return text

    def match_annotation_to_blocks(self, annotation: ReadingOrderAnnotation, 
                                 text_blocks: List[Dict]) -> Optional[int]:
        """アノテーションテキストとPDFブロックをマッチング"""
        # 全角を半角に正規化
        ann_text = self.normalize_fullwidth_chars(annotation.text).lower().strip()
        
        # 完全一致を探す
        for i, block in enumerate(text_blocks):
            block_text = self.normalize_fullwidth_chars(block['text']).lower().strip()
            if ann_text == block_text:
                return i
        
        # 部分一致を探す（アノテーションがブロックに含まれる）
        for i, block in enumerate(text_blocks):
            block_text = self.normalize_fullwidth_chars(block['text']).lower().strip()
            if ann_text in block_text:
                return i
        
        # 部分一致を探す（ブロックがアノテーションに含まれる）
        for i, block in enumerate(text_blocks):
            block_text = self.normalize_fullwidth_chars(block['text']).lower().strip()
            if block_text in ann_text and len(block_text) > 3:  # 短すぎる一致は除外
                return i
        
        # 特殊文字を除去して再度マッチング
        ann_text_clean = re.sub(r'[^\w\s]', '', ann_text)
        for i, block in enumerate(text_blocks):
            block_text_clean = re.sub(r'[^\w\s]', '', self.normalize_fullwidth_chars(block['text']).lower().strip())
            if ann_text_clean == block_text_clean:
                return i
        
        return None
    
    def calculate_reading_order_metrics(self, 
                                      annotations: List[ReadingOrderAnnotation],
                                      text_blocks: List[Dict],
                                      matched_indices: List[Tuple[int, int]]) -> Dict:
        """読み順序の評価指標を計算"""
        if len(matched_indices) < 2:
            return {
                'spearman_correlation': 0.0,
                'kendall_tau': 0.0,
                'order_preservation_rate': 0.0,
                'local_order_consistency': 0.0,
                'match_rate': len(matched_indices) / len(annotations) if annotations else 0.0
            }
        
        # 順序配列の作成
        annotation_order = [ann_idx for ann_idx, _ in matched_indices]
        block_order = [block_idx for _, block_idx in matched_indices]
        
        # スピアマンの順位相関係数
        spearman_corr, _ = spearmanr(annotation_order, block_order)
        
        # 順序保持率の計算
        preserved_pairs = 0
        total_pairs = 0
        
        for i in range(len(matched_indices)):
            for j in range(i + 1, len(matched_indices)):
                ann_i, block_i = matched_indices[i]
                ann_j, block_j = matched_indices[j]
                
                total_pairs += 1
                # アノテーションの順序とブロックの順序が一致しているか
                if (ann_i < ann_j and block_i < block_j) or \
                   (ann_i > ann_j and block_i > block_j):
                    preserved_pairs += 1
        
        order_preservation_rate = preserved_pairs / total_pairs if total_pairs > 0 else 0.0
        
        # 局所順序一致率（隣接要素）
        correct_adjacent = 0
        total_adjacent = len(matched_indices) - 1
        
        for i in range(total_adjacent):
            ann_i, block_i = matched_indices[i]
            ann_j, block_j = matched_indices[i + 1]
            
            # 隣接するアノテーションが、ブロックでも隣接しているか
            expected_distance = ann_j - ann_i
            actual_distance = block_j - block_i
            
            if abs(actual_distance) <= 2:  # 許容誤差2ブロック
                correct_adjacent += 1
        
        local_order_consistency = correct_adjacent / total_adjacent if total_adjacent > 0 else 0.0
        
        return {
            'spearman_correlation': float(spearman_corr) if not np.isnan(spearman_corr) else 0.0,
            'order_preservation_rate': order_preservation_rate,
            'local_order_consistency': local_order_consistency,
            'match_rate': len(matched_indices) / len(annotations)
        }
    
    def evaluate_page(self, pdf_path: Path, page_num: int, 
                     page_annotations: List[ReadingOrderAnnotation]) -> Dict:
        """特定ページの読み順序を評価"""
        # PDFからテキストブロックを抽出
        text_blocks = self.extract_pdf_text_blocks(pdf_path, page_num)
        
        if not text_blocks:
            return {
                'page': page_num,
                'status': 'no_blocks',
                'message': 'PDFからテキストブロックを抽出できませんでした'
            }
        
        # アノテーションとブロックのマッチング
        matched_indices = []
        unmatched_annotations = []
        
        for i, ann in enumerate(page_annotations):
            block_idx = self.match_annotation_to_blocks(ann, text_blocks)
            if block_idx is not None:
                matched_indices.append((i, block_idx))
            else:
                unmatched_annotations.append(ann)
        
        # 評価指標の計算
        metrics = self.calculate_reading_order_metrics(
            page_annotations, text_blocks, matched_indices
        )
        
        # 総合スコアの計算
        composite_score = (
            0.3 * metrics['spearman_correlation'] +
            0.3 * metrics['order_preservation_rate'] +
            0.2 * metrics['local_order_consistency'] +
            0.2 * metrics['match_rate']
        )
        
        return {
            'page': page_num,
            'status': 'evaluated',
            'metrics': {
                **metrics,
                'composite_score': composite_score
            },
            'counts': {
                'annotations': len(page_annotations),
                'text_blocks': len(text_blocks),
                'matched': len(matched_indices),
                'unmatched': len(unmatched_annotations)
            },
            'evaluation': self._get_evaluation(composite_score),
            'unmatched_annotations': [
                {'text': ann.text, 'order_id': ann.order_id} 
                for ann in unmatched_annotations[:5]  # 最初の5件のみ
            ]
        }
    
    def _get_evaluation(self, score: float) -> str:
        """スコアに基づく評価を返す"""
        if score >= 0.95:
            return "優秀"
        elif score >= 0.85:
            return "良好"
        elif score >= 0.70:
            return "可"
        elif score >= 0.50:
            return "要改善"
        else:
            return "不可"
    
    def generate_report(self, results: Dict) -> str:
        """評価結果レポートを生成"""
        report = []
        report.append("# PDF読み順序評価レポート\n")
        report.append(f"評価日時: {results['evaluation_date']}\n")
        report.append(f"対象PDF: {results['pdf_path']}\n")
        report.append(f"アノテーションファイル: {results['annotation_file']}\n")
        
        # サマリー
        if 'summary' in results:
            report.append("\n## 評価サマリー\n")
            summary = results['summary']
            report.append(f"- **総合評価**: {summary['overall_evaluation']}")
            report.append(f"- **平均総合スコア**: {summary['average_composite_score']:.3f}")
            report.append(f"- **平均マッチ率**: {summary['average_match_rate']:.1%}")
            report.append(f"- **評価ページ数**: {summary['pages_evaluated']}")
        
        # ページ別結果
        report.append("\n## ページ別評価結果\n")
        
        for page_result in results['page_results']:
            if page_result['status'] == 'evaluated':
                report.append(f"\n### ページ {page_result['page']}")
                
                metrics = page_result['metrics']
                counts = page_result['counts']
                
                report.append(f"- **総合スコア**: {metrics['composite_score']:.3f} ({page_result['evaluation']})")
                report.append(f"- **スピアマン相関**: {metrics['spearman_correlation']:.3f}")
                report.append(f"- **順序保持率**: {metrics['order_preservation_rate']:.3f}")
                report.append(f"- **局所一致率**: {metrics['local_order_consistency']:.3f}")
                report.append(f"- **マッチ率**: {metrics['match_rate']:.1%}")
                
                report.append(f"\n**統計**:")
                report.append(f"- アノテーション数: {counts['annotations']}")
                report.append(f"- 抽出ブロック数: {counts['text_blocks']}")
                report.append(f"- マッチ成功: {counts['matched']}")
                report.append(f"- マッチ失敗: {counts['unmatched']}")
                
                if page_result['unmatched_annotations']:
                    report.append(f"\n**マッチ失敗例**:")
                    for unmatched in page_result['unmatched_annotations']:
                        report.append(f"- {unmatched['order_id']}: {unmatched['text']}")
        
        # 改善提案
        report.append("\n## 改善提案\n")
        
        if 'summary' in results:
            avg_score = results['summary']['average_composite_score']
            
            if avg_score < 0.5:
                report.append("### 緊急改善が必要")
                report.append("- PDF抽出アルゴリズムの根本的な見直し")
                report.append("- レイアウト解析の実装")
                report.append("- 文字認識精度の向上")
            elif avg_score < 0.7:
                report.append("### 重要な改善点")
                report.append("- テキストブロックの分割ロジック改善")
                report.append("- 隣接ブロックの結合処理")
                report.append("- 特殊文字・記号の処理改善")
            elif avg_score < 0.85:
                report.append("### 推奨改善点")
                report.append("- 微細な順序調整")
                report.append("- エッジケースの対応")
                report.append("- パフォーマンス最適化")
            else:
                report.append("### 継続的改善")
                report.append("- 現状の品質を維持")
                report.append("- 新しいPDF形式への対応")
                report.append("- 処理速度の向上")
        
        return '\n'.join(report)


def main():
    """メイン実行関数"""
    logger.info("読み順序評価（アノテーションベース）を開始します...")
    
    # ファイルパス設定
    annotation_csv_path = Path("/root/AICE/prj-ms-document-check/apps/pdf_diff_system/data/reading_order_{㈪2023_MSADグループ_パンフレット} - annotation_template.csv")
    pdf_path = Path("/root/AICE/prj-ms-document-check/docs/img/2023.pdf")
    
    # 評価器の初期化
    evaluator = ReadingOrderEvaluatorWithAnnotation()
    
    # アノテーション読み込み
    annotations = evaluator.load_reading_order_annotations(annotation_csv_path)
    if not annotations:
        logger.error("アノテーションを読み込めませんでした")
        return
    
    # ページごとにグループ化
    page_annotations = {}
    for ann in annotations:
        if ann.page not in page_annotations:
            page_annotations[ann.page] = []
        page_annotations[ann.page].append(ann)
    
    # 各ページを評価
    results = {
        'evaluation_date': datetime.now().isoformat(),
        'pdf_path': str(pdf_path),
        'annotation_file': str(annotation_csv_path),
        'page_results': []
    }
    
    all_scores = []
    all_match_rates = []
    
    for page_num in sorted(page_annotations.keys()):
        logger.info(f"\nページ {page_num} の評価中...")
        page_anns = sorted(page_annotations[page_num], key=lambda a: a.order_number)
        
        result = evaluator.evaluate_page(pdf_path, page_num, page_anns)
        results['page_results'].append(result)
        
        if result['status'] == 'evaluated':
            score = result['metrics']['composite_score']
            match_rate = result['metrics']['match_rate']
            all_scores.append(score)
            all_match_rates.append(match_rate)
            logger.info(f"総合スコア: {score:.3f} ({result['evaluation']})")
            logger.info(f"マッチ率: {match_rate:.1%}")
    
    # サマリー計算
    if all_scores:
        results['summary'] = {
            'average_composite_score': float(np.mean(all_scores)),
            'min_composite_score': float(np.min(all_scores)),
            'max_composite_score': float(np.max(all_scores)),
            'average_match_rate': float(np.mean(all_match_rates)),
            'overall_evaluation': evaluator._get_evaluation(np.mean(all_scores)),
            'pages_evaluated': len(all_scores)
        }
    
    # 結果を保存
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    
    # JSON保存
    json_output = output_dir / "reading_order_evaluation_with_annotation.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # レポート生成
    report = evaluator.generate_report(results)
    report_output = output_dir / "reading_order_evaluation_report.md"
    with open(report_output, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"\n評価完了。結果を保存しました:")
    logger.info(f"- JSON: {json_output}")
    logger.info(f"- レポート: {report_output}")
    
    # コンソールにサマリー表示
    if 'summary' in results:
        print("\n" + "="*50)
        print(report.split("## 改善提案")[0])


if __name__ == "__main__":
    main()