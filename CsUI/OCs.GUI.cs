using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CleanSlate.CsGUI
{
    public class MainForm : Form
    {
        private BackendHost _backend;
        private ApiClient _api;
        private bool _closing;

        private ListView _scanList;
        private Panel _bottomPanel;
        private ProgressPanel _progressPanel;
        private Button _btnScan;
        private Button _btnClean;
        private Button _btnStatus;
        private StatusStrip _statusStrip;
        private ToolStripStatusLabel _statusLabel;

        private bool _isWorking = false;
        private int _displayProgress = 0;
        private int _targetProgress = 0;
        private string _progressContent = StatusPhrases.Initializing();
        private string _pendingEndContent = null;
        private System.Windows.Forms.Timer _progressTimer;

        private readonly List<ScanItem> _scanItems = new List<ScanItem>();

        private readonly object _logLock = new object();
        private StreamWriter _logWriter;
        private string _logFilePath;

        public MainForm()
        {
            Text = "CleanSlate.CsGUI";
            Width = 1000;
            Height = 700;
            StartPosition = FormStartPosition.CenterScreen;

            InitLogFile();
            BuildUi();

            Load += async (s, e) => await BootstrapAsync();
            FormClosing += MainForm_FormClosing;
        }

        private void InitLogFile()
        {
            _logFilePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "CsGUI.log");
            try
            {
                _logWriter = new StreamWriter(_logFilePath, append: true, new UTF8Encoding(false))
                {
                    AutoFlush = true
                };
            }
            catch
            {
                _logWriter = null;
            }
        }

        private void BuildUi()
        {
            _scanList = new ListView
            {
                Dock = DockStyle.Fill,
                View = View.Details,
                FullRowSelect = true,
                CheckBoxes = true,
                GridLines = true
            };
            _scanList.Columns.Add("名称", 220);
            _scanList.Columns.Add("大小(GB)", 100, HorizontalAlignment.Right);
            _scanList.Columns.Add("风险", 70);
            _scanList.Columns.Add("说明", 520);

            _bottomPanel = new Panel { Dock = DockStyle.Bottom, Height = 140 };

            _progressPanel = new ProgressPanel
            {
                Left = 15,
                Top = 15,
                Height = 30,
                Width = _bottomPanel.ClientSize.Width - 30
            };
            _bottomPanel.Resize += (s, e) =>
            {
                _progressPanel.Width = _bottomPanel.ClientSize.Width - 30;
            };

            _btnScan = new Button { Text = "开始扫描", Width = 140, Height = 45, Left = 15, Top = 70 };
            _btnClean = new Button { Text = "一键清理", Width = 140, Height = 45, Left = 165, Top = 70, Enabled = false };
            _btnStatus = new Button { Text = "磁盘状态", Width = 140, Height = 45, Left = 315, Top = 70 };

            _btnScan.Click += async (s, e) => await RunScanAsync();
            _btnClean.Click += async (s, e) => await RunCleanAsync();
            _btnStatus.Click += async (s, e) => await ShowStatusAsync();

            _bottomPanel.Controls.Add(_progressPanel);
            _bottomPanel.Controls.Add(_btnScan);
            _bottomPanel.Controls.Add(_btnClean);
            _bottomPanel.Controls.Add(_btnStatus);

            _statusStrip = new StatusStrip();
            _statusLabel = new ToolStripStatusLabel();
            _statusStrip.Items.Add(_statusLabel);

            Controls.Add(_scanList);
            Controls.Add(_bottomPanel);
            Controls.Add(_statusStrip);

            _progressTimer = new System.Windows.Forms.Timer { Interval = 80 };
            _progressTimer.Tick += ProgressTimer_Tick;
            _progressTimer.Start();

            RefreshProgressText();
            SetUiEnabled(false);
        }

        private void SetUiEnabled(bool on)
        {
            _btnScan.Enabled = on;
            _btnStatus.Enabled = on;
            _btnClean.Enabled = on && _scanItems.Count > 0;
        }

        private void RefreshProgressText()
        {
            string text = _isWorking
                ? $"{_displayProgress}%  {_progressContent}"
                : _progressContent ?? "";

            _progressPanel.Value = _displayProgress;
            _progressPanel.Text = text;
            _progressPanel.Invalidate();
            _statusLabel.Text = text;
        }

        private void BeginWork(int initial, string content)
        {
            _isWorking = true;
            _displayProgress = Math.Max(0, Math.Min(100, initial));
            _targetProgress = _displayProgress;
            _progressContent = content ?? "";
            _pendingEndContent = null;
            RefreshProgressText();
        }

        private void SetWorkProgress(int target, string content)
        {
            _isWorking = true;
            _targetProgress = Math.Max(0, Math.Min(100, target));
            _progressContent = content ?? "";
        }

        private async Task FinishWorkAsync(int target, string finalContent, int timeoutMs = 5000)
        {
            _isWorking = true;
            _targetProgress = Math.Max(0, Math.Min(100, target));
            _pendingEndContent = finalContent ?? "";

            var sw = System.Diagnostics.Stopwatch.StartNew();
            while ((_displayProgress < _targetProgress || _pendingEndContent != null)
                   && sw.ElapsedMilliseconds < timeoutMs)
                await Task.Delay(40);

            if (_pendingEndContent != null)
            {
                _progressContent = _pendingEndContent;
                _pendingEndContent = null;
                RefreshProgressText();
            }
        }

        private void SetIdle(string content)
        {
            _isWorking = false;
            _displayProgress = 0;
            _targetProgress = 0;
            _progressContent = content ?? "";
            _pendingEndContent = null;
            RefreshProgressText();
        }

        private void ProgressTimer_Tick(object sender, EventArgs e)
        {
            if (!_isWorking) return;

            bool changed = false;

            if (_displayProgress < _targetProgress)
            {
                int diff = _targetProgress - _displayProgress;
                int step = Math.Max(1, diff / 3);
                _displayProgress = Math.Min(_targetProgress, _displayProgress + step);
                changed = true;
            }
            else if (_displayProgress > _targetProgress)
            {
                _displayProgress = _targetProgress;
                changed = true;
            }

            if (_displayProgress >= _targetProgress && _pendingEndContent != null)
            {
                _progressContent = _pendingEndContent;
                _pendingEndContent = null;
                changed = true;
            }

            if (changed) RefreshProgressText();
        }

        private async Task BootstrapAsync()
        {
            _api = new ApiClient();

            _backend = new BackendHost(
                backendPath: "py",
                backendArgsPrefix: @"D:\Hex备份\项目\CleanSlate.CsGUI\Backend\Oadmin.py",
                workingDir: @"D:\Hex备份\项目\CleanSlate.CsGUI\Backend",
                pipeConnectTimeoutMs: 30000);

            _backend.LogReceived += (s, e) => AppendLog(e.Level, e.Message);
            _backend.Exited += (s, e) =>
            {
                if (IsDisposed) return;
                try
                {
                    BeginInvoke(new Action(() =>
                    {
                        AppendLog("error", "Backend 进程已退出。");
                        SetIdle(StatusPhrases.BackendExited());
                        SetUiEnabled(false);
                    }));
                }
                catch { }
            };

            AppendLog("info", "正在启动 Backend（将弹出 UAC 提权，请允许）...");
            BeginWork(0, StatusPhrases.BackendStarting());

            try
            {
                await _backend.StartAsync();
            }
            catch (Exception ex)
            {
                AppendLog("error", $"Backend 启动失败：{ex.Message}");
                SetIdle(StatusPhrases.BackendFailed());
                MessageBox.Show(this, ex.Message, "启动失败",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            AppendLog("info",
                $"Backend 握手成功：port={_backend.Port}, version={_backend.Version}");
            SetWorkProgress(80, StatusPhrases.BackendChecking());

            _api.Configure(_backend.Port, _backend.Token);

            bool ready = false;
            for (int i = 0; i < 40; i++)
            {
                if (await _api.HealthAsync()) { ready = true; break; }
                await Task.Delay(250);
            }

            if (!ready)
            {
                AppendLog("error", "Backend /health 健康检查失败。");
                SetIdle("健康检查失败，请查看日志");
                return;
            }

            AppendLog("info", "Backend 已就绪。");
            await FinishWorkAsync(100, StatusPhrases.IdleReady());
            SetIdle(StatusPhrases.IdleReady());
            SetUiEnabled(true);
        }

        private async Task RunScanAsync()
        {
            if (_api == null) return;
            SetUiEnabled(false);
            BeginWork(0, StatusPhrases.ScanSubmitting());
            _scanItems.Clear();
            _scanList.Items.Clear();

            string endContent = StatusPhrases.ScanDone(0, 0);

            try
            {
                string submitJson = await _api.StartScanAsync();
                string taskId;
                using (var doc = JsonDocument.Parse(submitJson))
                    taskId = doc.RootElement.GetProperty("task_id").GetString();

                while (true)
                {
                    await Task.Delay(200);
                    string taskJson = await _api.GetScanTaskAsync(taskId);

                    using var tdoc = JsonDocument.Parse(taskJson);
                    var troot = tdoc.RootElement;

                    string status = troot.GetProperty("status").GetString();
                    int progress = troot.TryGetProperty("progress", out var p)
                                    ? p.GetInt32() : 0;

                    SetWorkProgress(progress, ScanStageText(progress));

                    if (status == "done")
                    {
                        PopulateScanResult(troot.GetProperty("result"));
                        double totalGb = 0.0;
                        foreach (var s in _scanItems)
                            totalGb += s.SizeGb;
                        endContent = StatusPhrases.ScanDone(_scanItems.Count, totalGb);
                        break;
                    }
                    if (status == "error")
                    {
                        string err = troot.GetProperty("error").GetString();
                        AppendLog("error", $"扫描失败：{err}");
                        endContent = StatusPhrases.ScanFailed();
                        break;
                    }
                }

                await FinishWorkAsync(100, endContent);
            }
            catch (Exception ex)
            {
                AppendLog("error", $"扫描异常：{ex.Message}");
                endContent = StatusPhrases.ScanFailed();
            }
            finally
            {
                SetIdle(endContent);
                SetUiEnabled(true);
            }
        }

        private static string ScanStageText(int progress)
        {
            if (progress < 10) return StatusPhrases.ScanPreparing();
            if (progress < 30) return StatusPhrases.ScanDisk();
            if (progress < 60) return StatusPhrases.ScanCounting();
            if (progress < 90) return StatusPhrases.ScanPatching();
            return StatusPhrases.ScanWrapping();
        }

        private void PopulateScanResult(JsonElement result)
        {
            _scanItems.Clear();
            _scanList.Items.Clear();
            if (result.ValueKind != JsonValueKind.Array) return;

            foreach (var item in result.EnumerateArray())
            {
                var s = new ScanItem
                {
                    Id = item.TryGetProperty("id", out var id) ? id.GetString() : "",
                    Name = item.TryGetProperty("name", out var n) ? n.GetString() : "",
                    SizeGb = item.TryGetProperty("size_gb", out var sz) ? sz.GetDouble() : 0,
                    Risk = item.TryGetProperty("risk", out var r) ? r.GetString() : "",
                    Detail = item.TryGetProperty("detail", out var d) ? d.GetString() : "",
                    CanClean = item.TryGetProperty("can_clean", out var cc) && cc.GetBoolean()
                };
                _scanItems.Add(s);

                var lvi = new ListViewItem(new[]
                {
                    s.Name,
                    s.SizeGb.ToString("F2"),
                    RiskLabel(s.Risk),
                    s.Detail
                })
                {
                    Checked = s.CanClean && s.Risk != "high",
                    Tag = s
                };

                _scanList.Items.Add(lvi);
            }

            _btnClean.Enabled = _scanItems.Count > 0;
        }

        private static string RiskLabel(string risk)
        {
            switch (risk)
            {
                case "high": return "高";
                case "mid": return "中";
                case "low": return "低";
                default: return risk ?? "";
            }
        }

        private async Task RunCleanAsync()
        {
            if (_api == null) return;

            var ids = new List<string>();
            bool highRisk = false;

            foreach (ListViewItem lvi in _scanList.Items)
            {
                if (!lvi.Checked) continue;
                var s = (ScanItem)lvi.Tag;
                if (s.Risk == "high") highRisk = true;
                ids.Add(s.Id);
            }

            if (ids.Count == 0)
            {
                MessageBox.Show(this, "请先勾选要清理的项目。", "提示");
                return;
            }

            if (highRisk)
            {
                var ans = MessageBox.Show(this,
                    "包含高风险项，是否继续？", "确认",
                    MessageBoxButtons.YesNo, MessageBoxIcon.Warning);
                if (ans != DialogResult.Yes) return;
            }

            SetUiEnabled(false);
            BeginWork(0, StatusPhrases.CleanWorking(ids.Count));

            string endContent = StatusPhrases.CleanFailed();

            try
            {
                string respJson = await _api.CleanAsync(ids.ToArray(), highRisk);
                AppendLog("info", "清理结果：" + respJson);

                using var doc = JsonDocument.Parse(respJson);
                var root = doc.RootElement;
                int ok = root.TryGetProperty("total_success", out var ss) ? ss.GetInt32() : 0;
                int fail = root.TryGetProperty("total_failed", out var ff) ? ff.GetInt32() : 0;
                double gb = root.TryGetProperty("total_freed_gb", out var gg) ? gg.GetDouble() : 0;

                endContent = StatusPhrases.CleanDone(ok, fail, gb);

                await FinishWorkAsync(100, endContent);

                MessageBox.Show(this,
                    $"清理完成\n成功：{ok}  失败：{fail}\n释放：{gb:F2} GB",
                    "完成");
            }
            catch (Exception ex)
            {
                AppendLog("error", $"清理异常：{ex.Message}");
                endContent = StatusPhrases.CleanFailed();
            }
            finally
            {
                SetIdle(endContent);
                SetUiEnabled(true);
            }
        }

        private async Task ShowStatusAsync()
        {
            if (_api == null) return;
            try
            {
                string json = await _api.GetStatusAsync();
                AppendLog("info", "磁盘状态：" + json);

                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                double total = root.GetProperty("total_gb").GetDouble();
                double used = root.GetProperty("used_gb").GetDouble();
                double free = root.GetProperty("free_gb").GetDouble();
                double pct = root.GetProperty("usage_percent").GetDouble();

                MessageBox.Show(this,
                    $"总：{total:F1} GB\n已用：{used:F1} GB\n剩余：{free:F1} GB\n使用率：{pct:F1}%",
                    "磁盘状态");
            }
            catch (Exception ex)
            {
                AppendLog("error", $"获取磁盘状态失败：{ex.Message}");
            }
        }

        private void AppendLog(string level, string message)
        {
            if (_logWriter == null) return;
            string line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {message}";
            try
            {
                lock (_logLock)
                {
                    _logWriter.WriteLine(line);
                }
            }
            catch { }
        }

        private async void MainForm_FormClosing(object sender, FormClosingEventArgs e)
        {
            if (_closing) return;
            _closing = true;
            e.Cancel = true;

            try
            {
                var shutdownTask = _api != null ? _api.ShutdownAsync() : Task.CompletedTask;
                await Task.WhenAny(shutdownTask, Task.Delay(3000));
            }
            catch { }

            try { _progressTimer?.Stop(); _progressTimer?.Dispose(); } catch { }

            _backend?.Dispose();
            _api?.Dispose();

            try
            {
                lock (_logLock)
                {
                    _logWriter?.Flush();
                    _logWriter?.Dispose();
                    _logWriter = null;
                }
            }
            catch { }

            Close();
        }
    }

    internal class ProgressPanel : Panel
    {
        private int _value;
        private string _text = "";

        public int Value
        {
            get => _value;
            set { _value = Math.Max(0, Math.Min(100, value)); }
        }

        public string Text
        {
            get => _text;
            set { _text = value ?? ""; }
        }

        public ProgressPanel()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint
                   | ControlStyles.UserPaint
                   | ControlStyles.OptimizedDoubleBuffer
                   | ControlStyles.ResizeRedraw, true);
            DoubleBuffered = true;
            BackColor = SystemColors.Control;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(BackColor);

            int w = ClientSize.Width;
            int h = ClientSize.Height;
            if (w <= 2 || h <= 2) return;

            using (var pen = new Pen(SystemColors.ControlDark))
                g.DrawRectangle(pen, 0, 0, w - 1, h - 1);

            int fill = (int)((w - 2) * _value / 100.0);
            if (fill > 0)
            {
                using (var b = new SolidBrush(Color.FromArgb(6, 176, 37)))
                    g.FillRectangle(b, 1, 1, fill, h - 2);
            }

            Color fg = _value >= 50 ? Color.White : Color.Black;

            using (var b = new SolidBrush(fg))
            using (var sf = new StringFormat
            {
                Alignment = StringAlignment.Center,
                LineAlignment = StringAlignment.Center,
                Trimming = StringTrimming.EllipsisCharacter,
                FormatFlags = StringFormatFlags.NoWrap
            })
            {
                g.DrawString(_text, Font, b, new RectangleF(1, 1, w - 2, h - 2), sf);
            }
        }
    }

    public class ScanItem
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public double SizeGb { get; set; }
        public string Risk { get; set; }
        public string Detail { get; set; }
        public bool CanClean { get; set; }
    }
}