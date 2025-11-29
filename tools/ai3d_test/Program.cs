using System;
using System.Linq;
using System.Reflection;
using System.IO;

Console.WriteLine("ai3d_test: detecting TencentCloud Ai3d SDK and environment...");

string secretId = Environment.GetEnvironmentVariable("TENCENT_SECRET_ID") ?? string.Empty;
string secretKey = Environment.GetEnvironmentVariable("TENCENT_SECRET_KEY") ?? string.Empty;

string Mask(string s)
{
	if (string.IsNullOrEmpty(s)) return "(not set)";
	if (s.Length <= 6) return s.Substring(0, Math.Min(4, s.Length)) + "...";
	return s.Substring(0, 4) + "..." + s.Substring(s.Length - 2);
}

Console.WriteLine($"SecretId: {Mask(secretId)}");
Console.WriteLine($"SecretKey: {Mask(secretKey)}");

// Look for loaded assemblies that mention Ai3d or TencentCloudSDK.Ai3d
var loaded = AppDomain.CurrentDomain.GetAssemblies();
var currentName = Assembly.GetExecutingAssembly().GetName().Name;
var candidates = loaded.Where(a => a.FullName != null && a.GetName().Name != currentName && (a.FullName.IndexOf("Ai3d", StringComparison.OrdinalIgnoreCase) >= 0 || a.FullName.IndexOf("TencentCloudSDK.Ai3d", StringComparison.OrdinalIgnoreCase) >= 0)).ToList();

if (!candidates.Any())
{
	// Try to load the assembly by name if not already loaded
	try
	{
		var asm = Assembly.Load("TencentCloudSDK.Ai3d");
		if (asm != null) candidates.Add(asm);
	}
	catch { }
}

// If still not found, try loading any DLLs from the output directory that include "ai3d" in the filename
if (!candidates.Any())
{
	try
	{
		var baseDir = AppContext.BaseDirectory;
		Console.WriteLine($"Output base directory: {baseDir}");
		var allDlls = Directory.GetFiles(baseDir, "*.dll");
		Console.WriteLine($"DLLs in output folder: {allDlls.Length}");
		var files = allDlls.Where(p => p.IndexOf("ai3d", StringComparison.OrdinalIgnoreCase) >= 0).ToArray();
		Console.WriteLine($"DLLs matching 'ai3d': {files.Length}");
		foreach (var f in files)
		{
			Console.WriteLine($"Attempting to load DLL from output folder: {Path.GetFileName(f)}");
			try
			{
				var a = Assembly.LoadFrom(f);
				Console.WriteLine($"  Loaded: {a.GetName().Name} ({a.GetName().Version})");
				if (a != null && !candidates.Any(x => x.FullName == a.FullName)) candidates.Add(a);
			}
			catch (Exception ex)
			{
				Console.WriteLine($"  Failed to load {Path.GetFileName(f)}: {ex.GetType().Name} {ex.Message}");
			}
		}
	}
	catch { }
}

if (!candidates.Any())
{
	Console.WriteLine("TencentCloudSDK.Ai3d assembly not found in the app domain or output folder.");
	Console.WriteLine("Installed packages are present in the project; if you want a network test, we can add a sample call next.");
	return;
}

Console.WriteLine($"Found {candidates.Count} assembly(ies) referencing Ai3d:");
for (int i = 0; i < candidates.Count; i++)
{
	var a = candidates[i];
	Console.WriteLine($"  [{i}] {a.GetName().Name}  ({a.GetName().Version})");
}

// Inspect types that look like client classes
foreach (var asm in candidates)
{
	var clientTypes = asm.GetExportedTypes().Where(t => t.Name.EndsWith("Client") || t.Name.IndexOf("Ai3d", StringComparison.OrdinalIgnoreCase) >= 0).ToArray();
	if (!clientTypes.Any()) continue;

	Console.WriteLine($"\nAssembly {asm.GetName().Name} client-like types:");
	foreach (var t in clientTypes)
	{
		Console.WriteLine($"- {t.FullName}");
		var methods = t.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly)
			.Select(m => m.Name).Distinct().Take(20).ToArray();
		if (methods.Any())
		{
			Console.WriteLine($"  Methods (sample up to 20): {string.Join(", ", methods)}");
		}
	}
}

Console.WriteLine("\nReflection inspection complete.");
Console.WriteLine("If you want, I can add a concrete API call example next (requires knowing which API call you want to run).");
