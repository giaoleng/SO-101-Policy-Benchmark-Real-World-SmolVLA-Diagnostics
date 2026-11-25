# SO-101 真机 SmolVLA 训练与评测

## 实验状态

Baseline 与 Improved 两组 SmolVLA 均已完成训练和正式真机评测；独立 Recovery 专项测试也已完成。

## 数据组成

| 数据条件 | Baseline | Improved | 数据组成 |
|---|---:|---:|---|
| Clean | 50 | 50 | 标准位置正常示教 |
| Randomized | 0 | 50 | 10 个训练位置轮换，每个位置 5 条 |
| Recovery | 0 | 50 | 其中 20 条包含主动释放、重新抓取并完成放置 |
| Color-varied | 0 | 50 | 红、橙、黄、蓝、紫五色各 10 条；绿色仅用于评测 |
| **合计** | **50** | **200** | Baseline 使用 Clean；Improved 合并四组 |

训练数据、原始视频、Parquet 文件、模型权重和逐回合日志保存在本地或私有存储，不提交到公共 GitHub 仓库。若示教数据存放于私有 Hugging Face Dataset，先登录，再运行：

```bash
hf auth login
python scripts/real/download_study_datasets.py --repo-id YOUR_PRIVATE_DATASET_REPO --condition clean randomized recovery color
```

下载脚本在运行时接收仓库 ID，记录解析后的 commit SHA，并校验每组 50 条、30 FPS、六维 action/state 和双相机特征；不会上传数据。

## Full Fine-Tuning

两组训练使用相同 SmolVLA 基础权重、Seed 1000、10,000 steps、Batch Size 32，每隔 2,000 steps 保存 Checkpoint。训练命令显式设置 `freeze_vision_encoder=false`、`train_expert_only=false`、`train_state_proj=true`，不使用 LoRA。

| 模型 | 数据集 | 实际规模 |
|---|---|---:|
| Baseline | Clean | 50 |
| Improved | Clean + Randomized + Recovery + Color-varied | 200 |

统一训练入口为 `scripts/real/train_study.py`。脚本会校验 Baseline 必须为 50 条、Improved 必须为 200 条，并在训练后保存 `study_manifest.json`，记录训练配置、数据来源、Checkpoint SHA-256 和相机特征映射。

## 正式 ID/OOD 评测

两组模型均已完成以下正式评测。每个模型 40 次 ID、四类 OOD 各 15 次，共 100 次有效计分回合；每个正式场景另有一次不计分预热。

| 场景 | 每模型有效次数 | 测试条件 |
|---|---:|---|
| ID | 40 | 红色 Cube 标准位置、标准光照 |
| OOD: New Positions | 15 | 训练位置之外的新位置 |
| OOD: Reduced Lighting | 15 | 标准位置、低光照 |
| OOD: Different Object | 15 | 绿色 Cube，仅用于评测 |
| OOD: Distractors | 15 | 标准位置，增加干扰物 |

评测入口为 `scripts/real/evaluate_study.py`，正式汇总入口为 `scripts/real/summarize_study.py`。正式评测原始 JSONL 和 CSV 保存在本地，不提交到公共仓库。

正式评测结果：

| 正式评测场景 | 每模型有效回合数 | Baseline 成功率（成功次数） | Improved 成功率（成功次数） |
|---|---:|---:|---:|
| ID | 40 | 75.00%（30/40） | 87.50%（35/40） |
| OOD: New Positions | 15 | 33.33%（5/15） | 80.00%（12/15） |
| OOD: Reduced Lighting | 15 | 40.00%（6/15） | 66.67%（10/15） |
| OOD: Different Object（未见绿色 Cube） | 15 | 46.67%（7/15） | 73.33%（11/15） |
| OOD: Distractors | 15 | 46.67%（7/15） | 73.33%（11/15） |
| **OOD 合计** | **60** | **41.67%（25/60）** | **73.33%（44/60）** |
| **全部场景** | **100** | **55%（55/100）** | **79%（79/100）** |

## Recovery 专项评测

Recovery 专项与正式 ID/OOD 评测分开进行。Baseline 和 Improved 均已完成 10 次有效可控掉落测试，记录掉落后重抓尝试、重抓结果和最终入杯结果。Improved 的重抓成功率从 20% 提高至 60%，完整恢复成功率从 10% 提高至 50%，均提升 40 个百分点。该结果表明在本次专项测试中 Improved 的恢复表现更好；由于每组仅 10 次测试且训练数据量和多样性同时变化，不将提升单独归因于 Recovery 示教。

| Recovery 诊断指标 | Baseline | Improved |
|---|---:|---:|
| 有效可控掉落测试 | 10 次 | 10 次 |
| 尝试重抓次数 | 3 | 8 |
| 成功重抓次数 | 2 | 6 |
| 最终入杯次数 | 1 | 5 |
| Re-grasp Success Rate（重抓成功 / 有效掉落） | 20% | **60%** |
| Recovery Success Rate（重抓后入杯 / 有效掉落） | 10% | **50%** |

查看两组模型的 Recovery 专项协议：

```bash
python scripts/real/study_protocol.py --phase recovery --condition baseline
python scripts/real/study_protocol.py --phase recovery --condition improved
```

专项评测入口为 `scripts/real/evaluate_study.py`。运行时分别指定 Baseline/Improved 的 Checkpoint、训练 Manifest 和独立输出文件；例如：

```bash
python scripts/real/evaluate_study.py \
  --condition baseline --seed 1000 --cell recovery \
  --checkpoint outputs/train/real_baseline_seed1000/checkpoints/010000/pretrained_model \
  --training-manifest outputs/train/real_baseline_seed1000/study_manifest.json \
  --output outputs/real/recovery_baseline.jsonl --dry-run

python scripts/real/evaluate_study.py \
  --condition improved --seed 1000 --cell recovery \
  --checkpoint outputs/train/real_improved_seed1000/checkpoints/010000/pretrained_model \
  --training-manifest outputs/train/real_improved_seed1000/study_manifest.json \
  --output outputs/real/recovery_improved.jsonl --dry-run
```

该协议要求每个有效回合均确认发生可控掉落，并记录 `regrasp_attempted`、`regrasped`、`placed` 和 `success`；其中 `success` 必须表示重抓后最终入杯。

对本地 Recovery JSONL 进行汇总：

```bash
python scripts/real/summarize_recovery.py \
  --baseline outputs/real/recovery_baseline.jsonl \
  --improved outputs/real/recovery_improved.jsonl \
  --csv outputs/real/recovery_summary.csv
```

Recovery 专项统计与正式 ID/OOD 统计分开保存，不混入每模型 100 次正式评测分母。

## 控制与安全

模型推理由 `RealPolicyRunner` 加载对应 Checkpoint 并调用 `policy.select_action(...)`。当前配置为 20 Hz 控制频率、45 秒单回合上限、最多 900 个控制步、推理超时 1 秒。正式部署前仍须在本机完成机械臂标定、关节限位、相机、停止入口和实体急停检查；公共配置默认不启用真机硬件。