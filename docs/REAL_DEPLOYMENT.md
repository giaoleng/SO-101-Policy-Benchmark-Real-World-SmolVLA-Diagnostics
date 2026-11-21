# SO-101 真机 SmolVLA 训练与评测

## 模型对照

统一使用同一个 SmolVLA 全参数微调入口，区分两组训练数据：

| 模型 | 训练数据 | 目的 |
|---|---|---|
| Baseline | 原始 Cube → Cup 示教 | 基础对照 |
| Improved | Clean + Randomized + Recovery + Color-varied，共 200 条 | 展示多样化及恢复示教数据的影响 |

四组增强示教由 Hugging Face Dataset [`giaobo/so101-smovla`](https://huggingface.co/datasets/giaobo/so101-smovla) 提供，分别位于 `cube-pickup-clean`、`cube-pickup-randomized`、`cube-pickup-recovery`、`cube-pickup-color` 子目录，绿色 Cube 不进入训练集。

## 硬件与安全

正式采集或评测前，需完成 [硬件部署指南](REAL_HARDWARE_SETUP.md) 的校准与安全检查。配置 `configs/real/so101.yaml` 默认将 `robot.hardware_confirmed` 设为 `false`；硬件校准完成后才能在本机启用。软件停止文件不能替代物理急停。

## 数据下载与合并

```bash
python scripts/real/download_study_datasets.py
python scripts/real/merge_study_datasets.py --dry-run
python scripts/real/merge_study_datasets.py \
  --input-root data/real_demonstrations \
  --output data/real_so101_improved \
  --repo-id local/so101_improved
```

LeRobot 0.5.1 的合并工具会处理 Episode 重编号、视频和元数据。源数据需要相同 Schema / FPS。合并脚本拒绝覆盖已有输出目录。

## Full Fine-Tuning

统一训练种子 1000、10,000 steps、batch size 32，每隔 2,000 steps 保存 Checkpoint。训练命令显式设置 `freeze_vision_encoder=false`、`train_expert_only=false`、`train_state_proj=true`，不使用 LoRA。LeRobot 0.5.1 默认预设为 AdamW、Learning Rate `1e-4`、Warmup `1000 steps`，实际生效值请核对 Base Model 配置及训练日志。

```bash
# Baseline，先检查命令
python scripts/real/train_study.py \
  --condition baseline --seed 1000 \
  --dataset-root data/real_so101_baseline \
  --repo-id local/so101_baseline \
  --base-model /path/to/local/smolvla_base \
  --output outputs/train/real_baseline_seed1000 --dry-run

# Improved，先检查命令
python scripts/real/train_study.py \
  --condition improved --seed 1000 \
  --dataset-root data/real_so101_improved \
  --repo-id local/so101_improved \
  --base-model /path/to/local/smolvla_base \
  --output outputs/train/real_improved_seed1000 --dry-run
```

检查后改为 `--execute` 才执行真实训练。训练产物包括 Checkpoint 与用于核验的 `study_manifest.json`。

## 统一真机评测

每个模型 ID 40 次，OOD 四场景分别 15 次，共 100 次正式计分，另有 5 次预热。两模型总计 200 次正式计分加 10 次预热。成功结果由操作者按任务完成条件人工核验；回合失败模式和控制日志由工具记录。

```bash
python scripts/real/study_protocol.py --phase evaluate --cell in_distribution

python scripts/real/evaluate_study.py \
  --condition improved --seed 1000 --cell in_distribution \
  --checkpoint outputs/train/real_improved_seed1000/checkpoints/010000/pretrained_model \
  --training-manifest outputs/train/real_improved_seed1000/study_manifest.json \
  --output outputs/real/eval_improved_s1000_id.jsonl --dry-run

python scripts/real/summarize_study.py outputs/real/eval_*.jsonl \
  --csv outputs/real/study_summary.csv --strict
```

模型推理由 `RealPolicyRunner` 加载真实 Checkpoint，调用 `policy.select_action(...)`。目前配置的控制频率为 20 Hz，最长回合 45 秒，最多 900 个控制步，推理超时 1 秒。LeRobot 0.5.1 默认预设 `num_steps=10`、`chunk_size=50`、`n_action_steps=50`，实际数值由加载的 Checkpoint 配置决定；评测脚本不覆盖。

## 结果口径

README 首页保留此前的模型摘要成绩，但不能将其认定为两模型新协议下 40 ID / 60 OOD 的精确统计结果。已有四组独立训练和评测也不等价于 Improved 使用 200 条合并数据的训练；实际获得相应 Checkpoint 与评测日志后，才能形成新方案的正式对照结果。
