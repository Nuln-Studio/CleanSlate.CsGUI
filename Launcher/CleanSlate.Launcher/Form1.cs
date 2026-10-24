using System;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CleanSlate.Launcher
{
    public partial class Form1 : Form
    {
        private const string LauncherVersion = "v0.1.3.beta";  // 别忘了更新！！！！！！！！！！！！！！！！

        private Panel _contentHost;
        private Panel _pageWelcome;
        private Panel _pagePath;
        private Panel _pageInstall;
        private Panel _pageFinish;

        private TextBox _txtDisclaimer;
        private TextBox _txtPath;
        private ProgressBar _progressBar;
        private Label _lblInstallStatus;
        private CheckBox _chkShortcut;
        private CheckBox _chkLaunch;

        public Form1()
        {
            InitializeCustomComponents();
            ShowPage(_pageWelcome);
        }

        private void InitializeCustomComponents()
        {
            Text = "CleanSlate.CsGUI 安装向导";
            ClientSize = new Size(600, 450);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            Font = SystemFonts.MessageBoxFont;

            try
            {
                Icon = IconHelper.Load();
            }
            catch { }
            _contentHost = new Panel { Dock = DockStyle.Fill };
            Controls.Add(_contentHost);

            _pageWelcome = BuildWelcomePage();
            _pagePath = BuildPathPage();
            _pageInstall = BuildInstallPage();
            _pageFinish = BuildFinishPage();

            _contentHost.Controls.Add(_pageWelcome);
            _contentHost.Controls.Add(_pagePath);
            _contentHost.Controls.Add(_pageInstall);
            _contentHost.Controls.Add(_pageFinish);

            foreach (Control c in _contentHost.Controls) c.Visible = false;
        }

        private void ShowPage(Panel page)
        {
            foreach (Control c in _contentHost.Controls) c.Visible = false;
            page.Visible = true;
            page.BringToFront();
        }

        

        private Panel BuildWelcomePage()
        {
            var panel = new Panel { Dock = DockStyle.Fill };
            const int left = 20;
            const int width = 560;

            panel.Controls.Add(new Label
            {
                Text = "欢迎使用 CleanSlate.CsGUI 安装向导",
                Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 12F, FontStyle.Bold),
                Location = new Point(left, 18),
                Size = new Size(width, 26)
            });

            panel.Controls.Add(new Label
            {
                Text = "请先阅读以下免责声明：",
                Location = new Point(left, 54),
                Size = new Size(width, 20)
            });

            _txtDisclaimer = new TextBox
            {
                Location = new Point(left, 80),
                Size = new Size(width, 300),
                Multiline = true,
                ReadOnly = true,
                TabStop = false,
                ScrollBars = ScrollBars.Vertical,
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 9F),
                Text = DisclaimerText
            };
            panel.Controls.Add(_txtDisclaimer);

            var btnInstall = new Button
            {
                Text = "安装",
                Location = new Point(left + width - 200, 400),
                Size = new Size(95, 28)
            };
            btnInstall.Click += (s, e) => OnBeginInstallFlow();
            panel.Controls.Add(btnInstall);

            var btnCancel = new Button
            {
                Text = "取消",
                Location = new Point(left + width - 95, 400),
                Size = new Size(95, 28)
            };
            btnCancel.Click += (s, e) => Environment.Exit(0);
            panel.Controls.Add(btnCancel);


            return panel;
        }

        private Panel BuildPathPage()
        {
            var panel = new Panel { Dock = DockStyle.Fill };
            const int left = 20;
            const int width = 560;

            panel.Controls.Add(new Label
            {
                Text = "选择安装位置",
                Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 12F, FontStyle.Bold),
                Location = new Point(left, 18),
                Size = new Size(width, 26)
            });

            panel.Controls.Add(new Label
            {
                Text = "建议使用默认路径，如需更改请点击“浏览”。",
                Location = new Point(left, 54),
                Size = new Size(width, 20)
            });

            panel.Controls.Add(new Label
            {
                Text = "安装目录：",
                Location = new Point(left, 100),
                Size = new Size(width, 20)
            });

            _txtPath = new TextBox
            {
                Location = new Point(left, 124),
                Size = new Size(width - 100, 24),
                Text = Path.Combine(AppContext.BaseDirectory, "CleanSlate.CsGUI"),
                BorderStyle = BorderStyle.FixedSingle
            };
            panel.Controls.Add(_txtPath);

            var btnBrowse = new Button
            {
                Text = "浏览...",
                Location = new Point(left + width - 95, 123),
                Size = new Size(95, 26)
            };
            btnBrowse.Click += BtnBrowse_Click;
            panel.Controls.Add(btnBrowse);

            panel.Controls.Add(new Label
            {
                Text = "提示：安装目录必须具有写入权限，且不能是 Windows 系统目录。",
                ForeColor = SystemColors.GrayText,
                Location = new Point(left, 160),
                Size = new Size(width, 40)
            });

            var btnBack = new Button
            {
                Text = "上一步",
                Location = new Point(left + width - 300, 400),
                Size = new Size(95, 28)
            };
            btnBack.Click += (s, e) => ShowPage(_pageWelcome);
            panel.Controls.Add(btnBack);

            var btnNext = new Button
            {
                Text = "开始安装",
                Location = new Point(left + width - 200, 400),
                Size = new Size(95, 28)
            };
            btnNext.Click += async (s, e) => await OnConfirmInstallAsync();
            panel.Controls.Add(btnNext);

            var btnCancel = new Button
            {
                Text = "取消",
                Location = new Point(left + width - 95, 400),
                Size = new Size(95, 28)
            };
            btnCancel.Click += (s, e) => Environment.Exit(0);
            panel.Controls.Add(btnCancel);



            return panel;
        }

        private Panel BuildInstallPage()
        {
            var panel = new Panel { Dock = DockStyle.Fill };
            const int left = 20;
            const int width = 560;

            panel.Controls.Add(new Label
            {
                Text = "正在安装",
                Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 12F, FontStyle.Bold),
                Location = new Point(left, 18),
                Size = new Size(width, 26)
            });

            panel.Controls.Add(new Label
            {
                Text = "请不要关闭本窗口，安装完成后会自动跳转。",
                Location = new Point(left, 54),
                Size = new Size(width, 20)
            });

            _progressBar = new ProgressBar
            {
                Location = new Point(left, 220),
                Size = new Size(width, 22),
                Style = ProgressBarStyle.Continuous
            };
            panel.Controls.Add(_progressBar);

            _lblInstallStatus = new Label
            {
                Text = "",
                Location = new Point(left, 252),
                Size = new Size(width, 22)
            };
            panel.Controls.Add(_lblInstallStatus);



            return panel;
        }

        private Panel BuildFinishPage()
        {
            var panel = new Panel { Dock = DockStyle.Fill };
            const int left = 20;
            const int width = 560;

            panel.Controls.Add(new Label
            {
                Text = "安装完成",
                Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 12F, FontStyle.Bold),
                Location = new Point(left, 18),
                Size = new Size(width, 26)
            });

            panel.Controls.Add(new Label
            {
                Text = "请选择附加选项：",
                Location = new Point(left, 54),
                Size = new Size(width, 20)
            });

            _chkShortcut = new CheckBox
            {
                Text = "创建桌面快捷方式",
                Location = new Point(left, 100),
                Size = new Size(400, 24),
                Checked = false
            };
            panel.Controls.Add(_chkShortcut);

            _chkLaunch = new CheckBox
            {
                Text = "立即启动 CleanSlate.CsGUI",
                Location = new Point(left, 130),
                Size = new Size(400, 24),
                Checked = true
            };
            panel.Controls.Add(_chkLaunch);

            var btnFinish = new Button
            {
                Text = "完成",
                Location = new Point(left + width - 95, 400),
                Size = new Size(95, 28)
            };
            btnFinish.Click += async (s, e) => await OnFinishAsync();
            panel.Controls.Add(btnFinish);



            return panel;
        }

        private void OnBeginInstallFlow()
        {
            var existing = InstallerCore.ReadInstallRecord();
            if (existing.HasValue)
            {
                using var dialog = new AlreadyInstalledDialog(
                    existing.Value.InstallPath, existing.Value.Version);
                dialog.ShowDialog(this);

                if (dialog.SelectedAction == AlreadyInstalledAction.Cancel)
                    return;

                if (dialog.SelectedAction == AlreadyInstalledAction.LaunchExisting)
                {
                    string exe = Path.Combine(existing.Value.InstallPath, "CsUI.exe");
                    try
                    {
                        InstallerCore.LaunchApp(exe, existing.Value.InstallPath);
                        Environment.Exit(0);
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show(this,
                            "启动已安装版本失败：" + ex.Message, "错误",
                            MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                    return;
                }
            }

            ShowPage(_pagePath);
        }

        private async Task OnConfirmInstallAsync()
        {
            string installDir = _txtPath.Text.Trim();

            if (!InstallerCore.IsPathSafe(installDir, out string reason))
            {
                MessageBox.Show(this, reason, "提示",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string baseDir = AppContext.BaseDirectory;

            if (InstallerCore.IsRunningFromTemp(baseDir))
            {
                MessageBox.Show(this,
                    "请先将压缩包完整解压到独立文件夹，再运行本程序。\n\n" +
                    "不要直接从压缩包内双击运行，否则安装会失败。",
                    "请先解压", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (!InstallerCore.IsDotNet8Installed())
            {
                TryInstallDotNet(baseDir);
                return;
            }

            ShowPage(_pageInstall);
            UpdateStatus("正在释放程序文件...", 30);

            try
            {
                await Task.Run(() => InstallerCore.ExtractResource("CleanSlate.CsUI.zip", installDir));
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, "释放文件失败：" + ex.Message, "错误",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                ShowPage(_pagePath);
                return;
            }

            UpdateStatus("正在校验文件...", 70);
            await Task.Delay(200);

            string csuiExe = Path.Combine(installDir, "CsUI.exe");
            if (!File.Exists(csuiExe))
            {
                MessageBox.Show(this,
                    "找不到 CsUI.exe。\n\n路径：" + csuiExe + "\n\n请确认安装包完整。",
                    "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                ShowPage(_pagePath);
                return;
            }

            InstallerCore.WriteInstallRecord(installDir, LauncherVersion);

            UpdateStatus("安装完成", 100);
            await Task.Delay(300);

            ShowPage(_pageFinish);
        }

        private async Task OnFinishAsync()
        {
            string installDir = _txtPath.Text.Trim();
            string csuiExe = Path.Combine(installDir, "CsUI.exe");

            if (_chkShortcut.Checked)
            {
                try
                {
                    await Task.Run(() => InstallerCore.CreateDesktopShortcut(csuiExe, installDir));
                }
                catch { }
            }

            if (_chkLaunch.Checked)
            {
                try
                {
                    InstallerCore.LaunchApp(csuiExe, installDir);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(this,
                        "启动 CleanSlate.CsGUI 失败：" + ex.Message, "错误",
                        MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }
                await Task.Delay(400);
            }

            Environment.Exit(0);
        }

        private void BtnBrowse_Click(object sender, EventArgs e)
        {
            using var dialog = new FolderBrowserDialog
            {
                Description = "选择 CleanSlate.CsGUI 的安装位置",
                SelectedPath = _txtPath.Text,
                ShowNewFolderButton = true
            };
            if (dialog.ShowDialog(this) == DialogResult.OK)
                _txtPath.Text = dialog.SelectedPath;
        }

        private void TryInstallDotNet(string baseDir)
        {
            string runtimePath = Path.Combine(baseDir, "dotnet8.exe");
            if (!File.Exists(runtimePath))
            {
                MessageBox.Show(this,
                    "未检测到 .NET 8 桌面运行时，且未找到安装包 dotnet8.exe。\n\n" +
                    "请前往官网下载 .NET 8 桌面运行时，或重新下载完整安装包。",
                    "缺少运行时", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            var ans = MessageBox.Show(this,
                "CleanSlate.CsGUI 需要 .NET 8 桌面运行时。\n\n" +
                "即将启动安装程序，请按提示完成安装后回到本窗口点击“开始安装”继续。",
                "需要安装 .NET 8", MessageBoxButtons.OKCancel, MessageBoxIcon.Information);
            if (ans != DialogResult.OK) return;

            try
            {
                InstallerCore.LaunchDotNetInstaller(runtimePath);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, "启动 .NET 运行时安装程序失败：" + ex.Message,
                    "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            MessageBox.Show(this,
                "请完成 .NET 8 安装后，回到本窗口点击“开始安装”继续。",
                "请完成安装", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        private void UpdateStatus(string text, int progress)
        {
            if (InvokeRequired)
            {
                Invoke(new Action(() => UpdateStatus(text, progress)));
                return;
            }
            if (_lblInstallStatus != null) _lblInstallStatus.Text = text ?? "";
            if (_progressBar != null) _progressBar.Value = Math.Max(0, Math.Min(100, progress));
        }

        private const string DisclaimerText =
@$"【CleanSlate.CsGUI 用户须知与免责声明】

注意:您目前下载的 CleanSlate.CsGUI 版本为 {LauncherVersion} 

本软件依据 GPL-3.0 授权发布，您可以在
遵守该许可证条款的前提下自由使用、修改与分发本软件。完整许可证文
本请参阅项目仓库中的 LICENSE 文件

【使用须知】
  1. 本软件的部分清理功能需要管理员权限（UAC 提权），请在弹窗中
     选择“是”以继续。
  2. 清理过程中请勿强制关闭程序或中断系统电源，以免数据损坏。
  3. 若安全软件提示风险，请将本程序添加至信任列表，或暂时关闭防护
     后再行操作。本软件不含任何广告、捆绑组件或数据上报行为。

【免责声明】
  本软件按“现状”提供，不附带任何明示或默示的担保，包括但不限于对
  适销性、特定用途适用性及非侵权性的担保。在任何情况下，版权持有
  人或贡献者均不对因使用或无法使用本软件而产生的任何直接、间接、
  偶然、特殊或后果性损害承担责任，即使已被告知此类损害的可能性。

  在使用本软件前，请您确认已充分阅读并理解上述条款。点击“安装”
  即表示您已知悉并同意本声明全部内容。";
    }
}