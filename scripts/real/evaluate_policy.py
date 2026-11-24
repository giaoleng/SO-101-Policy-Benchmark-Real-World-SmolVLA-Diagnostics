#!/usr/bin/env python3
"""人工复位与判定的SO-101多Episode评测，输出兼容汇总器的JSONL。"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.real.deploy_policy import metadata, parser, prepare
from scripts.real.runtime import RealPolicyRunner, local_path
from scripts.real.task_conditioning import TaskConditioner
from scripts.eval.act_rollout import JsonlRecorder


def read_outcome(input_fn=input, *, require_recovery=False):
    """操作者标注闭环结果；Recovery 模式强制记录完整掉落、重抓与入杯链路。"""
    flags = {
        'success', 'correct_target', 'started', 'reached', 'grasped', 'placed',
        'released', 'dropped', 'regrasp_attempted', 'regrasped',
    }
    failure_modes = {'none', 'reach', 'no_motion', 'recovery', 'grasp', 'placement', 'timeout', 'other'}
    while True:
        prompt = (
            'Recovery 专项请完整标注 dropped/regrasp_attempted/regrasped/placed/success；'
            'success 必须表示重抓后最终入杯。输入结果 JSON： '
            if require_recovery else
            '输入结果JSON，如 {"success":false,"started":true,"reached":false,'
            '"failure_mode":"reach"}（可记录dropped/regrasped等阶段）： '
        )
        raw = input_fn(prompt)
        try:
            result = json.loads(raw)
            if not isinstance(result, dict) or set(result) - (flags | {'failure_mode'}):
                raise ValueError('结果包含未知字段')
            if type(result.get('success')) is not bool:
                raise ValueError('success必须是布尔值')
            if any(type(value) is not bool for key, value in result.items() if key in flags):
                raise ValueError('阶段结果必须是布尔值')
            if 'failure_mode' in result and result['failure_mode'] not in failure_modes:
                raise ValueError(f'failure_mode必须属于{sorted(failure_modes)}')
            if result['success'] and any(result.get(k) is False for k in ('grasped', 'placed', 'released', 'correct_target')):
                raise ValueError('success=true不能同时存在明确失败的抓取/入杯/释放阶段')
            if all(k in result for k in ('grasped', 'placed', 'released')):
                actual = all(result[k] for k in ('grasped', 'placed', 'released'))
                if result['success'] != actual:
                    raise ValueError('success应与grasped、placed、released三项一致')
            if all(k in result for k in ('correct_target', 'grasped', 'placed')):
                if result['success'] != all(result[k] for k in ('correct_target', 'grasped', 'placed')):
                    raise ValueError('旧格式success应与correct_target/grasped/placed一致')
            if result.get('regrasped') is True and result.get('dropped') is False:
                raise ValueError('没有发生掉落的回合不应标记regrasped=true')
            if result.get('regrasped') is True and result.get('regrasp_attempted') is False:
                raise ValueError('regrasped=true时regrasp_attempted不能为false')
            if require_recovery:
                required = ('dropped', 'regrasp_attempted', 'regrasped', 'placed', 'success')
                missing = [key for key in required if type(result.get(key)) is not bool]
                if missing:
                    raise ValueError(f'Recovery 专项缺少布尔标注：{missing}')
                if result['dropped'] is not True:
                    raise ValueError('Recovery 专项每个有效回合都必须确认发生可控掉落')
                if result['success'] != (result['regrasped'] and result['placed']):
                    raise ValueError('Recovery success 必须等于 regrasped 且 placed')
            if result['success'] and result.get('failure_mode') not in (None, 'none'):
                raise ValueError('success=true时failure_mode只能是none或省略')
            return result
        except (ValueError, TypeError) as exc:
            print(f'结果格式错误：{exc}')


def main(argv=None):
    p = parser(__doc__)
    p.add_argument('--episodes', type=int)
    p.add_argument('--targets', nargs='+', help='按此顺序循环切换目标')
    p.add_argument('--split', help='统计分组名；默认使用--condition或配置中的split')
    p.add_argument('--condition', choices=('baseline', 'position_shift', 'no_motion', 'recovery', 'color_variation'),
                   help='当前实验条件标签（不改变物理环境，仅用于记录和分组）')
    args = p.parse_args(argv)
    cfg, default_target = prepare(args)
    episodes = args.episodes if args.episodes is not None else cfg['evaluation']['episodes']
    if episodes <= 0:
        p.error('--episodes必须为正整数')
    targets = args.targets or [default_target]
    condition = args.condition or cfg['evaluation'].get('condition', 'baseline')
    split = args.split or (condition if args.condition else cfg['evaluation']['split'])
    conditioner = TaskConditioner(cfg['conditioning'])
    for target in targets:
        conditioner.task(target)
    print(json.dumps({'episodes': episodes, 'target_sequence': targets,
                      'split': split, 'condition': condition}, ensure_ascii=False))
    if not args.execute:
        return
    output = local_path(args.output) if args.output else Path(cfg['evaluation']['output'])
    recorder = JsonlRecorder(output, {**metadata(cfg), 'split': split,
                                      'condition': condition, 'outcome_source': 'operator'})
    episode, target, result = 0, targets[0], {}
    try:
        runner = RealPolicyRunner(cfg)
        for episode in range(episodes):
            target = targets[episode % len(targets)]
            result = {}
            input(f'Episode {episode}: {conditioner.task(target)}\n请复位场景、将机械臂置于起始姿态，按Enter连接并执行： ')
            result = runner.run_episode(target)
            if result['reason'] == 'stop_file':
                recorder({**result, 'episode': episode, 'target_id': target, 'condition': condition,
                          'success': False, 'completed': False})
                break
            outcome = read_outcome()
            recorder({**result, **outcome, 'episode': episode, 'target_id': target,
                      'condition': condition, 'split': split, 'completed': True})
    except BaseException as exc:
        recorder({**result, 'episode': episode, 'target_id': target, 'condition': condition, 'success': False,
                  'completed': False, 'reason': 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'error',
                  'error_type': type(exc).__name__})
        raise
    finally:
        recorder.close()


if __name__ == '__main__':
    main()
