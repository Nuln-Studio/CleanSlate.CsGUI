using System.Runtime.InteropServices;

namespace CleanSlate.Launcher
{
    internal static class Program
    {
        [STAThread]
        static void Main()
        {
            ComWrappers.RegisterForMarshalling(WinFormsComInterop.WinFormsComWrappers.Instance);
            ApplicationConfiguration.Initialize();
            Application.Run(new Form1());
        }
    }
}