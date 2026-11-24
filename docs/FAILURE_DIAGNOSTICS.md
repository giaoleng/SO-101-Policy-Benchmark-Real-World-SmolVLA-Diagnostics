# SO-101 真机失败模式与恢复指标

本文定义项目使用的回合级失败标签和 Recovery 专项统计口径。原始示教数据、模型 Checkpoint、逐回合 JSONL 和导出的统计文件保存在本地或私有存储，不提交到公共源码仓库。

## 1. 回合级阶段标签

| 字段 | 含义 | 统计用途 |
|---|---|---|
| `started` | 是否形成有效启动动作 | No-Motion Rate |
| `reached` | 是否到达目标附近 | Reach Rate |
| `grasped` | 是否成功夹起目标 | Grasp Rate |
| `dropped` | 目标是否在搬运中掉落 | Drop Rate；Recovery 分母 |
| `regrasp_attempted` | 掉落后是否尝试重新抓取 | Recovery 行为覆盖 |
| `regrasped` | 是否成功重新抓起目标 | Re-grasp Success |
| `placed` | 是否最终放入杯中 | 完整任务完成阶段 |
| `success` | 是否完成规定的完整任务 | Task Success；Recovery Success |

阶段标签由操作者结合真实执行结果确认。未记录的阶段不能自动视为成功或失败。

## 2. 正式 ID/OOD 评测中的诊断指标

- **No-Motion Rate**：有效计分回合中 `started=false` 的比例。
- **Reach Rate**：有效计分回合中 `reached=true` 的比例。
- **Grasp Rate**：有效计分回合中 `grasped=true` 的比例。
- **Drop Rate**：有效计分回合中 `dropped=true` 的比例。
- **Re-grasp per Drop**：发生掉落的有效回合中 `regrasped=true` 的比例。
- **Recovery per Drop**：发生掉落的有效回合中最终 `success=true` 的比例。

## 3. Recovery 专项测试

Recovery 专项与正式 ID/OOD 评测分开统计。Baseline 和 Improved 各进行 10 次有效可控掉落测试。每个有效回合必须记录 `dropped`、`regrasp_attempted`、`regrasped`、`placed` 和 `success` 五项布尔标签。

统计口径：

- **Re-grasp Attempt Rate** = 尝试重抓次数 / 有效掉落次数。
- **Re-grasp Success per Drop** = 成功重抓次数 / 有效掉落次数。
- **Re-grasp Success per Attempt** = 成功重抓次数 / 尝试重抓次数。
- **Recovery Success per Drop** = 重抓后最终入杯次数 / 有效掉落次数。

Recovery 专项中的 `success` 必须表示“成功重抓并最终放入杯中”，不能只以重新夹起方块作为完整恢复成功。统计程序会检查这项关系，并要求每个模型恰有 10 次有效掉落（除非显式使用 `--allow-partial`）。

## 4. 本地统计命令

正式 ID/OOD 汇总：

```bash
python scripts/real/summarize_study.py outputs/real/eval_*.jsonl \
  --csv outputs/real/study_summary.csv --strict
```

Recovery 专项汇总：

```bash
python scripts/real/summarize_recovery.py \
  --baseline outputs/real/recovery_baseline.jsonl \
  --improved outputs/real/recovery_improved.jsonl \
  --csv outputs/real/recovery_summary.csv
```

统计文件仅写入本地路径；脚本不会上传数据、日志或模型权重。