namespace CleanSlate.CsGUI
{
    internal static class StatusPhrases
    {
        public const string SubjectSystem = "系统";
        public const string SubjectBackend = "后端启动";
        public const string SubjectScan = "扫描";
        public const string SubjectClean = "清理";

        public static string Initializing() => "正在初始化 CleanSlate 后端";
        public static string BackendStarting() => "正在启动 Backend，请允许 UAC 提权";
        public static string BackendChecking() => "正在检查后端健康状态";
        public static string BackendReady() => "后端已就绪";
        public static string IdleReady() => "就绪，可开始扫描";
        public static string BackendExited() => "后端已退出，请重启 CleanSlate";
        public static string BackendFailed() => "启动失败，请检查 UAC 是否被拒绝";

        public static string ScanSubmitting() => "正在提交扫描任务，请稍候";
        public static string ScanPreparing() => "正在准备扫描";
        public static string ScanDisk() => "正在扫描磁盘，请耐心等待";
        public static string ScanCounting() => "正在统计清理项";
        public static string ScanPatching() => "正在加载补丁";
        public static string ScanWrapping() => "正在收尾";
        public static string ScanDone(int n, double gb)
            => $"扫描完成，共 {n} 项，可释放 {gb:F2} GB";
        public static string ScanFailed() => "扫描失败，请查看日志";

        public static string CleanWorking(int n) => $"正在清理 {n} 项，请勿关闭窗口";
        public static string CleanDone(int ok, int fail, double gb)
            => $"清理完成，请务必重新进行扫描，成功 {ok} / 失败 {fail}，释放 {gb:F2} GB";
        public static string CleanFailed() => "清理失败，请查看日志";
    }
}