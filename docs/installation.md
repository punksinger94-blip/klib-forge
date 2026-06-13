# Installation and Removal

## Windows desktop

1. Download `K-LIB Forge_1.0.0_x64-setup.exe` and `SHA256SUMS.txt`.
2. Verify the SHA-256 checksum and the Authenticode signature.
3. Run the installer. The desktop includes its Python API sidecar.

K-LIB Forge stores desktop runtime data under the application-local data
directory returned by Windows for `com.klibforge.desktop`.

Uninstall from Windows Settings > Apps. Removing the application does not
silently delete exported `.klib` packages. Remove the application data directory
separately only when its local libraries and run history are no longer needed.

## Python

```powershell
python -m pip install klib-forge==1.0.0
klib --help
klib-api
klib-mcp
```

For Chroma:

```powershell
python -m pip install "klib-forge[chroma]==1.0.0"
```

Uninstall with `python -m pip uninstall klib-forge`.
