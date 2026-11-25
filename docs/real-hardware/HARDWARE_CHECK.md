# 模块 3：SO-101 硬件检查清单

完成 [机械臂标定](ROBOT_CALIBRATION.md) 和 [相机检查](CAMERA_CALIBRATION.md) 后，再执行本清单。它是人工检查流程，不会自动连接设备或发送动作。

## A. 机械与电气

- [ ] 机械臂底座固定，关节螺丝、舵盘和夹爪无松动。
- [ ] 工作区内没有可能被机械臂撞击的电脑、杯子、线缆或其他物体。
- [ ] 使用符合硬件规格的电源和线材；供电、控制板和电机总线连接牢固。
- [ ] 电机链路没有松脱、反接或异常发热；电机 ID / 波特率已按设备要求设置。
- [ ] Leader / Follower 的实体身份、USB 端口和配置 ID 已记录。

## B. 通信与标定

- [ ] 用 <code>lerobot-find-port</code> 确认 Follower 和 Leader 串口，不凭猜测使用 ttyACM 编号。
- [ ] Follower 的本机标定文件存在：<code>calibration/robots/so101_follower.json</code>。
- [ ] 如果使用 Leader，Leader 也有独立标定文件和 ID。
- [ ] 配置中的 <code>robot.port</code>、<code>robot.id</code>、<code>robot.calibration_dir</code> 与实际一致。
- [ ] 在断开电源前检查连接器和线缆；更换电机或拆装后重新核对标定。

## C. 相机与视觉

- [ ] 用 <code>lerobot-find-cameras</code> 确认 front / wrist 设备身份。
- [ ] Front 视野覆盖整个任务区域；wrist 视野能看到夹爪和接触区域。
- [ ] 相机支架稳固，机械臂全范围运动时不会遮挡、碰撞或拉扯相机线。
- [ ] 采集、训练和部署的图像尺寸、FPS、RGB 通道与 feature rename map 一致。
- [ ] 光照、曝光和白平衡不会在不同实验组之间无记录地改变。
- [ ] 如果系统使用三维几何，内参/外参已经单独标定并验证；纯 RGB SmolVLA 不要伪造不需要的几何参数。

## D. 运动范围与安全

- [ ] 已确认实体急停位置，操作者在整个测试过程中能够立即触及。
- [ ] 工作区清空，机械臂底座稳固，夹爪没有夹住物体或线缆。
- [ ] 在实际设备上逐个确认关节方向、零位、可运动范围和夹爪开合方向。
- [ ] 根据这台机械臂的真实可达范围填写 <code>control.joint_limits</code>；仓库 MJCF 参考值不能直接视为真实设备限位。
- [ ] 初次运动使用低速、小步长和空载动作；确认没有反向、突跳、异常噪声或碰撞后，再进行抓取任务。
- [ ] 明确 <code>disable_torque_on_disconnect</code> 的行为；若断开时会卸载力矩，先支撑机械臂并移开负载。
- [ ] 知道软件停止文件 <code>outputs/real/STOP</code> 的位置和使用方法，但不把它当作实体急停替代品。

## E. 软件与实验配置

- [ ] 使用项目锁定的 LeRobot 版本（当前接口基线为 0.5.1）和对应真机依赖。
- [ ] <code>configs/real/so101.yaml</code> 的串口、ID、标定目录、相机和策略 checkpoint 均已核对。
- [ ] checkpoint、processor、训练数据 feature 和六维真机关节 action/state 语义一致。
- [ ] 真机数据采集、训练和评测输出目录可写，磁盘空间足够。
- [ ] 先运行 dry-run / 文件检查，确认输出计划和输入路径正确。
- [ ] 完成无负载、低风险单步测试后，才允许执行完整采集或评测。

## 何时允许设置 hardware_confirmed

只有 A–E 所有适用项目均已人工确认，且实际关节限位已写入配置后，才由设备操作者在本机将 <code>robot.hardware_confirmed</code> 从 <code>false</code> 改为 <code>true</code>。

此标志只是项目运行器的人工确认门槛，不会自动验证急停、供电、安装质量或真实关节限位。任何硬件更换、重新装配、相机移动或标定变更后，都应重新执行相关检查。
