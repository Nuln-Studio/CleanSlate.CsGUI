using System;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace CleanSlate.CsGUI
{
    public class ApiClient : IDisposable
    {
        private readonly HttpClient _http;
        private string _baseUrl;

        public ApiClient()
        {
            _http = new HttpClient { Timeout = TimeSpan.FromSeconds(120) };
        }

        public void Configure(int port, string token)
        {
            _baseUrl = $"http://127.0.0.1:{port}/";
            _http.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Bearer", token);
        }

        public async Task<bool> HealthAsync()
        {
            try
            {
                var resp = await _http.GetAsync(_baseUrl + "health");
                return resp.IsSuccessStatusCode;
            }
            catch { return false; }
        }

        public async Task<string> GetStatusAsync()
        {
            var resp = await _http.GetAsync(_baseUrl + "status");
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task<string> GetVersionAsync()
        {
            var resp = await _http.GetAsync(_baseUrl + "version");
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task<string> StartScanAsync()
        {
            var resp = await _http.PostAsync(_baseUrl + "scan", null);
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task<string> GetScanTaskAsync(string taskId)
        {
            var resp = await _http.GetAsync(_baseUrl + $"scan_task/{taskId}");
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task<string> CleanAsync(string[] ids, bool allowHighRisk)
        {
            var payload = JsonSerializer.Serialize(new
            {
                ids,
                allow_high_risk = allowHighRisk
            });
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var resp = await _http.PostAsync(_baseUrl + "clean", content);
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task ShutdownAsync()
        {
            try { await _http.PostAsync(_baseUrl + "shutdown", null); }
            catch { }
        }
        public async Task<string> GetConfigAsync()
        {
            var resp = await _http.GetAsync(_baseUrl + "config");
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task<string> SetConfigAsync(string jsonPayload)
        {
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");
            var resp = await _http.PostAsync(_baseUrl + "config", content);
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }
        public async Task<string> ExportConfigAsync()
        {
            var resp = await _http.GetAsync(_baseUrl + "config/export");
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task<string> ImportConfigAsync(string yamlContent)
        {
            var payload = JsonSerializer.Serialize(new { content = yamlContent });
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var resp = await _http.PostAsync(_baseUrl + "config/import", content);
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }
        public async Task<string> GetPatchesAsync()
        {
            var resp = await _http.GetAsync(_baseUrl + "patches");
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task<string> ImportPatchAsync(string filename, string contentBase64)
        {
            var payload = JsonSerializer.Serialize(new
            {
                filename,
                content_b64 = contentBase64
            });
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var resp = await _http.PostAsync(_baseUrl + "patches/import", content);
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }

        public async Task<string> DeletePatchAsync(string filename)
        {
            var payload = JsonSerializer.Serialize(new { filename });
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var resp = await _http.PostAsync(_baseUrl + "patches/delete", content);
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }
        public async Task<string> GetCleanTaskAsync(string taskId)
        {
            var resp = await _http.GetAsync(_baseUrl + $"clean_task/{taskId}");
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsStringAsync();
        }
        public void Dispose() => _http?.Dispose();
    }
}