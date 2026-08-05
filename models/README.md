# 人脸模型目录

正式运行前，将以下 OpenCV Zoo 模型放在本目录，文件名必须保持不变：

- `face_detection_yunet_2023mar.onnx`
- `face_recognition_sface_2021dec.onnx`

官方下载页面：

- [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)

下载后分别执行 PowerShell：

```powershell
Get-FileHash .\models\face_detection_yunet_2023mar.onnx -Algorithm SHA256
Get-FileHash .\models\face_recognition_sface_2021dec.onnx -Algorithm SHA256
```

把得到的哈希写入 `.env` 的 `YUNET_MODEL_SHA256` 和 `SFACE_MODEL_SHA256`。生产模式没有固定校验和会拒绝启动；文件与校验和不一致也会拒绝加载。

模型文件受各自许可证约束，不纳入本仓库。不得使用来源不明或未经校验的模型替换生产文件。
