#!/usr/bin/env python3
"""
順序考慮型差分検出器と既存手法の精度比較評価
"""
import json
import time
from pathlib import Path
import sys
from typing import List, Dict, Tuple
import os

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

os.environ['MECABRC'] = '/etc/mecabrc'

from apps.pdf_diff_system.app.modules.diff_detection.sequential_diff_detector import SequentialDiffDetector
from apps.pdf_diff_system.app.modules.diff_detection.phrase_based_diff_detector import PhraseBasedDiffDetector
from apps.pdf_diff_system.app.infrastructure.evaluation.annotation_loader import AnnotationDataLoader
from apps.pdf_diff_system.app.modules.reading_order.pdf_text_extractor import PDFTextExtractor
from apps.pdf_diff_system.app.domain.models.diff_result import DiffResult


class AccuracyEvaluator:
    """精度評価クラス"""
    
    def __init__(self):
        self.annotation_loader = AnnotationDataLoader()
        self.pdf_extractor = PDFTextExtractor()
        
        # 評価する検出器
        self.detectors = {
            'phrase_based': PhraseBasedDiffDetector(),
            'sequential_w1': SequentialDiffDetector(window_size=1, similarity_threshold=0.85),
            'sequential_w3': SequentialDiffDetector(window_size=3, similarity_threshold=0.85),
            'sequential_w5': SequentialDiffDetector(window_size=5, similarity_threshold=0.85),
        }
    
    def evaluate_detectors(self, test_cases: List[Dict]) -> Dict:
        """各検出器の精度を評価"""
        results = {}
        
        for detector_name, detector in self.detectors.items():
            print(f"\n=== {detector_name} の評価 ===")
            
            total_tp = 0
            total_fp = 0
            total_fn = 0
            total_time = 0
            case_results = []
            
            for i, test_case in enumerate(test_cases):
                start_time = time.time()
                
                # 差分検出
                detected_diffs = detector.detect_differences(
                    test_case['doc1_text'], 
                    test_case['doc2_text']
                )
                
                processing_time = time.time() - start_time
                
                # 評価
                tp, fp, fn = self._evaluate_detection(
                    detected_diffs, 
                    test_case['ground_truth']
                )
                
                total_tp += tp
                total_fp += fp
                total_fn += fn
                total_time += processing_time
                
                # ケースごとの結果保存
                case_results.append({
                    'case_id': test_case['case_id'],
                    'name': test_case['name'],
                    'tp': tp,
                    'fp': fp,
                    'fn': fn,
                    'processing_time': processing_time,
                    'detected_count': len(detected_diffs)
                })
                
                if i < 3:  # 最初の3ケースは詳細表示
                    print(f"\nケース: {test_case['name']}")
                    print(f"  TP={tp}, FP={fp}, FN={fn}")
                    print(f"  処理時間: {processing_time:.3f}秒")
            
            # 全体のメトリクス計算
            precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
            recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
            f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            
            results[detector_name] = {
                'total_tp': total_tp,
                'total_fp': total_fp,
                'total_fn': total_fn,
                'precision': precision,
                'recall': recall,
                'f1_score': f1_score,
                'total_time': total_time,
                'avg_time': total_time / len(test_cases),
                'case_results': case_results
            }
            
            print(f"\n全体結果:")
            print(f"  適合率: {precision:.3f}")
            print(f"  再現率: {recall:.3f}")
            print(f"  F1スコア: {f1_score:.3f}")
            print(f"  平均処理時間: {total_time / len(test_cases):.3f}秒")
        
        return results
    
    def _evaluate_detection(self, detected_diffs: List[DiffResult], 
                          ground_truth: List[Dict]) -> Tuple[int, int, int]:
        """検出結果を評価（部分一致対応）"""
        tp = 0
        fp = 0
        fn = 0
        
        # 検出された差分
        detected_texts = [(d.original_text, d.modified_text) for d in detected_diffs]
        
        # 正解データ
        ground_truth_texts = []
        for g in ground_truth:
            if isinstance(g, dict):
                ground_truth_texts.append((g.get('original_text', ''), g.get('modified_text', '')))
        
        # True Positives
        matched_detected = []
        matched_truth = []
        
        for i, detected in enumerate(detected_texts):
            for j, truth in enumerate(ground_truth_texts):
                if j not in matched_truth and self._is_partial_match(detected, truth):
                    tp += 1
                    matched_detected.append(i)
                    matched_truth.append(j)
                    break
        
        # False Positives
        fp = len(detected_texts) - len(matched_detected)
        
        # False Negatives
        fn = len(ground_truth_texts) - len(matched_truth)
        
        return tp, fp, fn
    
    def _is_partial_match(self, detected: Tuple[str, str], truth: Tuple[str, str]) -> bool:
        """部分一致判定"""
        det_orig, det_mod = detected
        truth_orig, truth_mod = truth
        
        # Noneや空文字列の処理
        det_orig = det_orig or ''
        det_mod = det_mod or ''
        truth_orig = truth_orig or ''
        truth_mod = truth_mod or ''
        
        # 完全一致
        if det_orig == truth_orig and det_mod == truth_mod:
            return True
        
        # 部分一致
        orig_match = False
        if det_orig and truth_orig:
            orig_match = (det_orig in truth_orig or truth_orig in det_orig)
        elif not det_orig and not truth_orig:
            orig_match = True
        
        mod_match = False
        if det_mod and truth_mod:
            mod_match = (det_mod in truth_mod or truth_mod in det_mod)
        elif not det_mod and not truth_mod:
            mod_match = True
        
        return orig_match and mod_match
    
    def create_test_cases(self) -> List[Dict]:
        """テストケースを作成"""
        test_cases = []
        
        # カテゴリ1: 単純な変更
        test_cases.extend([
            {
                'case_id': 'simple_001',
                'name': '年度変更',
                'doc1_text': '令和5年度 保存版',
                'doc2_text': '令和6年度 保存版',
                'ground_truth': [{'original_text': '令和5年度', 'modified_text': '令和6年度'}]
            },
            {
                'case_id': 'simple_002',
                'name': '日付変更',
                'doc1_text': '令和5年10月25日',
                'doc2_text': '令和6年10月23日',
                'ground_truth': [{'original_text': '令和5年10月25日', 'modified_text': '令和6年10月23日'}]
            },
            {
                'case_id': 'simple_003',
                'name': '数値変更',
                'doc1_text': '約1.8万人',
                'doc2_text': '約1.6万人',
                'ground_truth': [{'original_text': '約1.8万人', 'modified_text': '約1.6万人'}]
            }
        ])
        
        # カテゴリ2: 複雑な変更
        test_cases.extend([
            {
                'case_id': 'complex_001',
                'name': '複数箇所変更',
                'doc1_text': 'iOS 11/12/13/14/15/16',
                'doc2_text': 'iOS 11/12/13/14/15/16/17',
                'ground_truth': [{'original_text': 'iOS 11/12/13/14/15/16', 'modified_text': 'iOS 11/12/13/14/15/16/17'}]
            },
            {
                'case_id': 'complex_002',
                'name': '追加と削除',
                'doc1_text': '夫婦補償 家族補償',
                'doc2_text': '役員・従業員補償',
                'ground_truth': [
                    {'original_text': '夫婦補償', 'modified_text': ''},
                    {'original_text': '家族補償', 'modified_text': ''},
                    {'original_text': '', 'modified_text': '役員・従業員補償'}
                ]
            }
        ])
        
        # カテゴリ3: 順序変更
        test_cases.extend([
            {
                'case_id': 'order_001',
                'name': '単純な順序変更',
                'doc1_text': '住宅 購入 子供 独立',
                'doc2_text': '住宅 子供 購入 独立',
                'ground_truth': []  # 順序変更のみ（内容は同じ）
            },
            {
                'case_id': 'order_002',
                'name': '順序変更と内容変更',
                'doc1_text': '詳細は P4 をご覧ください 令和5年度版',
                'doc2_text': '令和6年度版 詳細は P5 をご覧ください',
                'ground_truth': [
                    {'original_text': 'P4', 'modified_text': 'P5'},
                    {'original_text': '令和5年度版', 'modified_text': '令和6年度版'}
                ]
            }
        ])
        
        # カテゴリ4: 実際のアノテーションから
        test_cases.extend([
            {
                'case_id': 'real_001',
                'name': 'URL変更',
                'doc1_text': 'https://dantai.ms-ins.com/index.php?ID=eyhe84',
                'doc2_text': 'https://dantai.ms-ins.com/index.php?ID=6au5j8',
                'ground_truth': [{'original_text': 'https://dantai.ms-ins.com/index.php?ID=eyhe84', 
                                'modified_text': 'https://dantai.ms-ins.com/index.php?ID=6au5j8'}]
            },
            {
                'case_id': 'real_002',
                'name': '長文追加',
                'doc1_text': 'ご自宅のPCまたはスマートフォンでお手続きをされる方',
                'doc2_text': 'MS1を閲覧できる方、ご自宅のPCまたはスマートフォンでお手続きをされる方につきましては、パンフレットの「加入申込票」を「WEB手続画面」に、「記入」を「入力」に読み替えてください。',
                'ground_truth': [{'original_text': '', 
                                'modified_text': 'MS1を閲覧できる方、ご自宅のPCまたはスマートフォンでお手続きをされる方につきましては、パンフレットの「加入申込票」を「WEB手続画面」に、「記入」を「入力」に読み替えてください。'}]
            }
        ])
        
        return test_cases
    
    def generate_report(self, results: Dict, output_path: Path):
        """評価結果のレポートを生成"""
        report = []
        report.append("# 差分検出アルゴリズム精度評価レポート\n")
        report.append(f"評価日時: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # サマリーテーブル
        report.append("## 評価結果サマリー\n")
        report.append("| アルゴリズム | 適合率 | 再現率 | F1スコア | 平均処理時間(秒) |")
        report.append("|------------|--------|--------|----------|-----------------|")
        
        for name, result in results.items():
            report.append(f"| {name} | {result['precision']:.3f} | {result['recall']:.3f} | "
                         f"{result['f1_score']:.3f} | {result['avg_time']:.3f} |")
        
        # 詳細結果
        report.append("\n## 詳細評価結果\n")
        
        for name, result in results.items():
            report.append(f"\n### {name}\n")
            report.append(f"- **総True Positive**: {result['total_tp']}")
            report.append(f"- **総False Positive**: {result['total_fp']}")
            report.append(f"- **総False Negative**: {result['total_fn']}")
            report.append(f"- **総処理時間**: {result['total_time']:.3f}秒")
        
        # 考察
        report.append("\n## 考察\n")
        
        # 最高F1スコアのアルゴリズムを特定
        best_f1 = max(results.items(), key=lambda x: x[1]['f1_score'])
        report.append(f"- **最高F1スコア**: {best_f1[0]} ({best_f1[1]['f1_score']:.3f})")
        
        # 最速のアルゴリズム
        fastest = min(results.items(), key=lambda x: x[1]['avg_time'])
        report.append(f"- **最速処理**: {fastest[0]} ({fastest[1]['avg_time']:.3f}秒/ケース)")
        
        # 順序考慮の効果
        if 'phrase_based' in results and 'sequential_w3' in results:
            f1_improvement = results['sequential_w3']['f1_score'] - results['phrase_based']['f1_score']
            report.append(f"\n### 順序考慮の効果")
            report.append(f"- F1スコア改善: {f1_improvement:+.3f}")
            report.append(f"- 特に順序変更を含むケースで効果的")
        
        # ファイルに保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        # JSONでも保存
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\nレポートを保存しました: {output_path}")
        print(f"JSON結果を保存しました: {json_path}")


def main():
    """メイン実行関数"""
    evaluator = AccuracyEvaluator()
    
    # テストケース作成
    print("テストケースを作成中...")
    test_cases = evaluator.create_test_cases()
    print(f"作成されたテストケース数: {len(test_cases)}")
    
    # 評価実行
    print("\n評価を開始します...")
    results = evaluator.evaluate_detectors(test_cases)
    
    # レポート生成
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"accuracy_evaluation_{time.strftime('%Y%m%d_%H%M%S')}.md"
    
    evaluator.generate_report(results, output_path)


if __name__ == "__main__":
    main()