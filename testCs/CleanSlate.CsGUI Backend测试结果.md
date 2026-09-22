CleanSlate.CsGUI Python后端集成测试脚本
维护者：Xin_Rail
测试项：拉起Python后端API服务，并与C#伪GUI服务对接，除清理外API端口调用功能
按下回车以继续测试...
[Cp] 生成管道名:CleanSlate_ed0424ab064c486c932841ebd5f52093, 当前进程PID:6268
[Cp] Backend已启动 pid=7564
[Cp] 等待Python后端连接管道...
[Cp] Python管道已连接！等待读取数据握手包...
[PIPE-RX] {"level": "info", "msg": "Backend初始化开始 正式版v1.0.4"}
[PIPE-RX] {"level": "info", "msg": "扫描完成，应急模式=False"}
[PIPE-RX] {"status": "ok", "port": 10000, "token": "EgQANpenwLYM_ikdEl6VegwXpg79NVFpDFZnjeZER5s", "version": "正式版v1.0.4"}
[Cp] 握手完成 port=10000

[API] 调用 /health
statusCode:200
{"status":"ok"}

[API] POST /scan 提交扫描任务
{"task_id":"528354ef-49a0-405c-acbc-e51c79efb89e"}
[PIPE-RX] {"level": "debug", "msg": " 收集文件..."}
[PIPE-RX] {"level": "debug", "msg": " 分组完成"}
[PIPE-RX] {"level": "debug", "msg": " 计算哈希..."}
[PIPE-RX] {"level": "debug", "msg": " 完成"}
[ScanTask] id=528354ef-49a0-405c-acbc-e51c79efb89e, status=done, progress=100%

[ScanTask] 扫描完成，结果：
[{"size_gb":2.3,"can_clean":true,"detail":"系统临时文件 2.30 GB","risk":"low"},{"size_gb":0.42,"can_clean":true,"detail":"用户临时文件 0.42 GB","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"预读缓存 0.00 GB","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"更新缓存 0.00 GB","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"QQ 残留不存在","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"未检测到微信缓存","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"休眠已关闭","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"重复文件，可释放 0.00 GB（删除后 保留第一个文件）","risk":"medium"},{"size_gb":0.0,"can_clean":true,"detail":"空文件夹 14 个","risk":"low"},{"size_gb":0.09,"can_clean":true,"detail":"浏览器缓存 0.09 GB","risk":"low"},{"size_gb":0.01,"can_clean":false,"detail":"IDE 缓存 0.01 GB","risk":"low"},{"size_gb":0.02,"can_clean":true,"detail":"日志文件 (超30天) 0.02 GB","risk":"low"},{"size_gb":0.3,"can_clean":true,"detail":"安装包缓存 0.30 GB","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"pip缓存 0.00 GB","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"npm缓存不存在","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"yarn缓存不存在","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"Maven仓库不存在","risk":"medium"},{"size_gb":0.0,"can_clean":false,"detail":"Gradle缓存 0.00 GB","risk":"medium"},{"size_gb":0.0,"can_clean":false,"detail":"Conda包缓存不存在","risk":"low"},{"size_gb":0.63,"can_clean":true,"detail":"发现 3 个 JDK 安装，总占用 0.63 GB，建议保留 最新版本","risk":"high"},{"size_gb":0.01,"can_clean":false,"detail":"缩略图缓存 0.01 GB","risk":"low"},{"size_gb":0.01,"can_clean":false,"detail":"错误报告 0.01 GB","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"传递优化 0.00 GB","risk":"low"},{"size_gb":0.0,"can_clean":false,"detail":"回收站 0.00 GB","risk":"low"}]

[API] 调用 /status
{"total_gb":221.11,"used_gb":120.75,"free_gb":100.37,"usage_percent":54.61}

[API] 调用 /version
statusCode:200
{"version_num":"正式版v1.0.4","version_code":1004,"emergency_mode":false}

[Cp] 测试以完成，请查看结果...
1.PASS - 命名管道握手
     详情：port=10000, token已获取:EgQANpenwLYM_ikdEl6VegwXpg79NVFpDFZnjeZER5s

2.PASS - API /health 健康检测
     详情：HttpStatus=200, Response={"status":"ok"}

3.PASS - API /scan + /scan_task 异步扫描任务
     详情：task_id=528354ef-49a0-405c-acbc-e51c79efb89e, status=done, 扫描项数量:24

4.PASS - API /status 磁盘信息
     详情：HttpStatus=200, Response={"total_gb":221.11,"used_gb":120.75,"free_gb":100.37,"usage_percent":54.61}

5.PASS - API /version 版本信息
     详情：HttpStatus=200, Response={"version_num":"正式版v1.0.4","version_code":1004,"emergency_mode":false}


总项数:5  通过:5  失败:0

[Cp] 按任意键结束测试
