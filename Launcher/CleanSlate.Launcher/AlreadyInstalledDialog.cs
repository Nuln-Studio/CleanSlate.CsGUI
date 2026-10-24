using System;
using System.Drawing;
using System.Windows.Forms;
using System.IO;
namespace CleanSlate.Launcher
{
    public enum AlreadyInstalledAction
    {
        Overwrite,
        LaunchExisting,
        Cancel
    }

    public class AlreadyInstalledDialog : Form
    {
        public AlreadyInstalledAction SelectedAction { get; private set; } = AlreadyInstalledAction.Cancel;

        public AlreadyInstalledDialog(string installPath, string version)
        {
            Text = "已检测到安装";
            ClientSize = new Size(440, 230);
            StartPosition = FormStartPosition.CenterParent;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            Font = SystemFonts.MessageBoxFont;
            try
            {
                Icon = IconHelper.Load();
            }
            catch { }
            var lblTitle = new Label
            {
                Text = "已检测到 CleanSlate.CsGUI 的安装记录",
                Font = new Font(SystemFonts.MessageBoxFont, FontStyle.Bold),
                Location = new Point(16, 16),
                Size = new Size(408, 22)
            };
            Controls.Add(lblTitle);

            var lblPath = new Label
            {
                Text = "安装路径：" + installPath,
                Location = new Point(16, 50),
                Size = new Size(408, 18)
            };
            Controls.Add(lblPath);

            var lblVersion = new Label
            {
                Text = "已安装版本：" + version,
                Location = new Point(16, 72),
                Size = new Size(408, 18)
            };
            Controls.Add(lblVersion);

            var lblHint = new Label
            {
                Text = "请选择下一步操作：",
                Location = new Point(16, 108),
                Size = new Size(408, 18)
            };
            Controls.Add(lblHint);

            var btnOverwrite = new Button
            {
                Text = "覆盖安装",
                Location = new Point(16, 140),
                Size = new Size(110, 28)
            };
            btnOverwrite.Click += (s, e) =>
            {
                SelectedAction = AlreadyInstalledAction.Overwrite;
                DialogResult = DialogResult.OK;
                Close();
            };
            Controls.Add(btnOverwrite);

            var btnLaunch = new Button
            {
                Text = "启动已安装版本",
                Location = new Point(136, 140),
                Size = new Size(150, 28)
            };
            btnLaunch.Click += (s, e) =>
            {
                SelectedAction = AlreadyInstalledAction.LaunchExisting;
                DialogResult = DialogResult.OK;
                Close();
            };
            Controls.Add(btnLaunch);

            var btnCancel = new Button
            {
                Text = "取消",
                Location = new Point(296, 140),
                Size = new Size(110, 28)
            };
            btnCancel.Click += (s, e) =>
            {
                SelectedAction = AlreadyInstalledAction.Cancel;
                DialogResult = DialogResult.Cancel;
                Close();
            };
            Controls.Add(btnCancel);
        }
    }
}