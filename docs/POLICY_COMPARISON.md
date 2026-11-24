# SO-101 MuJoCo：ACT / Diffusion Policy / SmolVLA 对比

## 实验状态

ACT、Diffusion Policy 和 SmolVLA 的训练与 MuJoCo 闭环评测均已完成。三种策略在同一 SO-101 仿真任务、相同场景物理参数和统一成功判定下进行比较。

- **任务：** 抓取红色目标方块并放入固定蓝色收纳盒。
- **ID：** 四个可移动方块在训练分布覆盖的默认区域内随机生成。
- **OOD：** 四个可移动方块同时在训练分布之外的区域内随机生成，改变目标与干扰物的整体空间布局。
- **成功判定：** 正确抓取红色目标方块、稳定抬起，并最终放入蓝色收纳盒。

## ID / OOD 空间设置

| 评测条件 | X 采样范围（m） | Y 采样范围（m） | Z 初始高度（m） | 含义 |
|---|---:|---:|---:|---|
| ID | 0.21–0.27 | 0.04–0.16 | 0.815 | 默认训练分布区域 |
| OOD | 0.28–0.34 | 0.04–0.16 | 0.815 | X 方向平移 7 cm，与 ID 区域间隔 1 cm |

上述 OOD 坐标为本项目历史实验实际采用的范围，已确认，不是待验证的候选配置。两个区域在 X 方向不重叠。

环境重置时，`mujoco_env/y_env.py` 会在配置范围内同时随机采样**全部四个可移动方块**：红色目标方块，以及蓝、绿、黄色干扰方块。采样过程还会应用机械臂近似可达范围、收纳盒排除区和物体间距约束。蓝色收纳盒固定在 (0.25, -0.12, 0.80) m。

因此，本项目的 OOD 评测定义为**目标物体与干扰物整体场景布局的空间分布变化（Spatial Layout Generalization）**，而不是仅移动红色目标方块的单变量位置测试。三种策略使用相同的 ID/OOD 采样设置、随机种子 42、每种分布 100 个回合及统一成功判定。

## 实验结果

| 指标 | ACT | Diffusion Policy | SmolVLA |
|---|---:|---:|---:|
| Success Rate | **89%** | 80% | 95% |
| OOD Success Rate | **72%** | 62% | 83% |

以上为本项目确认采用的最终仿真实验结果。其他未列出的时间、失败阶段或推理延迟指标不在此处补写推测值。

## 策略与训练方式

| 策略 | 核心方法 | 初始化方式 |
|---|---|---|
| ACT | Transformer + Action Chunking | 随机初始化 |
| Diffusion Policy | 条件扩散去噪生成动作序列 | 随机初始化 |
| SmolVLA | 视觉-语言-动作策略 | 基于预训练权重微调 |

三种策略使用统一的任务定义、数据集与闭环评测环境。SmolVLA 使用预训练权重微调，ACT 和 Diffusion Policy 从头训练；比较结果时应保留这一训练初始化差异，不将性能差异简单归因于网络架构本身。

## 统一训练入口

```bash
# ACT
python scripts/train/train_act.py

# Diffusion Policy
bash scripts/train/train_diffusion.sh

# SmolVLA
bash scripts/train/finetune_smolvla.sh
```

训练数据、Checkpoint 与完整运行日志按本地或私有实验环境管理，不提交到公共仓库。复现时应使用实际实验采用的数据版本、LeRobot 版本、相机特征映射和训练配置。

## 统一闭环评测

三种策略通过 `scripts/eval/eval_mujoco.py` 接入同一仿真环境和 Episode 调度，逐回合结果由 `scripts/eval/summarize_rollouts.py` 汇总。

```bash
python scripts/eval/eval_mujoco.py --policy act \
  --checkpoint /path/to/act/pretrained_model \
  --dataset-root /path/to/so101_sim \
  --dry-run

python -m unittest discover -s tests -p test_unified_eval.py -v
```

正式评测需按模型选择对应 checkpoint、动作语义、图像特征键和数据集路径。示例中的路径为本地占位符，模型权重和实验数据不包含在公共仓库中。

## 结果解释边界

仿真任务为红色方块放入蓝色收纳盒；真机任务为 Cube → Cup。两者任务对象、相机成像、接触条件和控制链路不同，因此本表只用于仿真策略比较，不作为真机成功率或 Sim-to-Real 同任务性能的替代指标。