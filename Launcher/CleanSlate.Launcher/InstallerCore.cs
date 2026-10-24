using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;

namespace CleanSlate.Launcher
{
    internal static class InstallerCore
    {
        public static bool IsRunningFromTemp(string dir)
        {
            if (string.IsNullOrEmpty(dir)) return false;
            string lower = dir.ToLowerInvariant();
            return lower.Contains(@"\temp\")
                || lower.Contains(@"\7z")
                || lower.Contains(@"\winrar")
                || lower.Contains(@"\rar$")
                || lower.Contains(@"\appdata\local\temp");
        }

        public static bool IsDotNet8Installed()
        {
            string root = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                "dotnet", "shared", "Microsoft.WindowsDesktop.App");

            if (!Directory.Exists(root)) return false;

            foreach (var dir in Directory.GetDirectories(root))
            {
                string name = Path.GetFileName(dir);
                if (name.StartsWith("8.")) return true;
            }
            return false;
        }

        public static bool IsPathSafe(string path, out string reason)
        {
            reason = null;

            if (string.IsNullOrWhiteSpace(path))
            {
                reason = "安装路径不能为空。";
                return false;
            }

            string full;
            try
            {
                full = Path.GetFullPath(path).TrimEnd('\\').ToLowerInvariant();
            }
            catch
            {
                reason = "安装路径格式无效。";
                return false;
            }

            if (full == "c:")
            {
                reason = "不能安装到 C 盘根目录。";
                return false;
            }

            if (full == @"c:\windows" || full.StartsWith(@"c:\windows\"))
            {
                reason = "不能安装到 Windows 系统目录。";
                return false;
            }

            if (full == @"c:\program files" || full == @"c:\program files (x86)")
            {
                reason = "不能安装到 Program Files 根目录。";
                return false;
            }

            return true;
        }

        public static void ExtractResource(string resourceName, string targetDir)
        {
            var assembly = Assembly.GetExecutingAssembly();
            using Stream stream = assembly.GetManifestResourceStream(resourceName);
            if (stream == null)
                throw new Exception($"找不到内嵌资源: {resourceName}");

            if (!Directory.Exists(targetDir))
                Directory.CreateDirectory(targetDir);

            using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
            archive.ExtractToDirectory(targetDir, true);
        }

        public static void CreateDesktopShortcut(string targetExe, string workingDir)
        {
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string shortcutPath = Path.Combine(desktop, "CleanSlate.CsGUI.lnk");

            string targetEsc = targetExe.Replace("'", "''");
            string workEsc = workingDir.Replace("'", "''");
            string shortcutEsc = shortcutPath.Replace("'", "''");

            string ps = "$ws = New-Object -ComObject WScript.Shell; " +
                        $"$s = $ws.CreateShortcut('{shortcutEsc}'); " +
                        $"$s.TargetPath = '{targetEsc}'; " +
                        $"$s.WorkingDirectory = '{workEsc}'; " +
                        $"$s.IconLocation = '{targetEsc},0'; " +
                        $"$s.Description = '泥嚎哇~'; " +
                        "$s.Save()";


            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = $"-NoProfile -NonInteractive -WindowStyle Hidden -Command \"{ps}\"",
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var proc = Process.Start(psi);
            proc?.WaitForExit(8000);
        }

        public static void LaunchDotNetInstaller(string runtimePath)
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = runtimePath,
                UseShellExecute = true
            });
        }

        public static void LaunchApp(string exePath, string workingDir)
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = exePath,
                WorkingDirectory = workingDir,
                UseShellExecute = true
            });
        }

        public static string GetInstallRecordPath()
        {
            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "NulnStudio",
                "CleanSlate.CsGUI",
                "install.info");
        }

        public static (string InstallPath, string Version)? ReadInstallRecord()
        {
            try
            {
                string file = GetInstallRecordPath();
                if (File.Exists(file))
                {
                    string content = File.ReadAllText(file).Trim();
                    if (!string.IsNullOrEmpty(content))
                    {
                        string[] parts = content.Split('|');
                        if (parts.Length >= 2)
                        {
                            string path = parts[0].Trim();
                            string version = parts[1].Trim();
                            if (!string.IsNullOrEmpty(path) &&
                                File.Exists(Path.Combine(path, "CsUI.exe")))
                            {
                                return (path, version);
                            }
                        }
                    }
                }
            }
            catch { }

            string baseDir = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);

            var candidates = new List<string>
            {
                baseDir,
                Path.Combine(baseDir, "CleanSlate.CsGUI"),
                Path.Combine(baseDir, "CsUI"),
            };

            foreach (var dir in candidates)
            {
                try
                {
                    if (File.Exists(Path.Combine(dir, "CsUI.exe")))
                        return (dir, "");
                }
                catch { }
            }

            return null;
        }

        public static void WriteInstallRecord(string installPath, string version)
        {
            try
            {
                string file = GetInstallRecordPath();
                string dir = Path.GetDirectoryName(file);
                if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
                File.WriteAllText(file, $"{installPath}|{version}");
            }
            catch { }
        }
    }
}