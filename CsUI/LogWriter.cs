using System;
using System.IO;
using System.Text;

namespace CleanSlate.CsGUI
{
    internal class LogWriter : IDisposable
    {
        private readonly object _lock = new object();
        private StreamWriter _writer;

        public LogWriter(string path)
        {
            try
            {
                _writer = new StreamWriter(path, append: true, new UTF8Encoding(false))
                {
                    AutoFlush = true
                };
            }
            catch
            {
                _writer = null;
            }
        }

        public void Write(string level, string message)
        {
            if (_writer == null) return;
            string line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {message}";
            try
            {
                lock (_lock)
                {
                    _writer.WriteLine(line);
                }
            }
            catch { }
        }

        public void Dispose()
        {
            try
            {
                lock (_lock)
                {
                    _writer?.Flush();
                    _writer?.Dispose();
                    _writer = null;
                }
            }
            catch { }
        }
    }
}