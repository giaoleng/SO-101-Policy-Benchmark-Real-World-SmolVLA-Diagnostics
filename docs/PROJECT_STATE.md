# 项目状态

## 仿真实验

SO-101 MuJoCo：红色方块放入蓝色收纳盒。

| 模型 | ID Success Rate | OOD Success Rate |
|---|---:|---:|
| ACT | 89% | 72% |
| Diffusion Policy | 80% | 62% |
| SmolVLA | 95% | 83% |

## SO-101 真机 Cube → Cup

项目展示采用 **Baseline SmolVLA** 与 **Improved SmolVLA** 两组对照，均为 Full Fine-Tuning（不使用 LoRA）。

- Baseline：原始示教数据。
- Improved：将 Clean、Randomized、Recovery、Color-varied 四组各 50 条示教合并，形成 200 条增强训练数据。绿色 Cube 仅用于 OOD 测试。
- 统一训练入口：`scripts/real/train_study.py`，通过 `--condition baseline|improved` 选择数据。
- 数据合并入口：`scripts/real/merge_study_datasets.py`，使用 LeRobot 0.5.1 的正式合并工具处理索引与视频。
- 统一真机评测入口：`scripts/real/evaluate_study.py`。
- 评测协议：每组模型 ID 40 次，OOD 60 次（新位置、低光照、绿色方块、干扰物各 15 次），每个场景另有一次预热。
- 统一汇总：`scripts/real/summarize_study.py`，`--strict` 校验两模型各 100 个正式 Episode。

README 首页保留已有的初始与改进模型摘要结果。但该结果与新的每模型 ID 40 / OOD 60 计数粒度并不完全相容，因此不应声称上述摘要百分比由此新协议的成功次数直接计算得出。

当前版本提供上述两模型训练与评测**工程入口**；历史上独立训练的四个策略模型不自动等价于合并训练的 Improved Checkpoint。正式两模型对照的实际权重与逐回合日志必须另行对应核验。

## 工程入口

- `scripts/real/download_study_datasets.py`：从 `giaobo/so101-smovla` 下载四组示教数据。
- `scripts/real/merge_study_datasets.py`：校验并合并四组 LeRobotDataset。
- `scripts/real/train_study.py`：Baseline / Improved 统一微调入口。
- `scripts/real/study_protocol.py`：示教采集和 ID / OOD 评测计划。
- `scripts/real/evaluate_study.py`：真机评测。
- `scripts/real/summarize_study.py`：回合级与失败模式统计。

设备标定文件、实际训练 Checkpoint 及原始真机日志不随公开源码仓库发布。
