using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace CleanSlate.CsGUI
{
    public class BackendHandshake
    {
        public string status { get; set; }
        public int port { get; set; }
        public string token { get; set; }
        public string version { get; set; }
    }

    public class BackendLogEventArgs : EventArgs
    {
        public string Level { get; set; } = "info";
        public string Message { get; set; }
        public string Raw { get; set; }
    }

    public class BackendHost : IDisposable
    {
        public event EventHandler<BackendLogEventArgs> LogReceived;
        public event EventHandler Exited;

        public int Port { get; private set; }
        public string Token { get; private set; }
        public string Version { get; private set; }
        public bool IsRunning => _proc != null && !_proc.HasExited;

        private Process _proc;
        private NamedPipeServerStream _pipe;
        private CancellationTokenSource _cts;

        private readonly string _backendPath;
        private readonly string _backendArgsPrefix;
        private readonly string _workingDir;
        private readonly int _pipeConnectTimeoutMs;

        public BackendHost(
            string backendPath,
            string backendArgsPrefix = null,
            string workingDir = null,
            int pipeConnectTimeoutMs = 30000)
        {
            _backendPath = backendPath;
            _backendArgsPrefix = backendArgsPrefix;
            _workingDir = workingDir;
            _pipeConnectTimeoutMs = pipeConnectTimeoutMs;
        }

        public async Task StartAsync()
        {
            _cts = new CancellationTokenSource();

            string pipeName = "CleanSlate_" + Guid.NewGuid().ToString("N");
            int myPid = Environment.ProcessId;

            _pipe = new NamedPipeServerStream(
                pipeName,
                PipeDirection.InOut,
                1,
                PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous);

            string args = string.IsNullOrEmpty(_backendArgsPrefix)
                ? $"--server --pipe {pipeName} --parent-pid {myPid}"
                : $"\"{_backendArgsPrefix}\" --server --pipe {pipeName} --parent-pid {myPid}";

            var psi = new ProcessStartInfo
            {
                FileName = _backendPath,
                Arguments = args,
                UseShellExecute = true,
                Verb = "runas",
                WindowStyle = ProcessWindowStyle.Hidden
            };
            if (!string.IsNullOrEmpty(_workingDir))
                psi.WorkingDirectory = _workingDir;

            try
            {
                _proc = Process.Start(psi);
            }
            catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
            {
                throw new InvalidOperationException("用户取消了 UAC 提权，Backend 无法启动。", ex);
            }

            if (_proc == null)
                throw new InvalidOperationException("无法启动 Backend 进程。");

            _proc.EnableRaisingEvents = true;

            var exitedTcs = new TaskCompletionSource<bool>();
            _proc.Exited += (s, e) =>
            {
                exitedTcs.TrySetResult(true);
                Exited?.Invoke(this, EventArgs.Empty);
            };

            var connectTask = _pipe.WaitForConnectionAsync(_cts.Token);
            var timeoutTask = Task.Delay(_pipeConnectTimeoutMs, _cts.Token);

            var completed = await Task.WhenAny(connectTask, timeoutTask, exitedTcs.Task);

            if (completed == exitedTcs.Task)
                throw new InvalidOperationException(
                    $"Backend 进程已退出（ExitCode={_proc.ExitCode}），未能建立管道。");

            if (completed == timeoutTask)
                throw new TimeoutException(
                    $"等待 Backend 命名管道连接超时（{_pipeConnectTimeoutMs}ms）。");

            await connectTask;

            var reader = new StreamReader(_pipe, new UTF8Encoding(false));

            BackendHandshake handshake = null;
            using (var handshakeCts = new CancellationTokenSource(_pipeConnectTimeoutMs))
            {
                while (handshake == null)
                {
                    string line;
                    try
                    {
                        line = await reader.ReadLineAsync(handshakeCts.Token);
                    }
                    catch (OperationCanceledException)
                    {
                        if (_proc.HasExited)
                            throw new InvalidOperationException(
                                $"Backend 进程已退出（ExitCode={_proc.ExitCode}），未收到握手。");
                        throw new TimeoutException(
                            $"等待 Backend 握手超时（{_pipeConnectTimeoutMs}ms）。");
                    }

                    if (line == null)
                    {
                        if (_proc.HasExited)
                            throw new InvalidOperationException(
                                $"Backend 进程已退出（ExitCode={_proc.ExitCode}），未收到握手。");
                        throw new InvalidOperationException("命名管道已关闭，未收到握手。");
                    }

                    if (string.IsNullOrWhiteSpace(line)) continue;

                    try
                    {
                        using var doc = JsonDocument.Parse(line);
                        var root = doc.RootElement;
                        if (root.TryGetProperty("status", out var st)
                            && st.GetString() == "ok")
                        {
                            handshake = JsonSerializer.Deserialize<BackendHandshake>(line);
                            break;
                        }
                    }
                    catch (JsonException) { }

                    var evt = new BackendLogEventArgs { Raw = line, Level = "info", Message = line };
                    try
                    {
                        using var doc = JsonDocument.Parse(line);
                        var root = doc.RootElement;
                        if (root.TryGetProperty("level", out var lvl))
                            evt.Level = lvl.GetString() ?? "info";
                        if (root.TryGetProperty("msg", out var msg))
                            evt.Message = msg.GetString() ?? line;
                    }
                    catch { }
                    LogReceived?.Invoke(this, evt);
                }
            }

            if (handshake == null || handshake.status != "ok")
                throw new InvalidOperationException("未收到有效的 Backend 握手数据。");

            Port = handshake.port;
            Token = handshake.token;
            Version = handshake.version;

            _ = Task.Run(() => PumpLogsAsync(reader, _cts.Token));
        }

        private async Task PumpLogsAsync(StreamReader reader, CancellationToken ct)
        {
            try
            {
                while (!ct.IsCancellationRequested)
                {
                    string line = await reader.ReadLineAsync(ct);
                    if (line == null) break;
                    if (string.IsNullOrWhiteSpace(line)) continue;

                    var evt = new BackendLogEventArgs { Raw = line, Level = "info", Message = line };
                    try
                    {
                        using var doc = JsonDocument.Parse(line);
                        var root = doc.RootElement;
                        if (root.TryGetProperty("level", out var lvl))
                            evt.Level = lvl.GetString() ?? "info";
                        if (root.TryGetProperty("msg", out var msg))
                            evt.Message = msg.GetString() ?? line;
                    }
                    catch { }

                    LogReceived?.Invoke(this, evt);
                }
            }
            catch (OperationCanceledException) { }
            catch (IOException) { }
            catch (ObjectDisposedException) { }
            catch (Exception ex)
            {
                LogReceived?.Invoke(this, new BackendLogEventArgs
                {
                    Level = "error",
                    Message = $"日志泵异常：{ex.Message}",
                    Raw = ex.ToString()
                });
            }
        }

        public void Dispose()
        {
            try { _cts?.Cancel(); } catch { }
            try { _pipe?.Dispose(); } catch { }
            try
            {
                if (_proc != null && !_proc.HasExited)
                {
                    _proc.Kill();
                    _proc.WaitForExit(3000);
                }
            }
            catch { }
            try { _proc?.Dispose(); } catch { }
        }
    }
}