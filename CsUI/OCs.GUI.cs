using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
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
        private Button _btnSettings;
        private Button _btnPatches;
        private StatusStrip _statusStrip;
        private ToolStripStatusLabel _statusLabel;
        private ToolStripStatusLabel _versionLabel;

        private const string GUI_VERSION = "0.1.2";

        private bool _isWorking = false;
        private int _displayProgress = 0;
        private int _targetProgress = 0;
        private string _progressContent = StatusPhrases.Initializing();
        private string _pendingEndContent = null;
        private System.Windows.Forms.Timer _progressTimer;

        private readonly List<ScanItem> _scanItems = new List<ScanItem>();
        private LogWriter _log;

        public MainForm()
        {
            Text = "CleanSlate.CsGUI 图形化客户端";
            MaximizeBox = false;
            Width = 1000;
            Height = 700;
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Dpi;
            Font = SystemFonts.MessageBoxFont;

            _log = new LogWriter(
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "CsGUI.log"));

            BuildUi();

            Load += async (s, e) => await BootstrapAsync();
            FormClosing += MainForm_FormClosing;
        }

        private void BuildUi()
        {
            _scanList = new ListView
            {
                Dock = DockStyle.Fill,
                View = View.Details,
                FullRowSelect = true,
                CheckBoxes = true,
                GridLines = false,
                BorderStyle = BorderStyle.None
            };
            _scanList.Columns.Add("名称", 220);
            _scanList.Columns.Add("大小(GB)", 100, HorizontalAlignment.Right);
            _scanList.Columns.Add("风险", 70);
            _scanList.Columns.Add("说明", 520);

            _bottomPanel = new Panel
            {
                Dock = DockStyle.Bottom,
                Height = 140,
                Padding = new Padding(15, 12, 15, 12)
            };

            _progressPanel = new ProgressPanel
            {
                Height = 28,
                Left = 15,
                Top = 15,
                Width = _bottomPanel.ClientSize.Width - 30,
                Font = SystemFonts.MessageBoxFont
            };

            int btnTop = 60;
            int btnW = 130;
            int btnH = 42;
            int gap = 8;

            _btnScan = new Button { Text = "开始扫描", Width = btnW, Height = btnH, Left = 15, Top = btnTop };
            _btnClean = new Button { Text = "一键清理", Width = btnW, Height = btnH, Left = 15 + (btnW + gap) * 1, Top = btnTop, Enabled = false };
            _btnStatus = new Button { Text = "磁盘状态", Width = btnW, Height = btnH, Left = 15 + (btnW + gap) * 2, Top = btnTop };

            _btnSettings = new Button
            {
                Text = "设置",
                Width = btnW,
                Height = btnH,
                Top = btnTop,
                FlatStyle = FlatStyle.System,
                Anchor = AnchorStyles.Top | AnchorStyles.Right
            };

            _btnPatches = new Button
            {
                Text = "补丁管理",
                Width = btnW,
                Height = btnH,
                Top = btnTop,
                Visible = false,
                FlatStyle = FlatStyle.System,
                Anchor = AnchorStyles.Top | AnchorStyles.Right
            };

            _bottomPanel.Resize += (s, e) =>
            {
                _progressPanel.Width = _bottomPanel.ClientSize.Width - 30;
                _btnSettings.Left = _bottomPanel.ClientSize.Width - _btnSettings.Width - 15;
                _btnPatches.Left = _btnSettings.Left - _btnPatches.Width - gap;
            };

            _btnScan.Click += async (s, e) => await RunScanAsync();
            _btnClean.Click += async (s, e) => await RunCleanAsync();
            _btnStatus.Click += async (s, e) => await ShowStatusAsync();
            _btnSettings.Click += async (s, e) => await OpenSettingsAsync();
            _btnPatches.Click += async (s, e) => await OpenPatchesAsync();

            _bottomPanel.Controls.Add(_progressPanel);
            _bottomPanel.Controls.Add(_btnScan);
            _bottomPanel.Controls.Add(_btnClean);
            _bottomPanel.Controls.Add(_btnStatus);
            _bottomPanel.Controls.Add(_btnSettings);
            _bottomPanel.Controls.Add(_btnPatches);

            _statusStrip = new StatusStrip();
            _statusLabel = new ToolStripStatusLabel
            {
                Spring = true,
                TextAlign = ContentAlignment.MiddleLeft
            };
            _versionLabel = new ToolStripStatusLabel
            {
                TextAlign = ContentAlignment.MiddleRight
            };
            _statusStrip.Items.Add(_statusLabel);
            _statusStrip.Items.Add(_versionLabel);
            _statusStrip.SizingGrip = false;

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
            _btnSettings.Enabled = on;
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

#if DEBUG
            string devDir = @"D:\Hex备份\项目\CleanSlate.CsGUI\Backend";
            string devScript = Path.Combine(devDir, "Oadmin.py");

            _log.Write("info", $"[DEBUG] 使用开发模式启动 Backend：py {devScript}");

            _backend = new BackendHost(
                backendPath: "py",
                backendArgsPrefix: devScript,
                workingDir: devDir,
                pipeConnectTimeoutMs: 30000);
#else
            string baseDir = AppContext.BaseDirectory;
            string backendDir = Path.Combine(baseDir, "Backend");
            string backendExe = Path.Combine(backendDir, "Backend.exe");

            if (File.Exists(backendExe))
            {
                _log.Write("info", $"[RELEASE] 使用发布模式启动 Backend：{backendExe}");
                _backend = new BackendHost(
                    backendPath: backendExe,
                    backendArgsPrefix: "",
                    workingDir: backendDir,
                    pipeConnectTimeoutMs: 30000);
            }
            else
            {
                _log.Write("error", $"找不到 Backend.exe：{backendExe}");
                MessageBox.Show(this,
                    $"找不到后端程序：\n{backendExe}\n\n请确认 Backend 文件夹已正确安装。",
                    "启动失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
                SetIdle(StatusPhrases.BackendFailed());
                return;
            }
#endif

            _backend.LogReceived += (s, e) => _log.Write(e.Level, e.Message);
            _backend.Exited += (s, e) =>
            {
                if (IsDisposed) return;
                try
                {
                    BeginInvoke(new Action(() =>
                    {
                        _log.Write("error", "Backend 进程已退出。");
                        SetIdle(StatusPhrases.BackendExited());
                        SetUiEnabled(false);
                    }));
                }
                catch { }
            };

            _log.Write("info", "正在启动 Backend（将弹出 UAC 提权，请允许）...");
            BeginWork(0, StatusPhrases.BackendStarting());

            try
            {
                await _backend.StartAsync();
            }
            catch (Exception ex)
            {
                _log.Write("error", $"Backend 启动失败：{ex.Message}");
                SetIdle(StatusPhrases.BackendFailed());
                MessageBox.Show(this, ex.Message, "启动失败",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            _log.Write("info",
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
                _log.Write("error", "Backend /health 健康检查失败。");
                SetIdle("健康检查失败，请查看日志");
                return;
            }

            _log.Write("info", "Backend 已就绪。");

            try
            {
                string patchJson = await _api.GetPatchesAsync();
                using var pdoc = JsonDocument.Parse(patchJson);
                if (pdoc.RootElement.TryGetProperty("enable_patch", out var ep)
                    && ep.GetBoolean())
                {
                    _btnPatches.Visible = true;
                }
            }
            catch (Exception ex)
            {
                _log.Write("warn", $"查询补丁状态失败：{ex.Message}");
            }

            _versionLabel.Text = $"GUI版本: v{GUI_VERSION} | 内核版本: {_backend.Version}";

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
                        _log.Write("error", $"扫描失败：{err}");
                        endContent = StatusPhrases.ScanFailed();
                        break;
                    }
                }

                await FinishWorkAsync(100, endContent);
            }
            catch (Exception ex)
            {
                _log.Write("error", $"扫描异常：{ex.Message}");
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
                _log.Write("info", "清理结果：" + respJson);

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
                _log.Write("error", $"清理异常：{ex.Message}");
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
                _log.Write("info", "磁盘状态：" + json);

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
                _log.Write("error", $"获取磁盘状态失败：{ex.Message}");
            }
        }

        private async Task OpenSettingsAsync()
        {
            if (_api == null) return;

            using var dlg = new SettingsForm(_api);
            var result = dlg.ShowDialog(this);

            if (result == DialogResult.OK)
            {
                _log.Write("info", "用户在设置中选择了退出以重启。");
                Close();
            }
        }

        private async Task OpenPatchesAsync()
        {
            if (_api == null) return;

            using var dlg = new PatchesForm(_api);
            dlg.ShowDialog(this);
            await Task.CompletedTask;
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
            _log?.Dispose();

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

            var rect = new Rectangle(0, 0, w - 1, h - 1);

            using (var bg = new SolidBrush(SystemColors.Window))
                g.FillRectangle(bg, rect);
            using (var border = new Pen(SystemColors.ActiveBorder))
                g.DrawRectangle(border, rect);

            int fill = (int)((w - 2) * _value / 100.0);
            if (fill > 0)
            {
                var fillRect = new Rectangle(1, 1, fill, h - 2);
                using (var b = new SolidBrush(Color.FromArgb(6, 176, 37)))
                    g.FillRectangle(b, fillRect);
            }

            Color fg = _value >= 50 ? Color.White : SystemColors.ControlText;

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