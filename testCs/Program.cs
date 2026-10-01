using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace BackendTest
{
    public class TestResult
    {
        public string Name { get; set; }
        public bool Success { get; set; }
        public string Message { get; set; }
    }

    internal class Program
    {
        static async Task Main(string[] args)
        {
            List<TestResult> testResults = new List<TestResult>();

            var pipeName = $"CleanSlate_{Guid.NewGuid():N}";
            int myPid = Environment.ProcessId;
            Console.WriteLine("CleanSlate.CsGUI Python后端集成测试脚本");
            Console.WriteLine("维护者：Xin_Rail");
            Console.WriteLine("测试项：拉起Python后端API服务，并与C#伪GUI服务对接，除清理外API端口调用功能");
            Console.WriteLine("按下回车以继续测试...");
            Console.ReadKey();
            Console.WriteLine($"[Cp] 生成管道名:{pipeName}, 当前进程PID:{myPid}");


            using var serverPipe = new NamedPipeServerStream(
                pipeName,
                PipeDirection.InOut,
                1,
                PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous);

            var psi = new ProcessStartInfo
            {
                FileName = "py",
                Arguments = "\"D:\\Hex备份\\项目\\CleanSlate.CsGUI\\Backend\\Oadmin.py\" --server --pipe " + pipeName + " --parent-pid " + myPid,
                WorkingDirectory = @"D:\Hex备份\项目\CleanSlate.CsGUI\Backend",
                UseShellExecute = false,
                CreateNoWindow = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            var proc = Process.Start(psi);
            Console.WriteLine($"[Cp] Backend已启动 pid={proc.Id}");

            proc.OutputDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    Console.WriteLine($"[PY-print-OUT] {e.Data}");
            };
            proc.ErrorDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    Console.WriteLine($"[PY-error-ERR] {e.Data}");
            };
            proc.BeginOutputReadLine();
            proc.BeginErrorReadLine();

            Console.WriteLine("[Cp] 等待Python后端连接管道...");
            await serverPipe.WaitForConnectionAsync();
            Console.WriteLine("[Cp] Python管道已连接！等待读取数据握手包...");

            byte[] buf = new byte[4096];
            var sb = new StringBuilder();
            int apiPort = 0;
            string bearerToken = null;
            bool handshakeDone = false;
            var pipeReadTask = Task.Run(async () =>
            {
                while (serverPipe.IsConnected)
                {
                    var read = await serverPipe.ReadAsync(buf, 0, buf.Length);
                    if (read == 0) break;
                    sb.Append(Encoding.UTF8.GetString(buf, 0, read));
                    var text = sb.ToString();
                    if (text.Contains("\n"))
                    {
                        var lines = text.Split('\n', StringSplitOptions.RemoveEmptyEntries);
                        foreach (var line in lines)
                        {
                            Console.WriteLine($"[PIPE-RX] {line}");
                            try
                            {
                                var jsonDoc = JsonDocument.Parse(line);
                                var root = jsonDoc.RootElement;
                                if (!handshakeDone && root.TryGetProperty("status", out var statusVal)
                                    && statusVal.GetString() == "ok")
                                {
                                    apiPort = root.GetProperty("port").GetInt32();
                                    bearerToken = root.GetProperty("token").GetString();
                                    Console.WriteLine($"[Cp] 握手完成 port={apiPort}");
                                    handshakeDone = true;
                                }
                            }
                            catch
                            {
                            }
                        }
                        sb.Clear();
                    }
                }
            });

            while (!handshakeDone)
            {
                await Task.Delay(50);
                if (proc.HasExited)
                {
                    Console.WriteLine("[Cp] Python进程提前退出");
                    break;
                }
            }

            // 握手测试项
            if (handshakeDone && bearerToken != null && apiPort != 0)
            {
                testResults.Add(new TestResult
                {
                    Name = "命名管道握手",
                    Success = true,
                    Message = $"port={apiPort}, token已获取:{bearerToken}"
                });
            }
            else
            {
                testResults.Add(new TestResult
                {
                    Name = "命名管道握手",
                    Success = false,
                    Message = "未收到有效握手数据包"
                });
                Console.WriteLine("[Cp] 未收到有效握手数据包，程序退出");
                Console.ReadKey();
                if (!proc.HasExited) proc.Kill();
                return;
            }

            using var httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(300);
            httpClient.BaseAddress = new Uri($"http://127.0.0.1:{apiPort}/");
            httpClient.DefaultRequestHeaders.Authorization
                = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", bearerToken);

            try
            {
                // 1.检查 /health
                Console.WriteLine("\n[API] 调用 /health");
                var healthResp = await httpClient.GetAsync("health");
                string healthBody = await healthResp.Content.ReadAsStringAsync();
                Console.WriteLine($"statusCode:{(int)healthResp.StatusCode}");
                Console.WriteLine(healthBody);
                testResults.Add(new TestResult
                {
                    Name = "API /health 健康检测",
                    Success = healthResp.IsSuccessStatusCode,
                    Message = $"HttpStatus={(int)healthResp.StatusCode}, Response={healthBody}"
                });

                // 2.扫描 /scan
                Console.WriteLine("\n[API] POST /scan 提交扫描任务");
                var scanSubmitResp = await httpClient.PostAsync("scan", null);
                string submitJson = await scanSubmitResp.Content.ReadAsStringAsync();
                Console.WriteLine(submitJson);
                var submitObj = JsonSerializer.Deserialize<JsonElement>(submitJson);
                string taskId = submitObj.GetProperty("task_id").GetString();

                bool scanOk = false;
                string scanMsg = "";
                while (true)
                {
                    await Task.Delay(800);
                    var taskResp = await httpClient.GetAsync($"scan_task/{taskId}");
                    string taskJson = await taskResp.Content.ReadAsStringAsync();
                    var taskObj = JsonSerializer.Deserialize<JsonElement>(taskJson);
                    string taskStatus = taskObj.GetProperty("status").GetString();
                    int progress = taskObj.GetProperty("progress").GetInt32();
                    Console.WriteLine($"[ScanTask] id={taskId}, status={taskStatus}, progress={progress}%");

                    if (taskStatus == "done")
                    {
                        Console.WriteLine("\n[ScanTask] 扫描完成，结果：");
                        Console.WriteLine(taskObj.GetProperty("result").ToString());
                        scanOk = true;
                        scanMsg = $"task_id={taskId}, status=done, 扫描项数量:{taskObj.GetProperty("result").GetArrayLength()}";
                        break;
                    }
                    if (taskStatus == "error")
                    {
                        scanOk = false;
                        scanMsg = $"task_id={taskId}, error={taskObj.GetProperty("error").GetString()}";
                        Console.WriteLine($"\n[ScanTask] 扫描异常：{taskObj.GetProperty("error").GetString()}");
                        break;
                    }
                }
                testResults.Add(new TestResult
                {
                    Name = "API /scan + /scan_task 异步扫描任务",
                    Success = scanOk,
                    Message = scanMsg
                });

                //3. /status 磁盘状态
                Console.WriteLine("\n[API] 调用 /status");
                var statusResp = await httpClient.GetAsync("status");
                string statusBody = await statusResp.Content.ReadAsStringAsync();
                Console.WriteLine(statusBody);
                testResults.Add(new TestResult
                {
                    Name = "API /status 磁盘信息",
                    Success = statusResp.IsSuccessStatusCode,
                    Message = $"HttpStatus={(int)statusResp.StatusCode}, Response={statusBody}"
                });

                //4. /version 版本接口
                Console.WriteLine("\n[API] 调用 /version");
                var VersionResp = await httpClient.GetAsync("version");
                string verBody = await VersionResp.Content.ReadAsStringAsync();
                Console.WriteLine($"statusCode:{(int)VersionResp.StatusCode}");
                Console.WriteLine(verBody);
                testResults.Add(new TestResult
                {
                    Name = "API /version 版本信息",
                    Success = VersionResp.IsSuccessStatusCode,
                    Message = $"HttpStatus={(int)VersionResp.StatusCode}, Response={verBody}"
                });
            }
            catch (Exception ex)
            {
                testResults.Add(new TestResult
                {
                    Name = "HTTP API整体执行",
                    Success = false,
                    Message = $"发生异常: {ex.Message}"
                });
                Console.WriteLine($"\n[API]异常：{ex.Message}");
            }

            Console.WriteLine("\n[Cp] 测试以完成，请查看结果...");
            int num = 0; 
            foreach (var tr in testResults)
            {
                string mark = tr.Success ? "PASS" : "FAIL";
                num ++;
                Console.WriteLine($"{num}.{mark} - {tr.Name}");
                Console.WriteLine($"     详情：{tr.Message}\n");
            }
            int passCnt = testResults.Count(x => x.Success);
            int failCnt = testResults.Count(x => !x.Success);
            Console.WriteLine($"\n总项数:{testResults.Count}  通过:{passCnt}  失败:{failCnt}");

            Console.WriteLine("\n[Cp] 按任意键结束测试");
            Console.ReadKey();

            if (!proc.HasExited)
            {
                proc.Kill();
                proc.WaitForExit();
            }
        }
    }
}
