using System;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CleanSlate.CsGUI
{
    public class PatchesForm : Form
    {
        private readonly ApiClient _api;

        private Label _lblPatchDir;
        private ListView _list;
        private Button _btnImport;
        private Button _btnDelete;
        private Button _btnRefresh;
        private Button _btnClose;

        public PatchesForm(ApiClient api)
        {
            _api = api;
            Text = "补丁管理";
            ClientSize = new System.Drawing.Size(640, 460);
            StartPosition = FormStartPosition.CenterParent;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = false;

            BuildUi();

            Load += async (s, e) => await RefreshAsync();
        }

        private void BuildUi()
        {
            var lblHint = new Label
            {
                Left = 12,
                Top = 12,
                Width = 616,
                Text = "导入补丁后需要重启 CleanSlate 才会生效。"
            };

            _lblPatchDir = new Label
            {
                Left = 12,
                Top = 36,
                Width = 616,
                ForeColor = System.Drawing.SystemColors.GrayText
            };

            _list = new ListView
            {
                Left = 12,
                Top = 62,
                Width = 616,
                Height = 320,
                View = View.Details,
                FullRowSelect = true,
                GridLines = true,
                MultiSelect = false
            };
            _list.Columns.Add("文件名", 300);
            _list.Columns.Add("大小", 100, HorizontalAlignment.Right);
            _list.Columns.Add("状态", 180);

            _btnImport = new Button { Text = "导入补丁...", Left = 12, Top = 396, Width = 120, Height = 32 };
            _btnDelete = new Button { Text = "删除选中", Left = 142, Top = 396, Width = 120, Height = 32 };
            _btnRefresh = new Button { Text = "刷新", Left = 272, Top = 396, Width = 100, Height = 32 };
            _btnClose = new Button { Text = "关闭", Left = 528, Top = 396, Width = 100, Height = 32 };

            _btnImport.Click += async (s, e) => await ImportAsync();
            _btnDelete.Click += async (s, e) => await DeleteAsync();
            _btnRefresh.Click += async (s, e) => await RefreshAsync();
            _btnClose.Click += (s, e) => Close();

            Controls.AddRange(new Control[]
                { lblHint, _lblPatchDir, _list, _btnImport, _btnDelete, _btnRefresh, _btnClose });

            AcceptButton = _btnImport;
            CancelButton = _btnClose;
        }

        private async Task RefreshAsync()
        {
            _list.Items.Clear();
            _btnImport.Enabled = false;
            _btnDelete.Enabled = false;

            try
            {
                string json = await _api.GetPatchesAsync();
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                if (root.TryGetProperty("patch_dir", out var pd))
                    _lblPatchDir.Text = "补丁目录：" + pd.GetString();

                if (root.TryGetProperty("files", out var files)
                    && files.ValueKind == JsonValueKind.Array)
                {
                    foreach (var item in files.EnumerateArray())
                    {
                        string fn = item.TryGetProperty("filename", out var f) ? f.GetString() : "";
                        long size = item.TryGetProperty("size", out var sz) ? sz.GetInt64() : 0;
                        bool loaded = item.TryGetProperty("loaded", out var ld) && ld.GetBoolean();

                        var lvi = new ListViewItem(new[]
                        {
                            fn,
                            FormatSize(size),
                            loaded ? "已加载" : "未加载（重启后生效）"
                        })
                        { Tag = fn };

                        _list.Items.Add(lvi);
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, $"获取补丁列表失败：{ex.Message}", "错误",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                _btnImport.Enabled = true;
            }
        }

        private static string FormatSize(long bytes)
        {
            if (bytes < 1024) return bytes + " B";
            if (bytes < 1024 * 1024) return (bytes / 1024.0).ToString("F1") + " KB";
            return (bytes / (1024.0 * 1024)).ToString("F2") + " MB";
        }

        private async Task ImportAsync()
        {
            using var dlg = new OpenFileDialog
            {
                Title = "选择补丁文件",
                Filter = "补丁文件 (*.bcs;*.py)|*.bcs;*.py|所有文件 (*.*)|*.*",
                CheckFileExists = true
            };
            if (dlg.ShowDialog(this) != DialogResult.OK) return;

            string path = dlg.FileName;
            string name = Path.GetFileName(path);
            string b64;
            try
            {
                byte[] data = File.ReadAllBytes(path);
                b64 = Convert.ToBase64String(data);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, $"读取文件失败：{ex.Message}", "错误",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            try
            {
                await _api.ImportPatchAsync(name, b64);
                MessageBox.Show(this,
                    "补丁已导入。\n\n需要重启 CleanSlate 才会加载。",
                    "导入成功",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
                await RefreshAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, $"导入失败：{ex.Message}", "错误",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async Task DeleteAsync()
        {
            if (_list.SelectedItems.Count == 0)
            {
                MessageBox.Show(this, "请先选中一个文件。", "提示");
                return;
            }

            string filename = (string)_list.SelectedItems[0].Tag;

            var ans = MessageBox.Show(this,
                $"确定删除补丁文件「{filename}」吗？\n\n如果它已经被加载，重启后就不再生效。",
                "确认删除",
                MessageBoxButtons.YesNo, MessageBoxIcon.Warning);
            if (ans != DialogResult.Yes) return;

            try
            {
                await _api.DeletePatchAsync(filename);
                await RefreshAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, $"删除失败：{ex.Message}", "错误",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}