# 项目状态

## 仿真实验

SO-101 MuJoCo：抓取红色目标方块并放入固定蓝色收纳盒。ACT、Diffusion Policy 和 SmolVLA 的训练与统一闭环评测均已完成。

| 模型 | ID Success Rate | OOD Success Rate |
|---|---:|---:|
| ACT | 89% | 72% |
| Diffusion Policy | 80% | 62% |
| SmolVLA | 95% | 83% |

ID 采样范围为 X=0.21–0.27 m、Y=0.04–0.16 m；历史 OOD 实验实际采用 X=0.28–0.34 m、Y=0.04–0.16 m。环境每次重置时同时随机生成红色目标方块和蓝、绿、黄色干扰方块，因此 OOD 衡量的是整体场景物体布局的空间泛化，而非仅改变目标方块位置。

## SO-101 真机 Cube → Cup

Baseline 与 Improved 两组 SmolVLA 均已完成 Full Fine-Tuning、正式 ID/OOD 评测和 Recovery 专项测试。

| 数据条件 | Baseline | Improved |
|---|---:|---:|
| Clean | 50 | 50 |
| Randomized | 0 | 50 |
| Recovery | 0 | 50 |
| Color-varied | 0 | 50 |
| **合计** | **50** | **200** |

- **Baseline**：使用 Clean 组 50 条正常示教。
- **Improved**：合并 Clean、Randomized、Recovery、Color-varied 四组，每组 50 条，共 200 条示教。
- **训练配置**：同一 SmolVLA 基础权重、Full Fine-Tuning、不使用 LoRA、Seed 1000、10,000 steps、Batch Size 32。
- **正式评测**：每个模型 40 次 ID + 4 类 OOD 各 15 次，共 100 次有效计分回合；两模型均已完成。
- **Recovery 专项**：Baseline 与 Improved 各完成 10 次有效可控掉落测试；重抓成功率分别为 20%（2/10）和 60%（6/10），完整恢复成功率分别为 10%（1/10）和 50%（5/10）。该专项独立于正式 ID/OOD 评测。
- **数据与产物**：训练示教、模型 Checkpoint、逐回合 JSONL 和统计 CSV 保存在本地或私有存储，不随公共源码仓库发布。

## 真机实验结果

| 正式评测场景 | 每模型有效回合数 | Baseline 成功率（成功次数） | Improved 成功率（成功次数） |
|---|---:|---:|---:|
| ID | 40 | 75.00%（30/40） | 87.50%（35/40） |
| OOD: New Positions | 15 | 33.33%（5/15） | 80.00%（12/15） |
| OOD: Reduced Lighting | 15 | 40.00%（6/15） | 66.67%（10/15） |
| OOD: Different Object（未见绿色 Cube） | 15 | 46.67%（7/15） | 73.33%（11/15） |
| OOD: Distractors | 15 | 46.67%（7/15） | 73.33%（11/15） |
| **OOD 合计** | **60** | **41.67%（25/60）** | **73.33%（44/60）** |
| **全部场景** | **100** | **55%（55/100）** | **79%（79/100）** |

| Recovery 诊断指标 | Baseline | Improved |
|---|---:|---:|
| 有效可控掉落测试 | 10 次 | 10 次 |
| 尝试重抓次数 | 3 | 8 |
| 成功重抓次数 | 2 | 6 |
| 最终入杯次数 | 1 | 5 |
| Re-grasp Success Rate（重抓成功 / 有效掉落） | 20% | **60%** |
| Recovery Success Rate（重抓后入杯 / 有效掉落） | 10% | **50%** |

## 工程入口

- `scripts/real/download_study_datasets.py`：从运行时指定的私有/授权 Dataset 仓库下载四组示教数据；不硬编码数据集 ID。
- `scripts/real/merge_study_datasets.py`：校验并合并四组 LeRobotDataset。
- `scripts/real/train_study.py`：Baseline / Improved 统一全参数微调入口，并校验 50 / 200 条训练集规模。
- `scripts/real/study_protocol.py`：示教采集、正式 ID/OOD 和 Recovery 专项协议。
- `scripts/real/evaluate_study.py`：正式真机评测与独立 Recovery 专项评测。
- `scripts/real/summarize_study.py`：正式 ID/OOD 回合级与失败模式统计。
- `scripts/real/summarize_recovery.py`：Recovery 专项十次可控掉落测试统计。

公共仓库仅包含源码、配置、实验协议和统计工具，不包含私有示教数据、模型权重或真机原始日志。