using System;
using System.Drawing;
using System.Linq;
using System.Reflection;

namespace CleanSlate.Launcher
{
    internal static class IconHelper
    {
        public static Icon Load()
        {
            try
            {
                var asm = Assembly.GetExecutingAssembly();
                string icoName = asm.GetManifestResourceNames()
                    .FirstOrDefault(n => n.EndsWith(".ico", StringComparison.OrdinalIgnoreCase));

                if (icoName != null)
                {
                    using var stream = asm.GetManifestResourceStream(icoName);
                    if (stream != null) return new Icon(stream);
                }
            }
            catch { }

            return SystemIcons.Application;
        }
    }
}